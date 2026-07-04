"""
Zone Daily strategy: reuses the Smart Money push/CHoCH/demand-zone pipeline
(monthly push, weekly CHoCH + zone), then tightens the zone to the
inducement candle's body (dropping wick noise) and switches to daily bars
for a precise entry trigger and a fixed-length holding period, instead of
the open-ended monthly retracement/outcome tracking used by smart_money.

Entry rule: the first daily bar whose Low reaches the tightened zone's
upper edge triggers a buy at the *next* day's Open. Stop-loss is the
tightened zone's low; target is a fixed % gain from entry. If neither is
hit within the holding period, the setup is marked pending (positive/
negative depending on whether price is above or below entry at the end
of the window).
"""
import pandas as pd

from strategies.smart_money import find_swing_points, find_main_push, find_choch, find_demand_zone

NAME = "Zone Daily (Weekly Zone + Daily Entry)"
TIMEFRAMES = ("1mo", "1wk", "1d")  # (tf1=monthly, tf2=weekly, tf3=daily)

PARAM_SCHEMA = [
    {"key": "MIN_PUSH_PCT", "label": "Min Push %", "min": 20, "max": 60, "default": 40,
     "help": "Minimum Main Push size to qualify"},
    {"key": "TARGET_PCT", "label": "Target %", "min": 0.5, "max": 5.0, "default": 1.5, "step": 0.1,
     "help": "Gain from entry price counted as a win, within the holding period"},
    {"key": "HOLD_DAYS", "label": "Holding Period (days)", "min": 3, "max": 10, "default": 5,
     "help": "Number of daily bars to track after entry before calling it pending"},
    {"key": "MAX_RISK_PCT", "label": "Max Risk %", "min": 0.5, "max": 5.0, "default": 1.5, "step": 0.1,
     "help": "Skip the trade if entry-to-stop distance exceeds this % of entry price"},
]

DEFAULT_PARAMS = {
    "SWING_LENGTH": 3,
    "EQUAL_LOW_TOL": 1.5,
    "MIN_CONSOL": 4,
    "MAX_CONSOL_RANGE": 15,
    **{p["key"]: p["default"] for p in PARAM_SCHEMA},
}


def _tighten_zone(zone):
    """Narrow the zone to the inducement candle's body (open/close),
    dropping wick noise. Always a subset of the original zone bounds."""
    lo = min(zone['inducement_open'], zone['inducement_close'])
    hi = max(zone['inducement_open'], zone['inducement_close'])
    return round(lo, 2), round(hi, 2)


def _find_daily_touch(df_tf3, after_date, zone_high):
    """First daily bar after `after_date` whose Low reaches into the zone."""
    df_after = df_tf3[df_tf3.index > after_date]
    for i in range(len(df_after)):
        if df_after['Low'].iloc[i] <= zone_high:
            return i, df_after
    return None, df_after


def _qualifying_push_and_zone(df_tf1, df_tf2, params):
    """Yield (push, zone) pairs, most recent push first, for pushes that
    have a confirmed CHoCH and demand zone."""
    highs, lows = find_swing_points(df_tf1, params)
    pushes = find_main_push(df_tf1, highs, lows, params)
    for push in reversed(pushes):
        choch = find_choch(df_tf2, push)
        if choch is None:
            continue
        zone = find_demand_zone(df_tf2, push, params)
        if zone is None:
            continue
        yield push, zone


