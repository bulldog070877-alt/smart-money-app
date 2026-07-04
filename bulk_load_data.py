"""
One-time bulk loader: pre-populates the Neon `prices` cache for every symbol
in the S&P 500 + NIFTY 500 universes, across every timeframe any registered
strategy needs (currently monthly/weekly/daily). Run this once so
interactive backtests/screener runs read from Neon instead of paying the
yfinance network cost on every first-touch of a symbol.

Safe to re-run: it reuses data_store.get_history(), which only fetches bars
newer than what's already cached, so a second run is a fast top-up, not a
full re-download.

Usage:
    python bulk_load_data.py [--workers N]
"""
import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from data_store import get_history
from market_universe import SP500_TICKERS, NIFTY500_TICKERS
from strategies import STRATEGIES

DEFAULT_WORKERS = 10


def all_timeframes():
    tfs = set()
    for mod in STRATEGIES.values():
        tfs.update(mod.TIMEFRAMES)
    return sorted(tfs)


def all_symbols():
    return sorted(set(SP500_TICKERS) | set(NIFTY500_TICKERS))


def load_one(symbol, interval):
    df = get_history(symbol, interval)
    return len(df) if df is not None else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()

    symbols = all_symbols()
    timeframes = all_timeframes()
    tasks = [(s, tf) for s in symbols for tf in timeframes]
    total = len(tasks)
    print(f"Loading {len(symbols)} symbols x {len(timeframes)} timeframes {timeframes} "
          f"= {total} fetches, {args.workers} workers...")

    t0 = time.time()
    done = 0
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(load_one, s, tf): (s, tf) for s, tf in tasks}
        for future in as_completed(futures):
            symbol, interval = futures[future]
            done += 1
            try:
                rows = future.result()
                if rows == 0:
                    failed.append((symbol, interval, "no data returned"))
            except Exception as e:
                failed.append((symbol, interval, str(e)))
            if done % 50 == 0 or done == total:
                elapsed = time.time() - t0
                print(f"[{done}/{total}] elapsed {elapsed:.0f}s, {len(failed)} failed so far", flush=True)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s. {total - len(failed)}/{total} succeeded, {len(failed)} failed.")
    if failed:
        print("\nFailures:")
        for symbol, interval, reason in failed:
            print(f"  {symbol} {interval}: {reason}")


if __name__ == "__main__":
    main()
