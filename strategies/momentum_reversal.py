"""
Momentum Reversal (Oversold Bounce) strategy.

Derived empirically (see scan_momentum_events.py / analyze_spike_precursors.py):
fast >=5%/5-day spikes were preceded by a recognizable state - a volatile
stock that had drifted toward the lower part of its recent range, on a day
that gapped down on elevated volume, then snapped back. This strategy turns
that precursor state into a forward-testable entry rule:

  Signal (evaluated at the close of day D, all conditions known then):
    - 20-day daily-return volatility >= MIN_VOLATILITY
    - close sits in the lower MAX_POS_IN_RANGE of the 20-day range
    - day D gapped down by at least abs(MAX_GAP_PCT) (non-positive gap)
    - day D volume >= MIN_VOL_RATIO x its 20-day average

  Entry:  Open of day D+1 (so the screener can flag a name a day ahead).
  Target: entry x (1 + TARGET_PCT/100), a win if High reaches it within
          MAX_DAYS bars. Optional STOP_PCT below entry ends it as a loss.
  If neither triggers by MAX_DAYS: pending_positive / pending_negative
  depending on where the close finished vs entry.

Positions don't overlap: after a signal, the scan resumes only after that
trade's MAX_DAYS window closes, so stats aren't inflated by re-signalling
the same underlying move on consecutive days.
"""
import numpy as np
import pandas as pd

NAME = "Momentum Reversal (Oversold Bounce)"
TIMEFRAMES = ("1d",)  # daily only

LOOKBACK = 20

PARAM_SCHEMA = [
    {"key": "TARGET_PCT", "label": "Target %", "min": 1.0, "max": 10.0, "default": 5.0, "step": 0.5,
     "help": "Gain from entry counted as a win, within the holding period"},
    {"key": "MAX_DAYS", "label": "Holding Period (days)", "min": 3, "max": 12, "default": 5,
     "help": "Trading days to monitor after entry (tune 5 / 7 / 9 here)"},
    {"key": "MIN_VOLATILITY", "label": "Min Prior Volatility %", "min": 0.5, "max": 4.0, "default": 1.5, "step": 0.1,
     "help": "20-day daily-return std dev the stock must exceed - only volatile names"},
    {"key": "MAX_POS_IN_RANGE", "label": "Max Position in Range", "min": 0.1, "max": 1.0, "default": 0.5, "step": 0.05,
     "help": "Close must sit in the lower part of its 20-day range (0=at low, 1=at high)"},
    {"key": "MAX_GAP_PCT", "label": "Max Signal-Day Gap %", "min": -3.0, "max": 1.0, "default": 0.0, "step": 0.25,
     "help": "Signal day's gap vs prior close must be at or below this (0 = gapped down or flat)"},
    {"key": "MIN_VOL_RATIO", "label": "Min Volume Ratio", "min": 0.5, "max": 3.0, "default": 1.0, "step": 0.1,
     "help": "Signal-day volume vs its 20-day average"},
    {"key": "ENABLE_STOP", "label": "Enable stop loss", "type": "checkbox", "default": False,
     "help": "When on, a drop of Stop % below entry ends the trade as a loss"},
    {"key": "STOP_PCT", "label": "Stop %", "min": 1.0, "max": 15.0, "default": 5.0, "step": 0.5,
     "help": "How far below entry the stop sits (only applies when the stop is enabled)"},
    {"key": "ENABLE_MIN_RR", "label": "Enable Min RR filter", "type": "checkbox", "default": False,
     "help": "When on, skips trades whose reward:risk ratio is below Min RR Ratio "
             "(only meaningful with the stop loss enabled, since risk is undefined without one)"},
    {"key": "MIN_RR_RATIO", "label": "Min RR Ratio", "min": 0.5, "max": 5.0, "default": 2.0, "step": 0.1,
     "help": "Skip the trade if reward:risk is below this (only applies when the filter above is enabled)"},
]

DEFAULT_PARAMS = {
    "LOOKBACK": LOOKBACK,
    **{p["key"]: p["default"] for p in PARAM_SCHEMA},
}


def _signal_at(df, i, params):
    """Is day i (0-indexed) a valid signal day? All inputs are known at the
    close of day i. Returns a dict of the signal's measured features, or None."""
    lookback = params['LOOKBACK']
    if i < lookback + 1:
        return None
    prior = df.iloc[i - lookback:i]          # the lookback days before day i
    day = df.iloc[i]
    prev = df.iloc[i - 1]

    prior_lo = prior['Low'].min()
    prior_hi = prior['High'].max()
    rng = prior_hi - prior_lo
    if rng <= 0 or prior_lo <= 0 or prev['Close'] <= 0:
        return None

    rets = prior['Close'].pct_change().dropna() * 100
    volatility = rets.std()
    pos_in_range = (day['Close'] - prior_lo) / rng
    gap_pct = (day['Open'] - prev['Close']) / prev['Close'] * 100
    vol_mean = prior['Volume'].mean()
    vol_ratio = day['Volume'] / vol_mean if vol_mean else 0.0

    if volatility < params['MIN_VOLATILITY']:
        return None
    if pos_in_range > params['MAX_POS_IN_RANGE']:
        return None
    if gap_pct > params['MAX_GAP_PCT']:
        return None
    if vol_ratio < params['MIN_VOL_RATIO']:
        return None

    return {
        'volatility': round(float(volatility), 2),
        'pos_in_range': round(float(pos_in_range), 2),
        'gap_pct': round(float(gap_pct), 2),
        'vol_ratio': round(float(vol_ratio), 2),
    }


