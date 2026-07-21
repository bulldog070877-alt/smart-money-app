"""
Daily forward-test scan for the Demand Zone (SQL Two-Pass) strategy.

Meant to run once per trading day via a scheduled GitHub Actions workflow
(.github/workflows/demand_zone_scan.yml), independent of whether the
Streamlit app itself is awake. Requires NEON_DATABASE_URL as an environment
variable (data_store.connection_string() falls back to it when no Streamlit
secrets source is present).

Mirrors daily_momentum_scan.py's two-step structure against the
demand_zone_predictions table:

  1. Resolve open predictions against fresh price data:
       - 'awaiting_entry' -> a bar after signal_date has appeared, so the
         entry is now realized. Lock in the actual entry date/price (next
         bar's Open, exactly matching demand_zone_sql.backtest_symbol's
         rule) and recompute target off the real entry price - stop_loss
         stays as the zone's low, which is fixed at signal time and never
         depends on the realized entry price.
       - 'pending' -> check whether target/stop has been hit, or whether
         the hold_days window has fully elapsed (-> pending_positive /
         pending_negative).

  2. Screen the configured universe once (scan_universe): every symbol's
     current status is saved to demand_zone_watchlist as a dated snapshot
     (kept as history, not overwritten - see pages/demand_zone_watchlist.py).
     Symbols with a genuine new "ENTRY TOMORROW" signal (a zone touched
     today that also passes the risk/RR filters) additionally open a
     forward-test prediction in demand_zone_predictions, unless that symbol
     already has one open, so tracked positions don't overlap.

Run manually with: python daily_demand_zone_scan.py
"""
import sys
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values

import data_store
from market_universe import SP500_TICKERS
from strategies import demand_zone_sql as strat

PARAMS = dict(strat.DEFAULT_PARAMS)  # forward-test with the strategy's defaults
UNIVERSE = SP500_TICKERS


def _conn():
    return psycopg2.connect(data_store.connection_string())


def _ensure_alive(conn):
    """Neon's free-tier compute can idle-suspend during the ~20-minute
    per-symbol scoring loop in scan_universe, leaving this connection dead
    by the time we're ready to write - verify it's still alive and
    reconnect if not, rather than losing the whole run's work at the last
    step."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn
    except psycopg2.Error:
        try:
            conn.close()
        except Exception:
            pass
        return _conn()


def _grade_window(window, entry_price, target, stop, hold_days):
    """Mirrors demand_zone_sql.backtest_symbol's win/loss/pending logic over
    an already-sliced window of bars starting at the entry bar."""
    for k in range(len(window)):
        hi, lo = window['High'].iloc[k], window['Low'].iloc[k]
        if hi >= target:
            return 'win', target, window.index[k].date()
        if stop is not None and lo <= stop:
            return 'loss', stop, window.index[k].date()
    if len(window) >= hold_days:
        last_close = window['Close'].iloc[-1]
        outcome = 'pending_positive' if last_close > entry_price else 'pending_negative'
        return outcome, None, None
    return 'pending', None, None  # window not complete yet - still open


def resolve_awaiting_entries(conn):
    """Turn 'awaiting_entry' rows into 'pending' once a real entry bar exists."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, symbol, signal_date, stop_loss, hold_days "
            "FROM demand_zone_predictions WHERE outcome = 'awaiting_entry'"
        )
        rows = cur.fetchall()

    resolved = 0
    for pred_id, symbol, signal_date, stop, hold_days in rows:
        df = data_store.get_history(symbol, "1d")
        if df is None:
            continue
        after = df[df.index.date > signal_date]
        if len(after) == 0:
            continue  # tomorrow's bar hasn't landed yet

        entry_date = after.index[0].date()
        entry_price = round(float(after['Open'].iloc[0]), 2)
        target = round(entry_price * (1 + PARAMS['TARGET_PCT'] / 100), 2)

        window = after.iloc[:hold_days]
        outcome, exit_price, exit_date = _grade_window(window, entry_price, target, stop, hold_days)

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE demand_zone_predictions SET "
                "entry_date=%s, entry_price_est=%s, target=%s, "
                "outcome=%s, exit_price=%s, exit_date=%s, checked_at=%s "
                "WHERE id=%s",
                (entry_date, entry_price, target,
                 outcome, exit_price, exit_date, datetime.now(), pred_id),
            )
        conn.commit()
        resolved += 1
    return resolved


