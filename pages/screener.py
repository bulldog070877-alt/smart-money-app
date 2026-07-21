import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

from data_store import get_history
from market_universe import SP500_TICKERS, NIFTY500_TICKERS
from strategies import list_strategies, get_strategy

OPTIMISED_STOCKS = [
    'COST', 'WMT', 'MCD', 'PG', 'ADM', 'EL', 'MO', 'KO', 'PEP',
    'ITW', 'DOV', 'HON', 'GE', 'CAT', 'DE', 'MMM', 'ETN',
    'GOOGL', 'NFLX', 'META', 'DIS',
    'MCO', 'AMP', 'JPM', 'GS', 'MA', 'V', 'MS', 'BLK', 'SPGI',
    'ABBV', 'UNH', 'JNJ', 'TMO', 'ABT', 'DHR',
    'ADSK', 'AAPL', 'MSFT', 'ADBE', 'QCOM',
    'ORLY', 'SBUX', 'ROST', 'HD', 'AMZN', 'LOW', 'TJX',
    'O', 'IRM', 'PLD',
]

def get_current_price(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period='5d', interval='1d', timeout=15)
        if len(df) == 0: return None
        df.index = df.index.tz_localize(None)
        return round(df['Close'].iloc[-1], 2)
    except:
        return None

def fetch_data(symbol, interval):
    try:
        df = get_history(symbol, interval)
        if df is None or len(df) < 10: return None
        df = df.copy()
        df.attrs['symbol'] = symbol
        return df
    except Exception:
        return None

def quick_screen(symbol, strategy, params):
    """Quick screen for the current active/developing setup, if any."""
    dfs = [fetch_data(symbol, tf) for tf in strategy.TIMEFRAMES]
    if any(df is None for df in dfs):
        return None

    current_price = get_current_price(symbol)
    if current_price is None:
        return None

    result = strategy.screen_symbol(dfs, current_price, params)
    if result is None:
        return None
    result['symbol'] = symbol
    return result

