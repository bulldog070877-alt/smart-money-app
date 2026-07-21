import streamlit as st
import pandas as pd
from datetime import datetime

from data_store import get_history, DEFAULT_HISTORY_YEARS
from market_universe import SP500_TICKERS, NIFTY500_TICKERS
from strategies import list_strategies, get_strategy

# Columns shown in the results table, in preference order - only the ones
# actually present for the strategy that produced `df` are used, since each
# strategy's setup dict has different fields (e.g. Momentum Reversal has no
# push/zone columns at all).
_PREFERRED_COLUMNS = [
    'push_date', 'signal_date', 'push_pct', 'zone_type', 'zone_low', 'zone_high',
    'entry_date', 'entry_price', 'stop_loss', 'target', 'rr_ratio',
]

_OUTCOME_LABELS = {
    'win': '✅ Win', 'loss': '❌ Loss', 'pending': '⏳ Pending',
    'pending_positive': '🟡 Pending (+)', 'pending_negative': '🟠 Pending (-)',
}


def _display_columns(df, extra=()):
    return ['symbol', 'sector'] + [c for c in _PREFERRED_COLUMNS if c in df.columns] + list(extra) + ['outcome']


OPTIMISED_UNIVERSE = {
    'Consumer Staples': ['COST', 'WMT', 'MCD', 'PG', 'ADM', 'EL', 'MO', 'KO', 'PEP', 'CL'],
    'Industrials': ['ITW', 'DOV', 'HON', 'GE', 'CAT', 'DE', 'MMM', 'EMR', 'ETN'],
    'Communication Services': ['GOOGL', 'NFLX', 'META', 'DIS'],
    'Financials': ['MCO', 'AMP', 'JPM', 'GS', 'MA', 'V', 'MS', 'BLK', 'SPGI'],
    'Health Care': ['STE', 'ABBV', 'UNH', 'JNJ', 'TMO', 'ABT', 'DHR'],
    'Information Technology': ['ADSK', 'AAPL', 'MSFT', 'ADBE', 'QCOM', 'NVDA'],
    'Consumer Discretionary': ['ORLY', 'SBUX', 'ROST', 'HD', 'AMZN', 'LOW', 'TJX'],
    'Real Estate': ['O', 'IRM', 'PLD', 'AMT'],
}

def fetch_data(symbol, interval):
    try:
        df = get_history(symbol, interval)
        if df is not None:
            df = df.copy()
            df.attrs['symbol'] = symbol
        return df
    except Exception:
        return None