def grade_pending(conn):
    """Re-check every already-entered, still-open prediction."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, symbol, entry_date, entry_price_est, target, stop_loss, hold_days "
            "FROM demand_zone_predictions WHERE outcome IN ('pending','pending_positive','pending_negative')"
        )
        rows = cur.fetchall()

    updated = 0
    for pred_id, symbol, entry_date, entry_price, target, stop, hold_days in rows:
        df = data_store.get_history(symbol, "1d")
        if df is None:
            continue
        window = df[df.index.date >= entry_date].iloc[:hold_days]
        if len(window) == 0:
            continue

        outcome, exit_price, exit_date = _grade_window(window, entry_price, target, stop, hold_days)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE demand_zone_predictions SET outcome=%s, exit_price=%s, exit_date=%s, checked_at=%s "
                "WHERE id=%s",
                (outcome, exit_price, exit_date, datetime.now(), pred_id),
            )
        conn.commit()
        updated += 1
    return updated


def _record_watchlist(conn, symbol, scan_date, result):
    """Save this symbol's current status to demand_zone_watchlist, regardless
    of whether it's an actionable signal - one row per (symbol, scan_date),
    kept as history rather than overwritten, so status changes over time are
    visible on the watchlist page."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO demand_zone_watchlist "
            "(symbol, scan_date, status, current_price, push_high, push_low, push_pct, "
            " fifty_pct, retracement_pct, zone_type, zone_low, zone_high, weekly_refined, "
            " distance_pct, rr_ratio) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (symbol, scan_date) DO UPDATE SET "
            "status=EXCLUDED.status, current_price=EXCLUDED.current_price, "
            "push_high=EXCLUDED.push_high, push_low=EXCLUDED.push_low, push_pct=EXCLUDED.push_pct, "
            "fifty_pct=EXCLUDED.fifty_pct, retracement_pct=EXCLUDED.retracement_pct, "
            "zone_type=EXCLUDED.zone_type, zone_low=EXCLUDED.zone_low, zone_high=EXCLUDED.zone_high, "
            "weekly_refined=EXCLUDED.weekly_refined, distance_pct=EXCLUDED.distance_pct, "
            "rr_ratio=EXCLUDED.rr_ratio",
            (symbol, scan_date, result['status'], result['current_price'], result['push_high'],
             result['push_low'], result['push_pct'], result['50pct_level'], result['retracement_pct'],
             result['zone_type'], result['zone_low'], result['zone_high'], result['weekly_refined'],
             result['distance_pct'], result['rr_ratio']),
        )


def scan_universe(conn, universe):
    """Single pass over the universe: records every currently-qualifying
    symbol's status to demand_zone_watchlist as a clean replacement of that
    day's snapshot, and additionally opens a forward-test prediction in
    demand_zone_predictions for symbols with a genuine new 'ENTRY TOMORROW'
    signal.

    Scores every symbol first (without writing), then deletes any existing
    watchlist rows for the scan_date(s)/symbols just scored, before writing
    fresh results - otherwise a symbol that no longer qualifies (e.g. its
    zone just got invalidated) would leave its last-qualifying-day's stale
    row sitting in the table forever, since nothing would ever touch it
    again once it stops producing a result."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT symbol FROM demand_zone_predictions "
            "WHERE outcome IN ('awaiting_entry','pending')"
        )
        already_open = {r[0] for r in cur.fetchall()}

    scored = []  # (symbol, scan_date, current_price, result-or-None)
    for symbol in universe:
        try:
            df = data_store.get_history(symbol, "1d")
            if df is None or len(df) < 10:
                continue
            df = df.copy()
            df.attrs['symbol'] = symbol
            current_price = round(float(df['Close'].iloc[-1]), 2)
            result = strat.screen_symbol((df,), current_price, PARAMS)
            scan_date = df.index[-1].date()
            scored.append((symbol, scan_date, current_price, result))
        except Exception as e:
            print(f"  ! {symbol}: {e}", file=sys.stderr)

    conn = _ensure_alive(conn)  # the scoring loop above can take ~20 min

    # Scoped to exactly the (symbol, scan_date) pairs just re-scored - not
    # every symbol in the universe. A symbol that merely failed to fetch
    # this run (transient network blip) is simply absent from `scored`, so
    # its last-known-good row from a previous run is left untouched instead
    # of being wiped with nothing to replace it.
    pairs = [(symbol, scan_date) for symbol, scan_date, _, _ in scored]
    if pairs:
        with conn.cursor() as cur:
            execute_values(
                cur,
                "DELETE FROM demand_zone_watchlist WHERE (symbol, scan_date) IN (VALUES %s)",
                pairs,
            )
        conn.commit()

    watchlisted, new_count = 0, 0
    for symbol, scan_date, current_price, result in scored:
        if result is None:
            continue
        try:
            _record_watchlist(conn, symbol, scan_date, result)
            watchlisted += 1

            if result['status'] == 'ENTRY TOMORROW' and symbol not in already_open:
                target_est = round(result['zone_high'] * (1 + PARAMS['TARGET_PCT'] / 100), 2)
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO demand_zone_predictions "
                        "(symbol, signal_date, entry_date, entry_price_est, target, stop_loss, "
                        " hold_days, zone_type, zone_low, zone_high, weekly_refined, push_pct, "
                        " rr_ratio, outcome, created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'awaiting_entry',%s) "
                        "ON CONFLICT (symbol, signal_date) DO NOTHING",
                        (symbol, scan_date, scan_date, current_price, target_est, result['zone_low'],
                         PARAMS['HOLD_DAYS'], result['zone_type'], result['zone_low'], result['zone_high'],
                         result['weekly_refined'], result['push_pct'], result['rr_ratio'], datetime.now()),
                    )
                    if cur.rowcount:
                        new_count += 1
            conn.commit()
        except Exception as e:
            print(f"  ! {symbol}: {e}", file=sys.stderr)
    return watchlisted, new_count


def main():
    print(f"[{datetime.now()}] Demand Zone daily scan starting "
          f"({len(UNIVERSE)} symbols in universe)")
    conn = _conn()
    try:
        resolved = resolve_awaiting_entries(conn)
        print(f"  entries realized: {resolved}")
        graded = grade_pending(conn)
        print(f"  predictions graded: {graded}")
        watchlisted, new = scan_universe(conn, UNIVERSE)
        print(f"  symbols watchlisted: {watchlisted}, new signals recorded: {new}")
    finally:
        try:
            conn.close()
        except Exception:
            pass  # scan_universe may have reconnected internally; this handle can be stale
    print(f"[{datetime.now()}] Done.")


if __name__ == "__main__":
    main()
