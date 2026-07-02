import streamlit as st

def show():
    st.title("📈 Smart Money Trading Strategy")
    st.markdown("### Trade like the Banks & Institutions")
    st.markdown("---")

    # Hero stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Win Rate", "92%", "+22% vs S&P avg")
    with col2:
        st.metric("Avg Risk/Reward", "2.1x", "Conservative estimate")
    with col3:
        st.metric("Expected Value", "+1.86R", "Per trade")
    with col4:
        st.metric("Stocks Tested", "449", "S&P 500 backtest")

    st.markdown("---")

    # What is this
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🎯 What is Smart Money Strategy?")
        st.markdown("""
<div class='info-box'>
Banks and institutions (Smart Money) move markets with massive orders.
They need liquidity — clusters of retail stop losses — to fill their positions.

This strategy identifies:
- **Where** Smart Money creates liquidity traps
- **When** they induce retail traders into false moves  
- **How** to enter AFTER they've trapped everyone else

Result: You trade WITH Smart Money, not against them.
</div>
""", unsafe_allow_html=True)

        st.markdown("### 📋 The 5-Step Process")
        steps = [
            ("1️⃣", "Find Main Push", "Strong bullish move (40%+) breaking previous highs"),
            ("2️⃣", "Wait for Pullback", "Price retraces 50%+ into Discount Zone"),
            ("3️⃣", "Identify Demand Zone", "Where Smart Money previously stepped in"),
            ("4️⃣", "Wait for Inducement", "Price sweeps stops below zone"),
            ("5️⃣", "Enter Trade", "Buy the reversal with clear Stop & Target"),
        ]
        for emoji, title, desc in steps:
            st.markdown(f"""
<div class='success-box'>
<b>{emoji} {title}</b><br>
<span style='color: #8892a4; font-size: 13px;'>{desc}</span>
</div>
""", unsafe_allow_html=True)

    with col2:
        st.markdown("### 🏆 Backtest Results by Sector")
        import pandas as pd
        sector_data = pd.DataFrame({
            'Sector': ['Consumer Staples', 'Industrials', 'Comm Services',
                      'Financials', 'Health Care', 'Utilities',
                      'Info Technology', 'Consumer Discret', 'Real Estate',
                      'Materials', 'Energy'],
            'Win Rate %': [77.9, 74.1, 71.9, 71.5, 70.3, 70.0,
                          69.0, 68.9, 67.8, 63.0, 54.5],
            'Avg RR': [2.05, 1.89, 2.09, 1.91, 1.81, 1.85,
                      1.89, 2.20, 2.32, 1.75, 1.65],
            'Status': ['⭐ Best', '⭐ Strong', '⭐ Strong', '⭐ Strong',
                      '✅ Good', '✅ Good', '✅ Good', '✅ Good',
                      '⚠️ Selective', '⚠️ Selective', '❌ Avoid']
        })

        import altair as alt
        chart = alt.Chart(sector_data).mark_bar().encode(
            x=alt.X('Win Rate %:Q', scale=alt.Scale(domain=[50, 85])),
            y=alt.Y('Sector:N', sort='-x'),
            color=alt.condition(
                alt.datum['Win Rate %'] >= 70,
                alt.value('#26a69a'),
                alt.value('#ef5350')
            ),
            tooltip=['Sector', 'Win Rate %', 'Avg RR', 'Status']
        ).properties(height=350).configure_view(
            fill='#1a2744'
        ).configure_axis(
            labelColor='#cadcfc',
            titleColor='#4fc3f7',
            gridColor='#2a3f6f'
        )
        st.altair_chart(chart, use_container_width=True)

        st.markdown("### 🔑 Key Rules")
        rules = [
            "Only trade in the **Discount Zone** (below 50%)",
            "Only trade **fresh** untouched Demand Zones",
            "Wait for **Inducement** before entering",
            "**All 3 timeframes** must align (Monthly/Weekly/Daily)",
            "Risk max **$150 per trade** regardless of zone size",
            "**No Energy sector** — too news-driven",
        ]
        for rule in rules:
            st.markdown(f"✓ {rule}")

    st.markdown("---")
    st.markdown("""
<div style='text-align: center; color: #8892a4; font-size: 13px;'>
Backtested on 449 S&P 500 stocks | 25+ years of data | Monthly/Weekly/Daily timeframes<br>
⚠️ Past performance does not guarantee future results. Trade responsibly.
</div>
""", unsafe_allow_html=True)
