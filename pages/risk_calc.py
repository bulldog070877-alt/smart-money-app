import streamlit as st
import pandas as pd

def show():
    st.title("📐 Risk Calculator")
    st.markdown("Calculate position size, risk and reward for any trade setup")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 💼 Account Settings")
        total_capital = st.number_input(
            "Total Capital ($)", value=18000, step=1000,
            help="Your total trading capital"
        )
        position_size = st.number_input(
            "Position Size per Trade ($)", value=3000, step=500,
            help="Fixed amount per trade"
        )
        max_risk_pct = st.slider(
            "Max Risk % of Position", 1.0, 10.0, 5.0, 0.5,
            help="Maximum loss as % of position size"
        )
        max_risk_dollars = round(position_size * max_risk_pct / 100, 2)

        st.markdown(f"""
<div class='info-box'>
<b>Account Summary:</b><br>
Max Positions: <b>{int(total_capital / position_size)}</b> simultaneous trades<br>
Max Risk per Trade: <b>${max_risk_dollars}</b><br>
Max Total Exposure: <b>${position_size * int(total_capital / position_size):,}</b><br>
Max Total Risk: <b>${max_risk_dollars * int(total_capital / position_size):,.0f}</b> ({round(max_risk_dollars * int(total_capital / position_size) / total_capital * 100, 1)}% of capital)
</div>
""", unsafe_allow_html=True)

        st.markdown("### 🎯 Trade Parameters")
        entry_price = st.number_input("Entry Price ($)", value=137.93, step=0.01,
            help="Zone High — where you enter the trade")
        stop_price = st.number_input("Stop Loss Price ($)", value=130.74, step=0.01,
            help="Below Inducement candle Low (with 0.5% buffer)")
        target_price = st.number_input("Target Price ($)", value=202.85, step=0.01,
            help="Previous Higher High")

    with col2:
        st.markdown("### 📊 Trade Calculation")

        if entry_price > stop_price and target_price > entry_price:
            risk_per_share = round(entry_price - stop_price, 2)
            reward_per_share = round(target_price - entry_price, 2)
            rr_ratio = round(reward_per_share / risk_per_share, 2)

            # Shares calculation
            shares = int(max_risk_dollars / risk_per_share)
            actual_position = round(shares * entry_price, 2)
            actual_risk = round(shares * risk_per_share, 2)
            actual_reward = round(shares * reward_per_share, 2)

            # 3R target
            target_3r = round(entry_price + (risk_per_share * 3), 2)
            reward_3r = round(shares * risk_per_share * 3, 2)

            # Stop loss %
            sl_pct = round((risk_per_share / entry_price) * 100, 2)

            st.markdown(f"""
<div class='success-box'>
<b>✅ Trade Setup Summary</b>
</div>
""", unsafe_allow_html=True)

            m1, m2 = st.columns(2)
            with m1:
                st.metric("Shares to Buy", shares)
                st.metric("Actual Position", f"${actual_position:,.2f}")
                st.metric("Risk per Share", f"${risk_per_share}")
                st.metric("Stop Loss %", f"{sl_pct}%")
            with m2:
                st.metric("Risk/Reward Ratio", f"{rr_ratio}:1")
                st.metric("Actual Risk", f"${actual_risk}", f"of ${max_risk_dollars} max")
                st.metric("Potential Profit", f"${actual_reward:,.2f}")
                st.metric("Position vs Limit", f"${actual_position:,.0f} / ${position_size:,.0f}")

            st.markdown("---")
            st.markdown("### 🎯 Exit Strategy")

            exit_data = pd.DataFrame({
                'Exit Point': ['Stop Loss', 'Breakeven', '1R Target', '2R Target',
                              '3R Target (First Exit)', 'Full Target (Previous HH)'],
                'Price': [stop_price, entry_price,
                         round(entry_price + risk_per_share, 2),
                         round(entry_price + risk_per_share * 2, 2),
                         target_3r, target_price],
                'P&L ($)': [
                    f"-${actual_risk:.0f} ❌",
                    f"$0 (Breakeven)",
                    f"+${actual_risk:.0f}",
                    f"+${actual_risk*2:.0f}",
                    f"+${reward_3r:.0f} 🎯",
                    f"+${actual_reward:.0f} 🏆"
                ],
                'Action': [
                    'Full stop out',
                    'Move stop here after 3R',
                    'Partial exit optional',
                    'Partial exit optional',
                    'Take profit, move stop to BE',
                    'Full exit — previous HH'
                ]
            })
            st.dataframe(exit_data, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### 📈 Scenario Analysis")

            scenarios = pd.DataFrame({
                'Scenario': ['Stop Loss Hit', '1R Win', '2R Win', '3R Win (Lock In)', 'Full Target'],
                'Probability': ['8%', '~30%', '~25%', '~20%', '17%'],
                'P&L ($)': [f"-${actual_risk:.0f}",
                           f"+${actual_risk:.0f}",
                           f"+${actual_risk*2:.0f}",
                           f"+${reward_3r:.0f}",
                           f"+${actual_reward:.0f}"],
                'Account Change': [
                    f"-{round(actual_risk/total_capital*100, 2)}%",
                    f"+{round(actual_risk/total_capital*100, 2)}%",
                    f"+{round(actual_risk*2/total_capital*100, 2)}%",
                    f"+{round(reward_3r/total_capital*100, 2)}%",
                    f"+{round(actual_reward/total_capital*100, 2)}%"
                ]
            })
            st.dataframe(scenarios, use_container_width=True, hide_index=True)

            # Expected value
            ev_per_trade = round((0.92 * rr_ratio) - (0.08 * 1), 3)
            ev_dollars = round(ev_per_trade * actual_risk, 2)

            st.markdown(f"""
<div class='success-box'>
<b>💰 Expected Value (based on 92% win rate)</b><br>
Per Trade (in R): +{ev_per_trade}R<br>
Per Trade (in $): +${ev_dollars:.2f}<br>
Per 10 Trades: +${ev_dollars*10:.2f}<br>
Per 50 Trades: +${ev_dollars*50:.2f}
</div>
""", unsafe_allow_html=True)

        else:
            st.markdown("""
<div class='warning-box'>
⚠️ Please enter valid trade parameters:<br>
Entry Price must be > Stop Loss<br>
Target Price must be > Entry Price
</div>
""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📚 Risk Rules Reminder")
    rules_col1, rules_col2 = st.columns(2)
    with rules_col1:
        st.markdown("""
**Position Rules:**
- Fixed $3,000 position per trade ✅
- Max $150 risk per trade (5%) ✅  
- Buy fewer shares if zone is wide ✅
- Max 6 simultaneous positions ✅
- Never double up on same stock ✅
""")
    with rules_col2:
        st.markdown("""
**Exit Rules:**
- Stop Loss: Below inducement candle low ✅
- First target: 3:1 RR ✅
- Move stop to breakeven at 3:1 ✅
- Trail stop behind Weekly Higher Lows ✅
- Final target: Previous Higher High ✅
""")
