"""
Demand Zone (SQL Two-Pass) strategy: wraps the Postgres stored procedure
find_demand_zones_v2 (ported into this app's own Neon project, over views
that read the existing `prices` cache) instead of computing swing points/
zones in Python. The proc does a monthly push (HL->HH) search, then finds
daily impulse/FVG zones inside that push window, then refines them against
a matching weekly impulse candle.

Point-in-time correctness for backtesting: the proc's own out_current_price/
out_zone_status/out_pct_from_zone columns are always relative to the *latest*
row in daily_candles, regardless of the p_end_date passed in - they can't be
used to grade historical dates without leaking future price info. This
module never reads those three columns; zone touch/status is instead
computed locally against the actual historical (or live) OHLCV bars already
cached in `prices`.

Lookahead bias in zone *selection* (which push/zone counts as current) is
bounded, not eliminated: zones are recomputed once per calendar month
(using data through the end of the prior month only), and that snapshot is
used to grade every trading day within the following month. A true daily
recompute would need ~750 stored-proc calls per symbol for a 3-year
backtest (~2-4 minutes each) - monthly recompute is ~30x cheaper and matches
the proc's own monthly-swing foundation (the zone set structurally can't
change faster than that).
"""
import pandas as pd

from data_store import query_rows

NAME = "Demand Zone (SQL Two-Pass)"
TIMEFRAMES = ("1d",)  # daily only - zone geometry comes from the DB, not from dfs

MIN_HISTORY_MONTHS = 6  # skip months until this much history exists for the monthly swing search

PARAM_SCHEMA = [
    {"key": "MIN_PUSH_PCT", "label": "Min Push %", "min": 20, "max": 150, "default": 50,
     "help": "Minimum monthly HL->HH push size (%) for a zone set to qualify"},
    {"key": "REQUIRE_DECISIONAL", "label": "Decisional zones only", "type": "checkbox", "default": True,
     "help": "Skip the EXTREME (origin) zone, only use DECISIONAL (closer-in) zones"},
    {"key": "REQUIRE_WEEKLY_REFINED", "label": "Require weekly refinement", "type": "checkbox", "default": True,
     "help": "Only use zones confirmed by a matching weekly impulse candle"},
    {"key": "TARGET_PCT", "label": "Target %", "min": 0.5, "max": 5.0, "default": 1.5, "step": 0.1,
     "help": "Gain from entry price counted as a win, within the holding period"},
    {"key": "HOLD_DAYS", "label": "Holding Period (days)", "min": 3, "max": 10, "default": 5,
     "help": "Number of daily bars to track after entry before calling it pending"},
    {"key": "ENABLE_RISK_FILTER", "label": "Enable Max Risk % filter", "type": "checkbox", "default": True,
     "help": "When on, skips trades where the stop is wider than Max Risk % of entry"},
    {"key": "MAX_RISK_PCT", "label": "Max Risk %", "min": 0.5, "max": 5.0, "default": 1.5, "step": 0.1,
     "help": "Skip the trade if entry-to-stop distance exceeds this % of entry price"},
    {"key": "ENABLE_MIN_RR", "label": "Enable Min RR filter", "type": "checkbox", "default": False,
     "help": "When on, skips trades whose reward:risk ratio is below Min RR Ratio"},
    {"key": "MIN_RR_RATIO", "label": "Min RR Ratio", "min": 0.5, "max": 5.0, "default": 2.0, "step": 0.1,
     "help": "Skip the trade if reward:risk is below this (only applies when the filter above is enabled)"},
]

DEFAULT_PARAMS = {p["key"]: p["default"] for p in PARAM_SCHEMA}


def _symbol_of(df):
    return df.attrs.get('symbol') if df is not None else None


def _fetch_zones(symbol, floor_date, as_of_date, min_push_pct):
    return query_rows(
        "SELECT * FROM find_demand_zones_v2(%s, %s, %s, %s)",
        (symbol, floor_date.date(), as_of_date.date(), float(min_push_pct)),
    )


def _qualifying_zones(rows, params):
    out = []
    for r in rows:
        if params.get('REQUIRE_DECISIONAL', True) and r['out_zone_type'] != 'DECISIONAL':
            continue
        if params.get('REQUIRE_WEEKLY_REFINED', True) and not r['out_weekly_refined']:
            continue
        out.append(r)
    return out