# ============================================
# PAGE UI
# ============================================
def show():
    st.title("🔍 Strategy Backtester")
    st.markdown("Run a strategy backtest on your chosen stocks")
    st.markdown("---")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### ⚙️ Configuration")

        strategy_names = list_strategies()
        strategy_key = st.selectbox(
            "Strategy", list(strategy_names.keys()),
            format_func=lambda k: strategy_names[k]
        )
        strategy = get_strategy(strategy_key)

        market = st.selectbox("Market", ["US (S&P 500)", "IND (NIFTY 500)"])

        if market == "US (S&P 500)":
            mode_options = [
                f"Optimised Universe ({sum(len(v) for v in OPTIMISED_UNIVERSE.values())} stocks)",
                f"S&P 500 ({len(SP500_TICKERS)} stocks)",
                "Custom Stocks",
                "Single Stock Test",
            ]
            example_tickers, example_single = "AAPL, MSFT, GOOGL, AMZN", "AAPL"
        else:
            mode_options = [
                f"NIFTY 500 ({len(NIFTY500_TICKERS)} stocks)",
                "Custom Stocks",
                "Single Stock Test",
            ]
            example_tickers, example_single = "RELIANCE.NS, TCS.NS, INFY.NS", "RELIANCE.NS"

        mode = st.selectbox("Stock Universe", mode_options)

        params = dict(strategy.DEFAULT_PARAMS)
        for p in strategy.PARAM_SCHEMA:
            if p.get('type') == 'checkbox':
                params[p['key']] = st.checkbox(
                    p['label'], value=p['default'], help=p.get('help')
                )
            else:
                params[p['key']] = st.slider(
                    p['label'], p['min'], p['max'], p['default'],
                    step=p.get('step'), help=p.get('help')
                )

        st.markdown("**Date Range**")
        today = datetime.now().date()
        earliest_cached = today.replace(year=today.year - DEFAULT_HISTORY_YEARS)
        dc1, dc2 = st.columns(2)
        with dc1:
            start_date = st.date_input("Start date", value=earliest_cached,
                min_value=earliest_cached, max_value=today,
                help=f"Only the last {DEFAULT_HISTORY_YEARS} years are cached "
                     "to keep database storage/costs down.")
        with dc2:
            end_date = st.date_input("End date", value=today,
                min_value=start_date, max_value=today)
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)

        def _normalise(ticker):
            ticker = ticker.strip().upper()
            if market == "IND (NIFTY 500)" and ticker and '.' not in ticker:
                ticker += '.NS'
            return ticker

        if mode == "Custom Stocks":
            custom_input = st.text_area(
                "Enter tickers (comma separated)",
                example_tickers,
                height=100
            )
            stocks = [_normalise(s) for s in custom_input.split(',') if s.strip()]
            sectors = {s: 'Custom' for s in stocks}

        elif mode == "Single Stock Test":
            single = _normalise(st.text_input("Enter ticker", example_single))
            stocks = [single]
            sectors = {single: 'Custom'}

        elif mode.startswith("S&P 500"):
            stocks = list(SP500_TICKERS)
            sectors = {t: 'S&P 500' for t in stocks}

        elif mode.startswith("NIFTY 500"):
            stocks = list(NIFTY500_TICKERS)
            sectors = {t: 'NIFTY 500' for t in stocks}

        else:
            selected_sectors = st.multiselect(
                "Filter by sector (leave empty for all)",
                list(OPTIMISED_UNIVERSE.keys()),
                default=[]
            )
            if selected_sectors:
                stocks = [t for s, tickers in OPTIMISED_UNIVERSE.items()
                         for t in tickers if s in selected_sectors]
                sectors = {t: s for s, tickers in OPTIMISED_UNIVERSE.items()
                          for t in tickers if s in selected_sectors}
            else:
                stocks = [t for tickers in OPTIMISED_UNIVERSE.values() for t in tickers]
                sectors = {t: s for s, tickers in OPTIMISED_UNIVERSE.items() for t in tickers}

        if mode != "Single Stock Test" and len(stocks) > 1:
            max_n = len(stocks)
            default_n = min(5, max_n)
            limit = st.slider(
                "Stocks to test this run", 1, max_n, default_n,
                help="Start small to validate your parameters quickly, then "
                     "increase toward the full list once you're happy with them."
            )
            stocks = stocks[:limit]

        st.markdown(f"**Stocks to test:** {len(stocks)}")
        st.markdown(f"**Est. time:** ~{len(stocks) * 4} seconds")

        run = st.button("🚀 Run Backtest", use_container_width=True)

    with col2:
        st.markdown("### 📊 Results")

        if run:
            all_setups = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, symbol in enumerate(stocks):
                status_text.markdown(f"**Processing:** {symbol} ({i+1}/{len(stocks)})")
                try:
                    dfs = [fetch_data(symbol, tf) for tf in strategy.TIMEFRAMES]
                    if any(df is None for df in dfs):
                        setups = []
                    else:
                        setups = strategy.backtest_symbol(dfs, params, start_ts, end_ts)
                    for s in setups:
                        s['symbol'] = symbol
                        s['sector'] = sectors.get(symbol, 'Unknown')
                    all_setups.extend(setups)
                except Exception:
                    pass
                progress_bar.progress((i + 1) / len(stocks))

            status_text.markdown("✅ **Backtest Complete!**")
            progress_bar.empty()

            df = pd.DataFrame(all_setups)
            st.session_state['backtest_results'] = df

            if all_setups:
                # Summary metrics
                total = len(df)
                wins = len(df[df['outcome'] == 'win'])
                losses = len(df[df['outcome'] == 'loss'])
                completed = wins + losses

                m1, m2, m3, m4 = st.columns(4)
                with m1: st.metric("Total Setups", total)
                with m2: st.metric("Wins", wins)
                with m3: st.metric("Losses", losses)
                with m4:
                    wr = round((wins/completed)*100, 2) if completed > 0 else 0
                    st.metric("Win Rate", f"{wr}%")

                if completed > 0:
                    win_rrs = df[df['outcome'] == 'win']['rr_ratio'].dropna()

                    m5, m6, m7 = st.columns(3)
                    if len(win_rrs) > 0:
                        avg_rr = round(win_rrs.mean(), 2)
                        ev = round((wr/100 * avg_rr) - (1 - wr/100), 3)
                        with m5: st.metric("Avg RR", f"{avg_rr}:1")
                        with m6: st.metric("Expected Value", f"+{ev}R")
                        with m7: st.metric("Max RR", f"{round(win_rrs.max(), 2)}:1")
                    else:
                        # No RR data - e.g. Momentum Reversal with its stop loss
                        # off, where risk (and so RR) is undefined by design.
                        with m5: st.metric("Avg RR", "N/A")
                        with m6: st.metric("Expected Value", "N/A")
                        with m7: st.metric("Max RR", "N/A")

                # Results table
                st.markdown("#### 📋 Detailed Results")
                display_df = df[_display_columns(df)].copy()
                display_df['outcome'] = display_df['outcome'].map(_OUTCOME_LABELS).fillna(display_df['outcome'])
                st.dataframe(display_df, use_container_width=True, height=400)

                # Download
                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Download Results CSV",
                    csv,
                    f"backtest_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.warning("No valid setups found. Try adjusting parameters.")

        elif st.session_state.get('backtest_results') is not None and len(st.session_state['backtest_results']) > 0:
            st.info("Previous results loaded. Run a new backtest or go to Results Analysis.")
            df = st.session_state['backtest_results']
            st.dataframe(df[_display_columns(df)].head(20), use_container_width=True)
        else:
            st.markdown("""
<div class='info-box'>
<b>How to use:</b><br>
1. Choose your strategy, market and stock universe<br>
2. Adjust parameters if needed<br>
3. Click Run Backtest<br>
4. Review results and download CSV<br><br>
<b>Tip:</b> Start with a single stock to test quickly,
then run the full optimised universe overnight.
</div>
""", unsafe_allow_html=True)
