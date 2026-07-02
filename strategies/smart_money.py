"""
Smart Money strategy: Main Push -> CHoCH -> Retracement -> Demand Zone.

Pure pandas/numpy logic, no Streamlit dependency, so this can run both from
the interactive app (backtest.py, screener.py) and later from a headless
scheduled script by importing `strategies.get_strategy("smart_money")`.
"""
import pandas as pd

NAME = "Smart Money (Push + CHoCH + Demand Zone)"
TIMEFRAMES = ("1mo", "1wk")  # (tf1, tf2)

PARAM_SCHEMA = [
    {"key": "MIN_PUSH_PCT", "label": "Min Push %", "min": 20, "max": 60, "default": 40,
     "help": "Minimum Main Push size to qualify"},
    {"key": "MIN_RETRACEMENT", "label": "Min Retracement %", "min": 40, "max": 60, "default": 50,
     "help": "Minimum pullback before looking for entry"},
]

DEFAULT_PARAMS = {
    "SWING_LENGTH": 3,
    "MAX_RETRACEMENT": 95,
    "EQUAL_LOW_TOL": 1.5,
    "MIN_CONSOL": 4,
    "MAX_CONSOL_RANGE": 15,
    **{p["key"]: p["default"] for p in PARAM_SCHEMA},
}


def find_swing_points(df, params):
    sl = params['SWING_LENGTH']
    highs, lows = [], []
    for i in range(sl, len(df) - sl):
        ch, cl = df['High'].iloc[i], df['Low'].iloc[i]
        if ch > df['High'].iloc[i-sl:i].max() and ch > df['High'].iloc[i+1:i+sl+1].max():
            highs.append({'date': df.index[i], 'price': ch, 'type': 'HH'})
        if cl < df['Low'].iloc[i-sl:i].min() and cl < df['Low'].iloc[i+1:i+sl+1].min():
            lows.append({'date': df.index[i], 'price': cl, 'type': 'HL'})
    for i in range(1, len(highs)):
        highs[i]['type'] = 'HH' if highs[i]['price'] > highs[i-1]['price'] else 'LH'
    for i in range(1, len(lows)):
        lows[i]['type'] = 'HL' if lows[i]['price'] > lows[i-1]['price'] else 'LL'
    return highs, lows


def find_main_push(df, highs, lows, params):
    min_push_pct = params['MIN_PUSH_PCT']
    pushes = []
    for hh in [h for h in highs if h['type'] == 'HH']:
        prev_lows = [l for l in lows if l['date'] < hh['date']]
        if not prev_lows: continue
        valid_hl = None
        for j in range(len(prev_lows)-1, -1, -1):
            candidate = prev_lows[j]
            if not [l for l in prev_lows if l['date'] > candidate['date'] and l['price'] < candidate['price']]:
                valid_hl = candidate
                break
        if valid_hl is None: continue
        push_size = hh['price'] - valid_hl['price']
        push_pct = (push_size / valid_hl['price']) * 100
        if push_pct >= min_push_pct:
            pushes.append({
                'hh_date': hh['date'], 'hh_price': round(hh['price'], 2),
                'hl_date': valid_hl['date'], 'hl_price': round(valid_hl['price'], 2),
                'push_size': round(push_size, 2), 'push_pct': round(push_pct, 2),
                '50pct_level': round(valid_hl['price'] + push_size * 0.5, 2)
            })
    return pushes


def find_choch(df_tf2, push):
    df_after = df_tf2[df_tf2.index > push['hh_date']].copy()
    if len(df_after) < 4: return None
    lows = []
    for i in range(len(df_after)):
        lows.append(df_after['Low'].iloc[i])
        if len(lows) >= 3 and lows[-1] < lows[-2] < lows[-3] and lows[-1] > push['hl_price']:
            return {'date': df_after.index[i], 'price': round(lows[-1], 2)}
    return None


def check_retracement(df_tf1, push, choch_date, params):
    df_after = df_tf1[df_tf1.index > choch_date].copy()
    hh, hl, pr = push['hh_price'], push['hl_price'], push['hh_price'] - push['hl_price']
    for i in range(len(df_after)):
        cl = df_after['Low'].iloc[i]
        ret = ((hh - cl) / pr) * 100
        if cl < hl or ret > params['MAX_RETRACEMENT']: return None
        if ret >= params['MIN_RETRACEMENT']:
            return {'date': df_after.index[i], 'price': round(cl, 2), 'retracement_pct': round(ret, 2)}
    return None