def _zone_key(r):
    return (round(float(r['out_final_low']), 2), round(float(r['out_final_high']), 2))


def _dist_pct(price, zone_low, zone_high):
    """Signed-ish distance used for screener buckets: 0 inside, positive
    above the zone, negative-magnitude-as-positive below it (mirrors
    zone_daily's convention of only bucketing the "above, approaching"
    side into READY/APPROACHING)."""
    if zone_low <= price <= zone_high:
        return 0.0
    if price < zone_low:
        return None  # BELOW ZONE - not a "distance to entry" case
    return round(((price - zone_high) / zone_high) * 100, 1)


def backtest_symbol(dfs, params, start_date, end_date):
    """Every historical zone touch in [start_date, end_date], graded over a
    fixed daily holding period. Zones are recomputed once per calendar
    month using only data through the end of the prior month (see module
    docstring) - each zone is only ever traded once, on its first touch."""
    (df,) = dfs
    symbol = _symbol_of(df)
    if not symbol or df is None:
        return []

    df = df[(df.index >= start_date) & (df.index <= end_date)]
    if len(df) < 10:
        return []

    floor_date = df.index.min()
    hold_days = params['HOLD_DAYS']
    target_pct = params['TARGET_PCT']
    min_push_pct = params['MIN_PUSH_PCT']
    history_floor = floor_date + pd.DateOffset(months=MIN_HISTORY_MONTHS)

    months = pd.period_range(df.index.min(), df.index.max(), freq='M')
    snapshots = {}
    prev_month_end = None
    for month in months:
        if prev_month_end is not None and prev_month_end >= history_floor:
            rows = _fetch_zones(symbol, floor_date, prev_month_end, min_push_pct)
            snapshots[month] = _qualifying_zones(rows, params)
        else:
            snapshots[month] = []
        month_rows = df[df.index.to_period('M') == month]
        if len(month_rows):
            prev_month_end = month_rows.index.max()

    traded_zones = set()
    setups = []
    dates = df.index
    for i in range(len(dates) - 1):  # need a next-day open to enter on
        day = dates[i]
        zones = snapshots.get(day.to_period('M'), [])
        if not zones:
            continue
        day_low = df['Low'].iloc[i]

        for z in zones:
            key = _zone_key(z)
            if key in traded_zones:
                continue
            zone_low, zone_high = key
            if day_low > zone_high:
                continue  # not touched yet

            traded_zones.add(key)  # only ever trade a zone on its first touch

            entry_date = dates[i + 1]
            entry_price = round(float(df['Open'].iloc[i + 1]), 2)
            stop = zone_low
            target = round(entry_price * (1 + target_pct / 100), 2)
            risk = round(entry_price - stop, 2)
            if risk <= 0:
                continue  # entry gapped through the stop already

            risk_pct = round((risk / entry_price) * 100, 2)
            if params.get('ENABLE_RISK_FILTER', True) and risk_pct > params['MAX_RISK_PCT']:
                continue

            reward = round(target - entry_price, 2)
            rr_ratio = round(reward / risk, 2) if risk > 0 else None
            if params.get('ENABLE_MIN_RR') and rr_ratio is not None and rr_ratio < params['MIN_RR_RATIO']:
                continue

            window = df[df.index >= entry_date].iloc[:hold_days]
            if len(window) == 0:
                continue

            outcome, exit_price, exit_date = 'pending', None, None
            for k in range(len(window)):
                h, l = window['High'].iloc[k], window['Low'].iloc[k]
                if h >= target:
                    outcome, exit_price = 'win', target
                    exit_date = window.index[k].date(); break
                if l <= stop:
                    outcome, exit_price = 'loss', stop
                    exit_date = window.index[k].date(); break

            if outcome == 'pending':
                last_close = window['Close'].iloc[-1]
                outcome = 'pending_positive' if last_close > entry_price else 'pending_negative'

            setups.append({
                'push_date': str(z['out_hh_date']) if z.get('out_hh_date') else None,
                'push_low_date': str(z['out_hl_date']) if z.get('out_hl_date') else None,
                'push_high': float(z['out_hh_price']) if z.get('out_hh_price') is not None else None,
                'push_low': float(z['out_hl_price']) if z.get('out_hl_price') is not None else None,
                'push_pct': float(z['out_push_pct']) if z.get('out_push_pct') is not None else None,
                'zone_type': z['out_zone_type'],
                'zone_low': zone_low,
                'zone_high': zone_high,
                'weekly_refined': bool(z['out_weekly_refined']),
                'touch_date': str(day.date()),
                'entry_date': str(entry_date.date()),
                'entry_price': entry_price,
                'stop_loss': stop,
                'target': target,
                'risk': risk,
                'risk_pct': risk_pct,
                'reward': reward,
                'rr_ratio': rr_ratio,
                'max_high': round(window['High'].max(), 2),
                'min_low': round(window['Low'].min(), 2),
                'outcome': outcome,
                'exit_price': exit_price,
                'exit_date': str(exit_date) if exit_date else None,
            })
    return setups


