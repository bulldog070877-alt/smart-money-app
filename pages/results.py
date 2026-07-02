import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

def show():
    st.title("📊 Results Analysis")
    st.markdown("Analyse backtest results by sector, stock and performance metrics")
    st.markdown("---")

    # Load data
    uploaded = st.file_uploader(
        "Upload backtest CSV (or use results from Backtester page)",
        type=['csv']
    )

    df = None
    if uploaded:
        df = pd.read_csv(uploaded)
        st.success(f"✅ Loaded {len(df)} setups from uploaded file")
    elif 'backtest_results' in st.session_state:
        df = st.session_state['backtest_results']
        st.info(f"📊 Using results from Backtester: {len(df)} setups")

    # Built-in S&P 500 results
    use_sp500 = st.checkbox("Use built-in S&P 500 backtest results", value=df is None)

    if use_sp500:
        # Built-in summary data from our backtest
        df = pd.DataFrame({
            'symbol': ['ITW','GOOGL','GOOG','ORLY','ADM','SBUX','STE','DOV','IRM','AIZ',
                      'O','NFLX','ROST','STLD','AMP','MCO','ADSK','HD','EL','MO',
                      'COST','WMT','MCD','AAPL','AMZN','QCOM','JPM','GS','MA','ABBV',
                      'MSFT','ADBE','HON','CAT','SPGI','UNH','JNJ','TMO'],
            'sector': ['Industrials','Comm Services','Comm Services','Consumer Discret',
                      'Consumer Staples','Consumer Discret','Health Care','Industrials',
                      'Real Estate','Financials','Real Estate','Comm Services',
                      'Consumer Discret','Materials','Financials','Financials',
                      'Info Technology','Consumer Discret','Consumer Staples','Consumer Staples',
                      'Consumer Staples','Consumer Staples','Consumer Staples',
                      'Info Technology','Consumer Discret','Info Technology',
                      'Financials','Financials','Financials','Health Care',
                      'Info Technology','Info Technology','Industrials','Industrials',
                      'Financials','Health Care','Health Care','Health Care'],
            'setups': [4,3,3,4,4,5,3,3,3,3,4,3,3,5,4,6,3,3,5,3,
                      8,5,5,8,8,12,6,4,3,3,6,5,4,4,4,8,5,4],
            'wins': [4,3,3,4,4,5,3,3,3,3,4,3,3,5,4,6,3,3,5,3,
                    8,5,5,7,7,11,5,4,3,3,5,5,3,3,4,5,4,3],
            'win_rate': [100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,
                        100,100,100,100,100,100,100,87.5,87.5,91.7,83.3,100,100,100,
                        83.3,100,75,75,100,62.5,80,75],
            'avg_rr': [4.73,4.04,3.69,3.45,3.38,3.34,3.12,2.96,2.87,2.77,
                      2.76,2.66,2.66,2.55,2.50,2.50,2.47,2.43,2.26,2.12,
                      1.93,1.46,1.44,1.52,1.54,2.22,2.65,1.20,1.46,1.36,
                      1.28,2.06,1.89,1.95,2.85,1.49,1.80,2.10],
        })
        df['losses'] = df['setups'] - df['wins']
        df['outcome'] = df.apply(lambda r: 'win' if r['wins'] > r['losses'] else 'loss', axis=1)
        st.info("📊 Showing S&P 500 backtest summary (449 stocks, 1,384 setups)")

    if df is None:
        st.markdown("""
<div class='info-box'>
Run the backtester first or upload a CSV file to see analysis here.
</div>
""", unsafe_allow_html=True)
        return

    # ── OVERALL METRICS ──
    st.markdown("### 🎯 Overall Performance")
    if 'win_rate' in df.columns:
        # Summary data mode
        total_setups = df['setups'].sum()
        total_wins = df['wins'].sum()
        total_losses = df['losses'].sum()
        completed = total_wins + total_losses
        overall_wr = round((total_wins / completed) * 100, 2) if completed > 0 else 0
        avg_rr = round(df['avg_rr'].mean(), 2)
        ev = round((overall_wr/100 * avg_rr) - (1 - overall_wr/100), 3)
    else:
        total_setups = len(df)
        wins = len(df[df['outcome'] == 'win'])
        losses = len(df[df['outcome'] == 'loss'])
        completed = wins + losses
        overall_wr = round((wins/completed)*100, 2) if completed > 0 else 0
        avg_rr = round(df[df['outcome']=='win']['rr_ratio'].mean(), 2) if wins > 0 else 0
        ev = round((overall_wr/100 * avg_rr) - (1 - overall_wr/100), 3)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Total Setups", f"{total_setups:,}")
    with c2: st.metric("Win Rate", f"{overall_wr}%")
    with c3: st.metric("Avg RR", f"{avg_rr}x")
    with c4: st.metric("Expected Value", f"+{ev}R")
    with c5: st.metric("Stocks", df['symbol'].nunique())

    st.markdown("---")

    # ── SECTOR ANALYSIS ──
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🏭 Win Rate by Sector")
        if 'win_rate' in df.columns:
            sector_df = df.groupby('sector').agg(
                Stocks=('symbol', 'nunique'),
                Setups=('setups', 'sum'),
                Wins=('wins', 'sum'),
                Losses=('losses', 'sum')
            ).reset_index()
            sector_df['Win Rate %'] = round(sector_df['Wins'] / (sector_df['Wins'] + sector_df['Losses']) * 100, 1)
            sector_df['Avg RR'] = df.groupby('sector')['avg_rr'].mean().round(2).values
        else:
            sector_df = df.groupby('sector').apply(lambda x: pd.Series({
                'Stocks': x['symbol'].nunique(),
                'Setups': len(x),
                'Wins': len(x[x['outcome']=='win']),
                'Losses': len(x[x['outcome']=='loss']),
            })).reset_index()
            sector_df['Win Rate %'] = round(sector_df['Wins'] / (sector_df['Wins'] + sector_df['Losses']) * 100, 1)

        sector_df = sector_df.sort_values('Win Rate %', ascending=False)

        chart = alt.Chart(sector_df).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X('Win Rate %:Q', scale=alt.Scale(domain=[50, 85])),
            y=alt.Y('sector:N', sort='-x', title=''),
            color=alt.condition(
                alt.datum['Win Rate %'] >= 70,
                alt.value('#26a69a'),
                alt.value('#ef5350')
            ),
            tooltip=['sector', 'Win Rate %', 'Setups', 'Stocks']
        ).properties(height=280).configure_view(
            fill='#1a2744', stroke='#2a3f6f'
        ).configure_axis(
            labelColor='#cadcfc', gridColor='#2a3f6f', titleColor='#4fc3f7'
        )
        st.altair_chart(chart, use_container_width=True)

    with col2:
        st.markdown("### 📈 Win Rate by Stock (Top 20)")
        if 'win_rate' in df.columns:
            stock_chart_df = df.nlargest(20, 'win_rate')[['symbol', 'win_rate', 'avg_rr', 'setups']]
            stock_chart_df.columns = ['Symbol', 'Win Rate %', 'Avg RR', 'Setups']
        else:
            stock_stats = df.groupby('symbol').apply(lambda x: pd.Series({
                'Win Rate %': round(len(x[x['outcome']=='win'])/len(x[x['outcome'].isin(['win','loss'])])*100, 1) if len(x[x['outcome'].isin(['win','loss'])]) > 0 else 0,
                'Setups': len(x[x['outcome'].isin(['win','loss'])]),
            })).reset_index()
            stock_stats = stock_stats[stock_stats['Setups'] >= 2]
            stock_chart_df = stock_stats.nlargest(20, 'Win Rate %')

        chart2 = alt.Chart(stock_chart_df).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X('Win Rate %:Q', scale=alt.Scale(domain=[50, 105])),
            y=alt.Y('Symbol:N', sort='-x', title=''),
            color=alt.condition(
                alt.datum['Win Rate %'] >= 90,
                alt.value('#f5c518'),
                alt.value('#4fc3f7')
            ),
            tooltip=['Symbol', 'Win Rate %', 'Setups']
        ).properties(height=280).configure_view(
            fill='#1a2744', stroke='#2a3f6f'
        ).configure_axis(
            labelColor='#cadcfc', gridColor='#2a3f6f', titleColor='#4fc3f7'
        )
        st.altair_chart(chart2, use_container_width=True)

    st.markdown("---")

    # ── DETAILED TABLE ──
    st.markdown("### 📋 Stock Performance Table")
    if 'win_rate' in df.columns:
        display = df[['symbol', 'sector', 'setups', 'wins', 'losses', 'win_rate', 'avg_rr']].copy()
        display.columns = ['Symbol', 'Sector', 'Setups', 'Wins', 'Losses', 'Win Rate %', 'Avg RR']
        display = display.sort_values('Win Rate %', ascending=False)
    else:
        display = df.groupby(['symbol']).apply(lambda x: pd.Series({
            'Sector': x['sector'].iloc[0] if 'sector' in x.columns else 'Unknown',
            'Setups': len(x),
            'Wins': len(x[x['outcome']=='win']),
            'Losses': len(x[x['outcome']=='loss']),
            'Win Rate %': round(len(x[x['outcome']=='win'])/max(1,len(x[x['outcome'].isin(['win','loss'])]))*100, 1),
            'Avg RR': round(x[x['outcome']=='win']['rr_ratio'].mean(), 2) if len(x[x['outcome']=='win']) > 0 else 0
        })).reset_index()
        display = display.rename(columns={'symbol': 'Symbol'})
        display = display.sort_values('Win Rate %', ascending=False)

    # Add emoji flags
    def flag(wr):
        if wr >= 90: return '⭐⭐'
        elif wr >= 80: return '⭐'
        elif wr >= 70: return '✅'
        elif wr >= 60: return '⚠️'
        else: return '❌'
    display['Flag'] = display['Win Rate %'].apply(flag)

    st.dataframe(display, use_container_width=True, height=400)

    # Download
    csv = display.to_csv(index=False)
    st.download_button(
        "📥 Download Analysis CSV",
        csv,
        f"analysis_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )

    st.markdown("---")
    st.markdown("""
<div style='color: #8892a4; font-size: 12px; text-align: center;'>
⚠️ Past performance does not guarantee future results. 
Win rates based on historical backtesting. Always manage risk responsibly.
</div>
""", unsafe_allow_html=True)
