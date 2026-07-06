"""
One-off research scan: finds every instance where a stock's price achieved
at least a given % gain within a rolling N-day window, for later pattern
analysis (looking for what these winners had in common beforehand).

Not a formal strategies/ module - this is a discovery tool, not a
backtestable buy/sell strategy (no entry/exit/stop rules of its own).
Events are non-overlapping: after a qualifying window is found, the scan
skips past its peak day before looking for the next one, rather than
capturing every overlapping 5-day window around the same underlying move.

Usage:
    python scan_momentum_events.py [--min-gain 1.5] [--window 5] [--universe optimised|sp500]
"""
import argparse

import pandas as pd

from data_store import get_history


def find_momentum_events(df, min_gain_pct=1.5, window_days=5):
    """entry = Close[D]; checks the best High reachable within the next
    window_days bars. Returns one event per non-overlapping qualifying move,
    each tagged with which day (1..window_days) the peak fell on."""
    events = []
    i = 0
    n = len(df)
    while i < n - 1:
        entry_price = df['Close'].iloc[i]
        entry_date = df.index[i]
        window = df.iloc[i + 1: i + 1 + window_days]
        if len(window) == 0 or entry_price <= 0:
            i += 1
            continue

        gains = (window['High'] - entry_price) / entry_price * 100
        max_gain = gains.max()
        if max_gain >= min_gain_pct:
            peak_pos = int(gains.values.argmax())
            peak_date = window.index[peak_pos]
            peak_price = window['High'].iloc[peak_pos]
            days_to_peak = peak_pos + 1  # 1-indexed within the window
            events.append({
                'entry_date': str(entry_date.date()),
                'entry_price': round(float(entry_price), 2),
                'peak_date': str(peak_date.date()),
                'peak_price': round(float(peak_price), 2),
                'days_to_peak': days_to_peak,
                'max_gain_pct': round(float(max_gain), 2),
            })
            i += days_to_peak + 1  # skip past this event - avoid overlap
        else:
            i += 1
    return events


def scan_universe(symbols, min_gain_pct=1.5, window_days=5, interval='1d'):
    all_events = []
    for sym in symbols:
        df = get_history(sym, interval)
        if df is None or len(df) < window_days + 1:
            continue
        for e in find_momentum_events(df, min_gain_pct, window_days):
            e['symbol'] = sym
            all_events.append(e)
    return all_events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--min-gain', type=float, default=1.5)
    parser.add_argument('--window', type=int, default=5)
    parser.add_argument('--universe', choices=['optimised', 'sp500'], default='optimised')
    parser.add_argument('--out', default='momentum_events.csv')
    args = parser.parse_args()

    if args.universe == 'optimised':
        from pages.backtest import OPTIMISED_UNIVERSE
        symbols = sorted({t for tickers in OPTIMISED_UNIVERSE.values() for t in tickers})
    else:
        from market_universe import SP500_TICKERS
        symbols = SP500_TICKERS

    print(f"Scanning {len(symbols)} symbols, min_gain={args.min_gain}%, window={args.window} days...")
    events = scan_universe(symbols, args.min_gain, args.window)
    df = pd.DataFrame(events)
    if len(df) > 0:
        df = df.sort_values(['symbol', 'entry_date']).reset_index(drop=True)
    df.to_csv(args.out, index=False)
    print(f"Found {len(df)} events across {df['symbol'].nunique() if len(df) else 0} symbols. Saved to {args.out}")
    if len(df) > 0:
        print("\nDays-to-peak distribution:")
        print(df['days_to_peak'].value_counts().sort_index())


if __name__ == "__main__":
    main()
