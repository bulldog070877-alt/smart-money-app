"""
Strategy registry.

Every strategy is a plain module exposing:
    NAME            display name shown in the UI
    TIMEFRAMES      tuple of yfinance interval strings the strategy needs,
                     e.g. ("1mo", "1wk") or ("1mo", "1wk", "1d") - any length
    PARAM_SCHEMA    list of {key, label, min, max, default, help, step?} dicts
                     for any parameters the user should be able to tune from the UI
    DEFAULT_PARAMS  dict of every param the strategy uses (tunable + fixed),
                     keyed the same as PARAM_SCHEMA entries plus internal constants
    backtest_symbol(dfs, params, start_date, end_date) -> list[dict]
                     dfs is a tuple of DataFrames matching TIMEFRAMES order.
                     Returns every historical setup found, each with an
                     'outcome' of 'win' / 'loss' / 'pending' (or a strategy-
                     specific variant, e.g. 'pending_positive')
    screen_symbol(dfs, current_price, params) -> dict | None
                     the current live/developing setup (if any) for daily screening

To add a new strategy: write a module implementing the interface above and
register it in STRATEGIES below. No changes needed in backtest.py, screener.py,
or a future scheduled-run script - they all look strategies up by key.
"""
from . import smart_money
from . import zone_daily
from . import momentum_reversal
from . import demand_zone_sql

STRATEGIES = {
    "smart_money": smart_money,
    "zone_daily": zone_daily,
    "momentum_reversal": momentum_reversal,
    "demand_zone_sql": demand_zone_sql,
}


def list_strategies():
    """Return {key: display_name} for every registered strategy."""
    return {key: mod.NAME for key, mod in STRATEGIES.items()}


def get_strategy(key):
    return STRATEGIES[key]
