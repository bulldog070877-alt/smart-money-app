"""
Daily forward-test scan for the Momentum Reversal (Oversold Bounce) strategy.

Meant to run once per trading day via a scheduled GitHub Actions workflow
(.github/workflows/momentum_scan.yml), independent of whether the Streamlit
app itself is awake. Requires NEON_DATABASE_URL as an environment variable
(data_store.connection_string() falls back to it when no Streamlit secrets
source is present).

Each run does two things against the momentum_predictions table:

  1. Resolve open predictions against fresh price data:
       - 'awaiting_entry' -> a bar after signal_date has appeared, so the
         entry is now realized. Lock in the actual entry date/price (next
         bar's Open, exactly matching backtest_symbol's rule) and recompute
         target/stop off the real entry price, moving it to 'pending'.
       - 'pending' -> check whether target/stop has been hit, or whether the
         MAX_DAYS holding window has fully elapsed (-> pending_positive /
         pending_negative, matching momentum_reversal._grade's rules).

  2. Screen the configured universe for new "ENTRY TOMORROW" signals and
     record them as 'awaiting_entry'. A symbol with an already-open
     prediction (awaiting_entry or pending) is skipped, so tracked positions
     don't overlap - the same non-overlap rule backtest_symbol enforces.

Run manually with: python daily_momentum_scan.py
"""
import sys
from datetime import date, datetime

import psycopg2

import data_store
from market_universe import SP500_TICKERS
from strategies import momentum_reversal as strat

PARAMS = dict(strat.DEFAULT_PARAMS)  # forward-test with the strategy's defaults
UNIVERSE = SP500_TICKERS


def _conn():
    return psycopg2.connect(data_store.connection_string())


def _grade_window(window, entry_price, target, stop, max_days):
    """Mirrors momentum_reversal._grade's win/loss/pending logic over an
    already-sliced window of bars starting at the entry bar."""
    for k in range(len(window)):
        hi, lo = window['High'].iloc[k], window['Low'].iloc[k]
        if hi >= target:
            return 'win', target, window.index[k].date()
        if stop is not None and lo <= stop:
            return 'loss', stop, window.index[k].date()
    if len(window) >= max_days:
        last_close = window['Close'].iloc[-1]
        outcome = 'pending_positive' if last_close > entry_price else 'pending_negative'
        return outcome, None, None
    return 'pending', None, None  # window not complete yet - still open


def resolve_awaiting_entries(conn):
    """Turn 'awaiting_entry' rows into 'pending' once a real entry bar exists."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, symbol, signal_date, entry_price_est, max_days "
            "FROM momentum_predictions WHERE outcome = 'awaiting_entry'"
        )
        rows = cur.fetchall()

    resolved = 0
    for pred_id, symbol, signal_date, target_est, max_days in rows:
        df = data_store.get_history(symbol, "1d")
        if df is None:
            continue
        after = df[df.index.date > signal_date]
        if len(after) == 0:
            continue  # tomorrow's bar hasn't landed yet

        entry_date = after.index[0].date()
        entry_price = round(float(after['Open'].iloc[0]), 2)
        target = round(entry_price * (1 + PARAMS['TARGET_PCT'] / 100), 2)
        stop = round(entry_price * (1 - PARAMS['STOP_PCT'] / 100), 2) if PARAMS.get('ENABLE_STOP') else None

        window = after.iloc[:max_days]
        outcome, exit_price, exit_date = _grade_window(window, entry_price, target, stop, max_days)

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE momentum_predictions SET "
                "entry_date=%s, entry_price_est=%s, target=%s, stop_loss=%s, "
                "outcome=%s, exit_price=%s, exit_date=%s, checked_at=%s "
                "WHERE id=%s",
                (entry_date, entry_price, target, stop,
                 outcome, exit_price, exit_date, datetime.now(), pred_id),
            )
        conn.commit()
        resolved += 1
    return resolved


def grade_pending(conn):
    """Re-check every already-entered, still-open prediction."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, symbol, entry_date, entry_price_est, target, stop_loss, max_days "
            "FROM momentum_predictions WHERE outcome IN ('pending','pending_positive','pending_negative')"
        )
        rows = cur.fetchall()

    updated = 0
    for pred_id, symbol, entry_date, entry_price, target, stop, max_days in rows:
        df = data_store.get_history(symbol, "1d")
        if df is None:
            continue
        window = df[df.index.date >= entry_date].iloc[:max_days]
        if len(window) == 0:
            continue

        outcome, exit_price, exit_date = _grade_window(window, entry_price, target, stop, max_days)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE momentum_predictions SET outcome=%s, exit_price=%s, exit_date=%s, checked_at=%s "
                "WHERE id=%s",
                (outcome, exit_price, exit_date, datetime.now(), pred_id),
            )
        conn.commit()
        updated += 1
    return updated


def scan_new_signals(conn, universe):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT symbol FROM momentum_predictions "
            "WHERE outcome IN ('awaiting_entry','pending')"
        )
        already_open = {r[0] for r in cur.fetchall()}

    new_count = 0
    for symbol in universe:
        if symbol in already_open:
            continue
        try:
            df = data_store.get_history(symbol, "1d")
            if df is None or len(df) < PARAMS['LOOKBACK'] + 2:
                continue
            current_price = round(float(df['Close'].iloc[-1]), 2)
            result = strat.screen_symbol((df,), current_price, PARAMS)
            if result is None:
                continue

            signal_date = df.index[-1].date()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO momentum_predictions "
                    "(symbol, signal_date, entry_date, entry_price_est, target, stop_loss, "
                    " max_days, prior_volatility, pos_in_range, signal_gap_pct, volume_ratio, "
                    " outcome, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'awaiting_entry',%s) "
                    "ON CONFLICT (symbol, signal_date) DO NOTHING",
                    (symbol, signal_date, signal_date, current_price,
                     result['push_high'], result['push_low'] if PARAMS.get('ENABLE_STOP') else None,
                     PARAMS['MAX_DAYS'], result['prior_volatility'], result['pos_in_range'],
                     result['signal_gap_pct'], result['volume_ratio'], datetime.now()),
                )
                if cur.rowcount:
                    new_count += 1
            conn.commit()
        except Exception as e:
            print(f"  ! {symbol}: {e}", file=sys.stderr)
    return new_count


def main():
    print(f"[{datetime.now()}] Momentum Reversal daily scan starting "
          f"({len(UNIVERSE)} symbols in universe)")
    conn = _conn()
    try:
        resolved = resolve_awaiting_entries(conn)
        print(f"  entries realized: {resolved}")
        graded = grade_pending(conn)
        print(f"  predictions graded: {graded}")
        new = scan_new_signals(conn, UNIVERSE)
        print(f"  new signals recorded: {new}")
    finally:
        conn.close()
    print(f"[{datetime.now()}] Done.")


if __name__ == "__main__":
    main()