def find_demand_zone(df_tf2, push, params):
    df_zone = df_tf2[(df_tf2.index >= push['hl_date']) & (df_tf2.index <= push['hh_date'])].copy()
    if len(df_zone) < 8: return None
    fifty_pct, hl_price = push['50pct_level'], push['hl_price']
    min_c, max_r = params['MIN_CONSOL'], params['MAX_CONSOL_RANGE']

    demand_zones = []
    for i in range(len(df_zone) - min_c + 1):
        window = df_zone.iloc[i:i+min_c]
        wh, wl = window['High'].max(), window['Low'].min()
        if ((wh - wl) / wl) * 100 > max_r: continue

        # Find equal lows
        groups = []
        for j in range(len(window)):
            cl = window['Low'].iloc[j]
            matched = False
            for g in groups:
                if abs(cl - g['ref']) / g['ref'] * 100 <= params['EQUAL_LOW_TOL']:
                    g['count'] += 1; matched = True; break
            if not matched: groups.append({'ref': cl, 'count': 1})
        if not [g for g in groups if g['count'] >= 2]: continue

        eq_level = min(g['ref'] for g in groups if g['count'] >= 2)
        consol_end = window.index[-1]

        # Find inducement
        df_after_consol = df_tf2[df_tf2.index >= consol_end].copy()
        inducement = None
        for k in range(len(df_after_consol)):
            cl, ch = df_after_consol['Low'].iloc[k], df_after_consol['High'].iloc[k]
            if cl < eq_level and (ch - cl) > 0:
                inducement = {'date': df_after_consol.index[k], 'low': round(cl, 2), 'high': round(ch, 2)}
                break
        if inducement is None: continue

        # Find impulse
        df_after_ind = df_tf2[df_tf2.index > inducement['date']].copy()
        impulse = None
        for k in range(min(2, len(df_after_ind))):
            o, c, h, l = df_after_ind['Open'].iloc[k], df_after_ind['Close'].iloc[k], df_after_ind['High'].iloc[k], df_after_ind['Low'].iloc[k]
            cr = h - l
            if c > o and cr > 0 and ((c - o) / cr) * 100 >= 50:
                impulse = {'date': df_after_ind.index[k], 'candles': k + 1}
                break
        if impulse is None: continue

        zone_low, zone_high = inducement['low'], inducement['high']
        if impulse['candles'] == 2:
            df_between = df_tf2[(df_tf2.index > inducement['date']) & (df_tf2.index < impulse['date'])]
            if len(df_between) > 0:
                zone_high = max(zone_high, df_between['High'].iloc[0])

        if zone_low > fifty_pct: continue

        # Freshness check
        fresh = True
        df_check = df_tf2[(df_tf2.index > impulse['date']) & (df_tf2.index <= push['hh_date'])].copy()
        for k in range(len(df_check)):
            if df_check['Low'].iloc[k] <= zone_high:
                fresh = False; break
        if not fresh: continue

        zone_type = 'extreme' if inducement['low'] < hl_price else 'decisional'
        zone_width = round(((zone_high - zone_low) / zone_low) * 100, 2)
        demand_zones.append({
            'zone_type': zone_type, 'zone_low': round(zone_low, 2),
            'zone_high': round(zone_high, 2), 'zone_width_pct': zone_width,
            'inducement_date': inducement['date'], 'inducement_low': inducement['low']
        })

    if not demand_zones: return None
    decisional = [z for z in demand_zones if z['zone_type'] == 'decisional']
    extreme = [z for z in demand_zones if z['zone_type'] == 'extreme']
    return decisional[0] if decisional else extreme[0]


def track_outcome(df_tf1, push, retracement):
    if retracement is None: return None
    df_after = df_tf1[df_tf1.index > retracement['date']].copy()
    if len(df_after) == 0: return None
    entry, stop, target = retracement['price'], push['hl_price'], push['hh_price']
    risk, reward = entry - stop, target - entry
    if risk <= 0: return None
    rr = round(reward / risk, 2)
    outcome, exit_price, exit_date = 'pending', None, None
    for i in range(len(df_after)):
        h, l = df_after['High'].iloc[i], df_after['Low'].iloc[i]
        if h >= push['hh_price']:
            outcome, exit_price = 'win', push['hh_price']
            exit_date = df_after.index[i].date(); break
        if l <= stop:
            outcome, exit_price = 'loss', stop
            exit_date = df_after.index[i].date(); break
    return {'outcome': outcome, 'entry_price': round(entry, 2), 'stop_loss': round(stop, 2),
            'target': round(target, 2), 'risk': round(risk, 2), 'reward': round(reward, 2),
            'rr_ratio': rr, 'exit_price': exit_price, 'exit_date': exit_date}


