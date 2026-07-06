"""
Research pass: for every "fast spike" event (a >=MIN_GAIN% move that peaked
within FAST_PEAK days), compute quantifiable features of the price action
*before* the entry day, then compare their distributions against a random
baseline of non-event days from the same stocks.

The point is to find what, if anything, systematically precedes a sharp
spike - measured, not eyeballed - so a real pattern (if one exists) can
later be turned into a proper entry rule.

Outputs two CSVs: spike_precursors.csv and baseline_precursors.csv.
"""
import argparse
import random

import numpy as np
import pandas as pd

from data_store import get_history
from scan_momentum_events import find_momentum_events

LOOKBACK = 20  # trading days of precursor context


def _features(df, i):
    """Precursor features computed from the LOOKBACK bars ending at day i-1
    (strictly before the entry day i). Returns None if not enough history."""
    if i < LOOKBACK + 1:
        return None
    prior = df.iloc[i - LOOKBACK:i]              # the LOOKBACK days before entry
    entry = df.iloc[i]
    prev = df.iloc[i - 1]

    closes = prior['Close']
    rets = closes.pct_change().dropna() * 100
    prior_hi = prior['High'].max()
    prior_lo = prior['Low'].min()
    rng = prior_hi - prior_lo

    # consecutive down closes immediately before entry
    down_streak = 0
    for j in range(len(prior) - 1, 0, -1):
        if prior['Close'].iloc[j] < prior['Close'].iloc[j - 1]:
            down_streak += 1
        else:
            break

    entry_close = entry['Close']
    gap_pct = (entry['Open'] - prev['Close']) / prev['Close'] * 100 if prev['Close'] else 0.0
    vol_mean = prior['Volume'].mean()
    entry_vol_ratio = entry['Volume'] / vol_mean if vol_mean else np.nan

    return {
        'prior_trend_pct': round((closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0] * 100, 2),
        'prior_volatility': round(rets.std(), 2),
        'prior_range_pct': round(rng / prior_lo * 100, 2) if prior_lo else np.nan,
        'pos_in_range': round((entry_close - prior_lo) / rng, 2) if rng else np.nan,  # 0=at low, 1=at high
        'down_streak': down_streak,
        'entry_gap_pct': round(gap_pct, 2),
        'entry_vol_ratio': round(entry_vol_ratio, 2) if not np.isnan(entry_vol_ratio) else np.nan,
        'dow': entry.name.dayofweek,  # 0=Mon
    }


def collect(symbols, min_gain, window, fast_peak, baseline_per_symbol, seed=42):
    random.seed(seed)
    spikes, baseline = [], []
    for sym in symbols:
        df = get_history(sym, '1d')
        if df is None or len(df) < LOOKBACK + window + 2:
            continue
        # map entry_date -> index for quick lookup
        date_to_i = {str(d.date()): k for k, d in enumerate(df.index)}
        events = find_momentum_events(df, min_gain, window)
        spike_idx = set()
        for e in events:
            if e['days_to_peak'] <= fast_peak:
                i = date_to_i.get(e['entry_date'])
                if i is None:
                    continue
                f = _features(df, i)
                if f is None:
                    continue
                f.update({'symbol': sym, 'entry_date': e['entry_date'],
                          'days_to_peak': e['days_to_peak'], 'max_gain_pct': e['max_gain_pct']})
                spikes.append(f)
                spike_idx.add(i)

        # baseline: random days from this symbol that are NOT spike-event days
        candidates = [k for k in range(LOOKBACK + 1, len(df) - window - 1) if k not in spike_idx]
        for k in random.sample(candidates, min(baseline_per_symbol, len(candidates))):
            f = _features(df, k)
            if f is None:
                continue
            f.update({'symbol': sym, 'entry_date': str(df.index[k].date())})
            baseline.append(f)
    return pd.DataFrame(spikes), pd.DataFrame(baseline)


def summarize(spikes, baseline):
    cols = ['prior_trend_pct', 'prior_volatility', 'prior_range_pct', 'pos_in_range',
            'down_streak', 'entry_gap_pct', 'entry_vol_ratio']
    print(f"\nSpike events: {len(spikes)}   Baseline days: {len(baseline)}\n")
    print(f"{'feature':<18}{'spike median':>14}{'baseline median':>18}{'spike mean':>13}{'base mean':>12}")
    for c in cols:
        s, b = spikes[c].dropna(), baseline[c].dropna()
        print(f"{c:<18}{s.median():>14.2f}{b.median():>18.2f}{s.mean():>13.2f}{b.mean():>12.2f}")
    print("\nDay-of-week (0=Mon) share:")
    print("  spike:   ", spikes['dow'].value_counts(normalize=True).sort_index().round(3).to_dict())
    print("  baseline:", baseline['dow'].value_counts(normalize=True).sort_index().round(3).to_dict())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--min-gain', type=float, default=5.0)
    p.add_argument('--window', type=int, default=5)
    p.add_argument('--fast-peak', type=int, default=2, help='only events peaking within this many days')
    p.add_argument('--baseline-per-symbol', type=int, default=40)
    p.add_argument('--universe', choices=['optimised', 'sp500'], default='optimised')
    args = p.parse_args()

    if args.universe == 'optimised':
        from pages.backtest import OPTIMISED_UNIVERSE
        symbols = sorted({t for tickers in OPTIMISED_UNIVERSE.values() for t in tickers})
    else:
        from market_universe import SP500_TICKERS
        symbols = SP500_TICKERS

    print(f"Scanning {len(symbols)} symbols: >={args.min_gain}% within {args.window}d, "
          f"peak within {args.fast_peak}d...")
    spikes, baseline = collect(symbols, args.min_gain, args.window, args.fast_peak,
                               args.baseline_per_symbol)
    spikes.to_csv('spike_precursors.csv', index=False)
    baseline.to_csv('baseline_precursors.csv', index=False)
    if len(spikes) and len(baseline):
        summarize(spikes, baseline)
    else:
        print("Not enough data collected.")


if __name__ == "__main__":
    main()
