"""
Strategy registry.

Every strategy is a plain module exposing:
    NAME            display name shown in the UI
    TIMEFRAMES      (tf1, tf2) yfinance interval strings the strategy needs
    PARAM_SCHEMA    list of {key, label, min, max, default, help} dicts for
                     any parameters the user should be able to tune from the UI
    DEFAULT_PARAMS  dict of every param the strategy uses (tunable + fixed),
                     keyed the same as PARAM_SCHEMA entries plus internal constants
    backtest_symbol(df_tf1, df_tf2, params, start_date, end_date) -> list[dict]
                     every historical setup found, each with an 'outcome' of
                     'win' / 'loss' / 'pending'
    screen_symbol(df_tf1, df_tf2, current_price, params) -> dict | None
                     the current live/developing setup (if any) for daily screening

To add a new strategy: write a module implementing the interface above and
register it in STRATEGIES below. No changes needed in backtest.py, screener.py,
or a future scheduled-run script - they all look strategies up by key.
"""
from . import smart_money

STRATEGIES = {
    "smart_money": smart_money,
}


def list_strategies():
    """Return {key: display_name} for every registered strategy."""
    return {key: mod.NAME for key, mod in STRATEGIES.items()}


def get_strategy(key):
    return STRATEGIES[key]