def backtest_symbol(df_tf1, df_tf2, params, start_date, end_date):
    """Every historical setup in [start_date, end_date], each tagged with a
    resolved outcome of 'win' / 'loss' / 'pending'."""
    df_tf1 = df_tf1[(df_tf1.index >= start_date) & (df_tf1.index <= end_date)]
    df_tf2 = df_tf2[(df_tf2.index >= start_date) & (df_tf2.index <= end_date)]
    if len(df_tf1) < 10 or len(df_tf2) < 10: return []

    highs, lows = find_swing_points(df_tf1, params)
    pushes = find_main_push(df_tf1, highs, lows, params)
    setups = []
    for push in pushes:
        choch = find_choch(df_tf2, push)
        if choch is None: continue
        retracement = check_retracement(df_tf1, push, choch['date'], params)
        if retracement is None: continue
        demand_zone = find_demand_zone(df_tf2, push, params)
        if demand_zone is None: continue
        outcome = track_outcome(df_tf1, push, retracement)
        if outcome is None: continue
        setups.append({
            'push_date': str(push['hh_date'].date()),
            'push_high': push['hh_price'],
            'push_low': push['hl_price'],
            'push_pct': push['push_pct'],
            '50pct_level': push['50pct_level'],
            'retracement_pct': retracement['retracement_pct'],
            'zone_type': demand_zone['zone_type'],
            'zone_low': demand_zone['zone_low'],
            'zone_high': demand_zone['zone_high'],
            'zone_width_pct': demand_zone['zone_width_pct'],
            'entry_price': outcome['entry_price'],
            'stop_loss': outcome['stop_loss'],
            'target': outcome['target'],
            'risk': outcome['risk'],
            'reward': outcome['reward'],
            'rr_ratio': outcome['rr_ratio'],
            'outcome': outcome['outcome'],
            'exit_price': outcome['exit_price'],
            'exit_date': str(outcome['exit_date']) if outcome['exit_date'] else None,
        })
    return setups


def _quick_zone(df_tf2, push):
    """Fast zone estimate for a push that hasn't fully retraced/confirmed
    yet, so find_demand_zone's strict CHoCH+impulse+freshness pipeline
    can't be used - this is a rougher approximation for live monitoring."""
    df_zone = df_tf2[
        (df_tf2.index >= push['hh_date'] - pd.Timedelta(weeks=52)) &
        (df_tf2.index <= push['hh_date'])
    ]
    zone_low, zone_high = None, None
    if len(df_zone) >= 8:
        for i in range(4, len(df_zone) - 4):
            window = df_zone.iloc[max(0, i - 4):i]
            wh, wl = window['High'].max(), window['Low'].min()
            if ((wh - wl) / wl) * 100 <= 15 and wl <= push['50pct_level']:
                zone_low, zone_high = round(wl, 2), round(wh, 2)
    return zone_low, zone_high


def screen_symbol(df_tf1, df_tf2, current_price, params):
    """The most recent still-developing push (not yet broken out, within
    the last 3 years) and its live status relative to current price."""
    highs, lows = find_swing_points(df_tf1, params)
    pushes = find_main_push(df_tf1, highs, lows, params)  # chronological order

    valid_push = None
    for push in reversed(pushes):
        if current_price >= push['hh_price']:
            continue
        push_age = (pd.Timestamp.now() - push['hh_date']).days
        if push_age > 365 * 3:
            continue
        valid_push = push
        break
    if valid_push is None:
        return None

    zone_low, zone_high = _quick_zone(df_tf2, valid_push)

    retracement_pct = round(((valid_push['hh_price'] - current_price) /
                             (valid_push['hh_price'] - valid_push['hl_price'])) * 100, 1)

    if zone_high and zone_low:
        dist = round(((current_price - zone_high) / zone_high) * 100, 1)
        if zone_low <= current_price <= zone_high:
            status, emoji = 'INSIDE ZONE', '🟢'
        elif 0 < dist <= 5:
            status, emoji = 'READY', '🟡'
        elif 0 < dist <= 15:
            status, emoji = 'APPROACHING', '🟠'
        elif current_price < zone_low:
            status, emoji = 'BELOW ZONE', '❌'
        else:
            status, emoji = 'WATCHING', '🔴'
    else:
        dist = None
        status, emoji = 'NO ZONE', '⚪'

    rr = None
    if zone_high and zone_low:
        entry, stop, target = zone_high, valid_push['hl_price'], valid_push['hh_price']
        risk = entry - stop
        if risk > 0:
            rr = round((target - entry) / risk, 2)

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