def show():
    st.title("🎯 Daily Screener")
    st.markdown(f"*Scan date: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    st.markdown("---")

    col1, col2 = st.columns([1, 3])

    with col1:
        st.markdown("### ⚙️ Settings")

        strategy_names = list_strategies()
        strategy_key = st.selectbox(
            "Strategy", list(strategy_names.keys()),
            format_func=lambda k: strategy_names[k]
        )
        strategy = get_strategy(strategy_key)
        params = dict(strategy.DEFAULT_PARAMS)

        market = st.selectbox("Market", ["US (S&P 500)", "IND (NIFTY 500)"])

        if market == "US (S&P 500)":
            universe_options = [
                "Optimised (51 stocks)",
                f"S&P 500 ({len(SP500_TICKERS)} stocks)",
                "Custom",
            ]
            example_tickers = "AAPL, MSFT, GOOGL"
        else:
            universe_options = [f"NIFTY 500 ({len(NIFTY500_TICKERS)} stocks)", "Custom"]
            example_tickers = "RELIANCE.NS, TCS.NS, INFY.NS"

        stock_mode = st.selectbox("Universe", universe_options)

        def _normalise(ticker):
            ticker = ticker.strip().upper()
            if market == "IND (NIFTY 500)" and ticker and '.' not in ticker:
                ticker += '.NS'
            return ticker

        if stock_mode == "Custom":
            custom = st.text_area("Tickers (comma separated)", example_tickers)
            scan_stocks = [_normalise(s) for s in custom.split(',') if s.strip()]
        elif stock_mode.startswith("S&P 500"):
            scan_stocks = list(SP500_TICKERS)
        elif stock_mode.startswith("NIFTY 500"):
            scan_stocks = list(NIFTY500_TICKERS)
        else:
            scan_stocks = OPTIMISED_STOCKS

        if len(scan_stocks) > 1:
            max_n = len(scan_stocks)
            default_n = min(5, max_n)
            limit = st.slider(
                "Stocks to scan this run", 1, max_n, default_n,
                help="Start small to validate quickly, then increase toward "
                     "the full list once you're happy with the results."
            )
            scan_stocks = scan_stocks[:limit]

        st.markdown(f"**Stocks:** {len(scan_stocks)}")
        st.markdown(f"**Est. time:** ~{len(scan_stocks) * 3}s")

        run_scan = st.button("🔍 Run Scan", use_container_width=True)

        st.markdown("---")
        st.markdown("### 🚦 Alert Levels")
        st.markdown("""
🟢 **Inside Zone** — Enter now
🟡 **Ready (<5%)** — Prepare entry
🟠 **Approaching (<15%)** — Watch
🔴 **Watching** — Pullback in progress
⚪ **No Zone** — Setup incomplete
❌ **Below Zone** — Setup invalid
""")

    with col2:
        if run_scan:
            results = []
            progress = st.progress(0)
            status = st.empty()

            for i, symbol in enumerate(scan_stocks):
                status.markdown(f"**Scanning:** {symbol} ({i+1}/{len(scan_stocks)})")
                try:
                    result = quick_screen(symbol, strategy, params)
                    if result:
                        results.append(result)
                except:
                    pass
                progress.progress((i + 1) / len(scan_stocks))
                time.sleep(0.3)

            progress.empty()
            status.markdown(f"✅ **Scan complete!** Found {len(results)} active setups")

            st.session_state['screener_results'] = results

        results = st.session_state.get('screener_results', [])

        if results:
            # Priority order
            priority = {'INSIDE ZONE': 0, 'READY': 1, 'APPROACHING': 2,
                       'WATCHING': 3, 'NO ZONE': 4, 'BELOW ZONE': 5}
            results.sort(key=lambda x: priority.get(x['status'], 9))

            # Alert buckets
            inside = [r for r in results if r['status'] == 'INSIDE ZONE']
            ready = [r for r in results if r['status'] == 'READY']
            approaching = [r for r in results if r['status'] == 'APPROACHING']
            watching = [r for r in results if r['status'] == 'WATCHING']

            # Summary
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("🟢 Inside Zone", len(inside))
            with c2: st.metric("🟡 Ready", len(ready))
            with c3: st.metric("🟠 Approaching", len(approaching))
            with c4: st.metric("🔴 Watching", len(watching))

            st.markdown("---")

            # Actionable alerts
            if inside or ready or approaching:
                st.markdown("### 🚨 Action Required")
                for r in inside + ready + approaching:
                    with st.expander(f"{r['emoji']} **{r['symbol']}** — {r['status']} | Price: ${r['current_price']}"):
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.markdown("**📊 Main Push**")
                            st.markdown(f"HH: ${r['push_high']}")
                            st.markdown(f"HL: ${r['push_low']}")
                            st.markdown(f"Push %: {r['push_pct']}%")
                            st.markdown(f"50% Level: ${r['50pct_level']}")
                        with c2:
                            st.markdown("**🎯 Demand Zone**")
                            if r['zone_low'] and r['zone_high']:
                                st.markdown(f"Zone: ${r['zone_low']} — ${r['zone_high']}")
                                st.markdown(f"Distance: {r['distance_pct']}%")
                                st.markdown(f"RR Ratio: {r['rr_ratio']}:1")
                            else:
                                st.markdown("No zone found")
                        with c3:
                            st.markdown("**💰 Trade Setup**")
                            if r['zone_high'] and r['rr_ratio']:
                                st.markdown(f"Entry: ${r['zone_high']}")
                                st.markdown(f"Stop: ${r['push_low']}")
                                st.markdown(f"Target: ${r['push_high']}")
                                st.markdown(f"**RR: {r['rr_ratio']}:1**")
            else:
                st.info("No immediate action required. Monitor watching list below.")

            # Watching list
            if watching:
                st.markdown("### 🔴 Watching List")
                watch_data = []
                for r in watching:
                    watch_data.append({
                        'Symbol': r['symbol'],
                        'Price': f"${r['current_price']}",
                        'Retracement': f"{r['retracement_pct']}%",
                        'Zone': f"${r['zone_low']} - ${r['zone_high']}" if r['zone_low'] else 'No zone',
                        'Distance': f"{r['distance_pct']}%" if r['distance_pct'] else '-',
                        'RR': f"{r['rr_ratio']}:1" if r['rr_ratio'] else '-',
                    })
                st.dataframe(pd.DataFrame(watch_data), use_container_width=True)

            # Full summary table
            st.markdown("### 📋 Full Scan Results")
            summary_data = [{
                'Symbol': r['symbol'],
                'Status': f"{r['emoji']} {r['status']}",
                'Price': f"${r['current_price']}",
                'Zone': f"${r['zone_low']}-${r['zone_high']}" if r['zone_low'] else '-',
                'Distance': f"{r['distance_pct']}%" if r['distance_pct'] else '-',
                'Retracement': f"{r['retracement_pct']}%",
                'RR': f"{r['rr_ratio']}:1" if r['rr_ratio'] else '-',
            } for r in results]
            st.dataframe(pd.DataFrame(summary_data), use_container_width=True)

        else:
            st.markdown("""
<div class='info-box'>
<b>Run a scan to see results here.</b><br><br>
The screener will check each stock for:
<ul>
<li>Active Main Push (40%+ move)</li>
<li>Pullback in progress</li>
<li>Valid Demand Zone identified</li>
<li>Distance to zone</li>
<li>Risk/Reward ratio</li>
</ul>
</div>
""", unsafe_allow_html=True)