def _grade(df, entry_i, entry_price, params):
    """Grade a trade entered at Open of day entry_i over MAX_DAYS bars."""
    max_days = params['MAX_DAYS']
    target = round(entry_price * (1 + params['TARGET_PCT'] / 100), 2)
    stop = round(entry_price * (1 - params['STOP_PCT'] / 100), 2) if params.get('ENABLE_STOP') else None

    window = df.iloc[entry_i:entry_i + max_days]
    if len(window) == 0:
        return None

    outcome, exit_price, exit_date = 'pending', None, None
    for k in range(len(window)):
        hi, lo = window['High'].iloc[k], window['Low'].iloc[k]
        if hi >= target:
            outcome, exit_price = 'win', target
            exit_date = window.index[k].date(); break
        if stop is not None and lo <= stop:
            outcome, exit_price = 'loss', stop
            exit_date = window.index[k].date(); break

    if outcome == 'pending':
        last_close = window['Close'].iloc[-1]
        outcome = 'pending_positive' if last_close > entry_price else 'pending_negative'

    max_high = round(float(window['High'].max()), 2)
    min_low = round(float(window['Low'].min()), 2)
    return {
        'target': target, 'stop_loss': stop, 'outcome': outcome,
        'exit_price': exit_price, 'exit_date': str(exit_date) if exit_date else None,
        'max_high': max_high, 'min_low': min_low,
        'max_gain_pct': round((max_high - entry_price) / entry_price * 100, 2),
    }


def backtest_symbol(dfs, params, start_date, end_date):
    (df,) = dfs
    df = df[(df.index >= start_date) & (df.index <= end_date)]
    if len(df) < params['LOOKBACK'] + params['MAX_DAYS'] + 2:
        return []

    setups = []
    i = params['LOOKBACK'] + 1
    n = len(df)
    while i < n - 1:
        sig = _signal_at(df, i, params)
        if sig is None:
            i += 1
            continue

        entry_i = i + 1                       # enter next day's open
        if entry_i >= n:
            break
        entry_price = round(float(df['Open'].iloc[entry_i]), 2)
        stop = round(entry_price * (1 - params['STOP_PCT'] / 100), 2) if params.get('ENABLE_STOP') else None
        risk = round(entry_price - stop, 2) if stop is not None else None

        graded = _grade(df, entry_i, entry_price, params)
        if graded is None:
            i += 1
            continue

        reward = round(graded['target'] - entry_price, 2)
        rr_ratio = round(reward / risk, 2) if risk and risk > 0 else None
        if params.get('ENABLE_MIN_RR') and rr_ratio is not None and rr_ratio < params['MIN_RR_RATIO']:
            i += 1  # reward:risk too thin - skip without consuming the holding window
            continue

        setups.append({
            'signal_date': str(df.index[i].date()),
            'entry_date': str(df.index[entry_i].date()),
            'entry_price': entry_price,
            'prior_volatility': sig['volatility'],
            'pos_in_range': sig['pos_in_range'],
            'signal_gap_pct': sig['gap_pct'],
            'volume_ratio': sig['vol_ratio'],
            'target': graded['target'],
            'stop_loss': stop,
            'risk': risk,
            'reward': reward,
            'rr_ratio': rr_ratio,
            'max_high': graded['max_high'],
            'min_low': graded['min_low'],
            'max_gain_pct': graded['max_gain_pct'],
            'outcome': graded['outcome'],
            'exit_price': graded['exit_price'],
            'exit_date': graded['exit_date'],
        })
        # no overlapping positions: resume after this trade's window closes
        i = entry_i + params['MAX_DAYS']
    return setups


def screen_symbol(dfs, current_price, params):
    """Flag a name whose most recent bar is a signal - i.e. a candidate to
    enter tomorrow. Returns fields mapped onto the shared screener display
    contract (target->push_high, stop/entry->push_low, entry zone->zone_*)."""
    (df,) = dfs
    if df is None or len(df) < params['LOOKBACK'] + 2:
        return None

    i = len(df) - 1                           # the latest completed bar
    sig = _signal_at(df, i, params)
    if sig is None:
        return None

    entry_est = current_price                 # tomorrow's open ~ today's close
    target = round(entry_est * (1 + params['TARGET_PCT'] / 100), 2)
    stop = round(entry_est * (1 - params['STOP_PCT'] / 100), 2) if params.get('ENABLE_STOP') else None
    risk = round(entry_est - stop, 2) if stop else None
    reward = round(target - entry_est, 2)
    rr = round(reward / risk, 2) if risk and risk > 0 else None

    if params.get('ENABLE_MIN_RR') and rr is not None and rr < params['MIN_RR_RATIO']:
        return None  # reward:risk too thin - not an actionable signal

    return {
        'status': 'ENTRY TOMORROW',
        'emoji': '🎯',
        'current_price': current_price,
        # mapped onto the shared screener display fields:
        'push_high': target,                  # "target"
        'push_low': stop if stop else entry_est,   # "stop / entry floor"
        'push_pct': params['TARGET_PCT'],
        '50pct_level': entry_est,
        'retracement_pct': round(sig['pos_in_range'] * 100, 1),
        'zone_low': round(entry_est * 0.999, 2),
        'zone_high': round(entry_est * 1.001, 2),
        'distance_pct': 0.0,
        'rr_ratio': rr,
        # momentum-specific extras (safe to ignore in the generic display):
        'prior_volatility': sig['volatility'],
        'pos_in_range': sig['pos_in_range'],
        'signal_gap_pct': sig['gap_pct'],
        'volume_ratio': sig['vol_ratio'],
    }