def screen_symbol(dfs, current_price, params):
    """Live status for the nearest qualifying zone today. `dfs` is (df,)."""
    (df,) = dfs
    symbol = _symbol_of(df)
    if not symbol or df is None or len(df) < 10:
        return None

    floor_date = df.index.min()
    today = df.index.max()
    rows = _fetch_zones(symbol, floor_date, today, params['MIN_PUSH_PCT'])
    zones = _qualifying_zones(rows, params)
    if not zones:
        return None

    def _abs_dist(r):
        lo, hi = _zone_key(r)
        d = _dist_pct(current_price, lo, hi)
        if d is None:  # below zone - still need a sortable distance
            return (lo - current_price) / lo * 100 if lo else 1e9
        return d

    z = min(zones, key=_abs_dist)
    zone_low, zone_high = _zone_key(z)
    dist = _dist_pct(current_price, zone_low, zone_high)

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

    prev_low = df['Low'].iloc[-2] if len(df) >= 2 else None
    today_low = df['Low'].iloc[-1]
    just_touched_today = today_low <= zone_high and (prev_low is None or prev_low > zone_high)

    target_pct = params['TARGET_PCT']
    risk = round(zone_high - zone_low, 2)
    reward = round(zone_high * target_pct / 100, 2)
    rr = round(reward / risk, 2) if risk > 0 else None
    risk_pct = round((risk / zone_high) * 100, 2) if zone_high else None

    if just_touched_today:
        risk_ok = (not params.get('ENABLE_RISK_FILTER', True)
                   or (risk_pct is not None and risk_pct <= params['MAX_RISK_PCT']))
        rr_ok = (not params.get('ENABLE_MIN_RR')
                 or (rr is not None and rr >= params['MIN_RR_RATIO']))
        if risk_ok and rr_ok:
            status, emoji = 'ENTRY TOMORROW', '🎯'
        elif not risk_ok:
            status, emoji = 'ZONE TOO WIDE', '⚪'
        else:
            status, emoji = 'LOW RR', '⚪'

    push_high = float(z['out_hh_price']) if z.get('out_hh_price') is not None else None
    push_low = float(z['out_hl_price']) if z.get('out_hl_price') is not None else None
    push_pct = float(z['out_push_pct']) if z.get('out_push_pct') is not None else None
    fifty_pct = float(z['out_fifty_pct']) if z.get('out_fifty_pct') is not None else None

    retracement_pct = None
    if push_high is not None and push_low is not None and push_high != push_low:
        retracement_pct = round(((push_high - current_price) / (push_high - push_low)) * 100, 1)

    return {
        'status': status,
        'emoji': emoji,
        'current_price': current_price,
        'push_high': push_high,
        'push_low': push_low,
        'push_pct': round(push_pct, 1) if push_pct is not None else None,
        '50pct_level': fifty_pct,
        'retracement_pct': retracement_pct,
        'zone_low': zone_low,
        'zone_high': zone_high,
        'distance_pct': dist if dist is not None else 0.0,
        'rr_ratio': rr,
        # extras, safe to ignore in the generic display:
        'zone_type': z['out_zone_type'],
        'weekly_refined': bool(z['out_weekly_refined']),
    }