def backtest_symbol(dfs, params, start_date, end_date):
    """Every historical setup in [start_date, end_date] resolved over a
    fixed daily holding period. `dfs` is (df_tf1, df_tf2, df_tf3) matching
    TIMEFRAMES order."""
    df_tf1, df_tf2, df_tf3 = dfs
    df_tf1 = df_tf1[(df_tf1.index >= start_date) & (df_tf1.index <= end_date)]
    df_tf2 = df_tf2[(df_tf2.index >= start_date) & (df_tf2.index <= end_date)]
    df_tf3 = df_tf3[(df_tf3.index >= start_date) & (df_tf3.index <= end_date)]
    if len(df_tf1) < 10 or len(df_tf2) < 10 or len(df_tf3) < 10:
        return []

    hold_days = params['HOLD_DAYS']
    target_pct = params['TARGET_PCT']

    # chronological order for backtesting (oldest push first)
    highs, lows = find_swing_points(df_tf1, params)
    pushes = find_main_push(df_tf1, highs, lows, params)

    setups = []
    for push in pushes:
        choch = find_choch(df_tf2, push)
        if choch is None: continue
        zone = find_demand_zone(df_tf2, push, params)
        if zone is None: continue

        zone_low, zone_high = _tighten_zone(zone)

        touch_idx, df_after_hh = _find_daily_touch(df_tf3, push['hh_date'], zone_high)
        if touch_idx is None or touch_idx + 1 >= len(df_after_hh):
            continue  # zone never touched in range, or no next bar to enter on

        touch_date = df_after_hh.index[touch_idx]
        entry_date = df_after_hh.index[touch_idx + 1]
        entry_price = round(df_after_hh['Open'].iloc[touch_idx + 1], 2)
        stop = zone_low
        target = round(entry_price * (1 + target_pct / 100), 2)

        risk = round(entry_price - stop, 2)
        if risk <= 0:
            continue  # entry gapped through the stop already

        risk_pct = round((risk / entry_price) * 100, 2)
        if risk_pct > params['MAX_RISK_PCT']:
            continue  # stop too wide relative to entry - skip rather than take a poor R:R trade

        window = df_tf3[df_tf3.index >= entry_date].iloc[:hold_days]
        if len(window) == 0:
            continue

        outcome, exit_price, exit_date = 'pending', None, None
        for i in range(len(window)):
            h, l = window['High'].iloc[i], window['Low'].iloc[i]
            if h >= target:
                outcome, exit_price = 'win', target
                exit_date = window.index[i].date(); break
            if l <= stop:
                outcome, exit_price = 'loss', stop
                exit_date = window.index[i].date(); break

        if outcome == 'pending':
            last_close = window['Close'].iloc[-1]
            outcome = 'pending_positive' if last_close > entry_price else 'pending_negative'

        reward = round(target - entry_price, 2)
        setups.append({
            'push_date': str(push['hh_date'].date()),
            'push_low_date': str(push['hl_date'].date()),
            'push_high': push['hh_price'],
            'push_low': push['hl_price'],
            'push_pct': push['push_pct'],
            'choch_date': str(choch['date'].date()),
            'zone_type': zone['zone_type'],
            'zone_low': zone_low,
            'zone_high': zone_high,
            'zone_low_wide': zone['zone_low'],
            'zone_high_wide': zone['zone_high'],
            'touch_date': str(touch_date.date()),
            'entry_date': str(entry_date.date()),
            'entry_price': entry_price,
            'stop_loss': stop,
            'target': target,
            'risk': risk,
            'risk_pct': risk_pct,
            'reward': reward,
            'rr_ratio': round(reward / risk, 2) if risk > 0 else None,
            'max_high': round(window['High'].max(), 2),
            'min_low': round(window['Low'].min(), 2),
            'outcome': outcome,
            'exit_price': exit_price,
            'exit_date': str(exit_date) if exit_date else None,
        })
    return setups


def screen_symbol(dfs, current_price, params):
    """Live status for the most recent push/zone: distance-based status if
    the zone hasn't been touched yet, or an ENTRY TOMORROW flag if today's
    daily bar was the first touch. `dfs` is (df_tf1, df_tf2, df_tf3)."""
    df_tf1, df_tf2, df_tf3 = dfs

    valid_push = valid_zone = None
    for push, zone in _qualifying_push_and_zone(df_tf1, df_tf2, params):
        push_age = (pd.Timestamp.now() - push['hh_date']).days
        if push_age > 365 * 3:
            continue
        valid_push, valid_zone = push, zone
        break

    if valid_push is None:
        return None

    zone_low, zone_high = _tighten_zone(valid_zone)
    touch_idx, df_after_hh = _find_daily_touch(df_tf3, valid_push['hh_date'], zone_high)
    just_touched_today = touch_idx is not None and touch_idx == len(df_after_hh) - 1

    dist = round(((current_price - zone_high) / zone_high) * 100, 1) if zone_high else None
    if zone_low <= current_price <= zone_high:
        status, emoji = 'INSIDE ZONE', '🟢'
    elif dist is not None and 0 < dist <= 5:
        status, emoji = 'READY', '🟡'
    elif dist is not None and 0 < dist <= 15:
        status, emoji = 'APPROACHING', '🟠'
    elif current_price < zone_low:
        status, emoji = 'BELOW ZONE', '❌'
    else:
        status, emoji = 'WATCHING', '🔴'

    target_pct = params['TARGET_PCT']
    risk = round(zone_high - zone_low, 2)
    reward = round(zone_high * target_pct / 100, 2)
    rr = round(reward / risk, 2) if risk > 0 else None
    risk_pct = round((risk / zone_high) * 100, 2) if zone_high else None

    if just_touched_today:
        # Mirror backtest_symbol's Max Risk % filter - don't flag as
        # actionable if the backtester would have skipped this trade.
        if risk_pct is not None and risk_pct <= params['MAX_RISK_PCT']:
            status, emoji = 'ENTRY TOMORROW', '🎯'
        else:
            status, emoji = 'ZONE TOO WIDE', '⚪'

    retracement_pct = round(((valid_push['hh_price'] - current_price) /
                             (valid_push['hh_price'] - valid_push['hl_price'])) * 100, 1)

    return {
        'status': status,
        'emoji': emoji,
        'current_price': current_price,
        'push_high': valid_push['hh_price'],
        'push_low': valid_push['hl_price'],
        'push_pct': round(valid_push['push_pct'], 1),
        '50pct_level': valid_push['50pct_level'],
        'retracement_pct': retracement_pct,
        'zone_low': zone_low,
        'zone_high': zone_high,
        'distance_pct': dist,
        'rr_ratio': rr,
    }
