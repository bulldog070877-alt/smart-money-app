import streamlit as st

def show():
    st.title("📚 Strategy Guide")
    st.markdown("Complete reference guide for the Smart Money Trading Strategy")
    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏗️ Concepts", "📋 Checklist", "🔄 Liquidity Cycle",
        "⏰ Timeframes", "❓ FAQ"
    ])

    with tab1:
        st.markdown("## Core Concepts")

        concepts = {
            "1️⃣ Market Structure": {
                "color": "#4fc3f7",
                "content": """
**What it is:** The framework of Higher Highs (HH) and Higher Lows (HL) that defines trend direction.

**Key components:**
- **Main Push:** The most recent impulsive bullish leg creating a new HH (must be 40%+)
- **50% Level:** Midpoint between Previous HL and new HH — our key dividing line
- **Discount Zone:** Below 50% — where we ONLY look to buy
- **Premium Zone:** Above 50% — too expensive, we avoid buying here

**The Rule:** We only buy when price is in the Discount Zone (below 50%)
"""
            },
            "2️⃣ Liquidity": {
                "color": "#ff9800",
                "content": """
**What it is:** Clusters of stop loss orders sitting at predictable price levels.

**Types of liquidity:**
- **Equal Highs/Lows:** Obvious levels everyone can see
- **Trendline Liquidity:** Stops below rising trendlines
- **Break & Test:** Stops below broken support levels
- **Structural Liquidity:** Stops at market structure levels

**Key insight:** Smart Money (banks) NEEDS this liquidity to fill their massive orders.
They engineer moves to these levels to collect the orders before reversing.

**A+ Setup:** Previous Day/Week/Month Low coinciding with Demand Zone = highest probability
"""
            },
            "3️⃣ Inducement": {
                "color": "#ab47bc",
                "content": """
**What it is:** Smart Money engineering a move to trap retail traders before the real move.

**The Sequence:**
1. **Accumulation:** Price consolidates, building a range
2. **Inducement:** Price breaks below liquidity pool, triggering stops
3. **Confirmation:** CHoCH + Momentum + Imbalance (FVG)
4. **Move:** Smart Money fully loaded, price moves aggressively

**Why it matters:** The inducement tells us Smart Money has collected all the orders they need.
After inducement, the real move begins.

**One key rule:** All three confirmations must be present after inducement.
"""
            },
            "4️⃣ Demand Zone": {
                "color": "#26a69a",
                "content": """
**What it is:** A specific price area where Smart Money previously stepped in aggressively.

**Two types:**
- **Decisional DZ:** The zone that directly caused the Main Push (broke previous HH)
- **Extreme DZ:** Zone near the Previous HL — deepest discount, origin of the entire move

**Valid Zone Criteria (ALL must be met):**
1. Located below 50% level (Discount Zone)
2. Consolidation of 4+ candles visible
3. Equal Lows forming liquidity
4. Inducement candle breaking below Equal Lows
5. Impulse candle (50%+ body) following inducement
6. Zone must be FRESH (never touched since creation)

**The Golden Rule:** A zone is only valid ONCE. Once touched, it's used up.
"""
            },
            "5️⃣ Lower TF Confirmations (RIFC)": {
                "color": "#f5c518",
                "content": """
**What it is:** Entry-level confirmation using the lowest timeframe (Daily).

**RIFC = Refined Institutional Funded Candle**

**The process:**
1. Price arrives at Demand Zone on Weekly
2. Drop to Daily timeframe
3. Look for same fractal pattern:
   - Bearish structure (LH + LL) on Daily
   - Price creates HH instead of LH → CHoCH
   - Inducement → Impulse → Imbalance on Daily
4. The RIFC = Daily POI that forms
5. Entry when price taps the RIFC

**Key insight:** Price action is fractal — same patterns repeat at every timeframe.
No extra rules needed, just apply the same logic at a smaller scale.
"""
            },
        }

        for title, data in concepts.items():
            with st.expander(title, expanded=False):
                st.markdown(f"<div style='border-left: 4px solid {data['color']}; padding-left: 15px;'>{data['content']}</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("## A+ Trade Checklist")
        st.markdown("*Every item must be checked before entering a trade*")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 📊 Market Structure")
            checks_ms = [
                "Strong Main Push identified (40%+ move)",
                "Previous HL and HH clearly defined",
                "Price currently in Discount Zone (below 50%)",
                "CHoCH confirmed on Weekly (2nd Lower Low)",
                "Pullback has started — not buying the top",
            ]
            for check in checks_ms:
                st.checkbox(check, key=f"ms_{check[:20]}")

            st.markdown("### 🎯 Demand Zone")
            checks_dz = [
                "Valid Demand Zone found on Weekly",
                "Zone has consolidation (4+ candles)",
                "Equal Lows visible in consolidation",
                "Inducement candle swept below Equal Lows",
                "Impulse candle confirms (50%+ body)",
                "Zone is FRESH — never touched before",
                "Zone is below 50% level",
            ]
            for check in checks_dz:
                st.checkbox(check, key=f"dz_{check[:20]}")

        with col2:
            st.markdown("### 🌟 A+ Bonus Conditions")
            checks_bonus = [
                "Previous Week/Month Low induced ⭐",
                "Multiple liquidity types coincide ⭐",
                "Zone aligns with Previous Structure ⭐",
                "Daily chart shows same pattern ⭐",
            ]
            for check in checks_bonus:
                st.checkbox(check, key=f"bonus_{check[:20]}")

            st.markdown("### 💰 Trade Management")
            checks_tm = [
                "Entry = Zone High (when Daily touches)",
                "Stop Loss = Below Inducement Low (with buffer)",
                "Target = Previous Higher High",
                "RR Ratio minimum 1.5:1",
                "Position size = $3,000",
                "Risk = max $150 (5% of position)",
                "Fewer shares if zone is wide",
                "No other open position in same stock",
            ]
            for check in checks_tm:
                st.checkbox(check, key=f"tm_{check[:20]}")

        if st.button("Reset All Checkboxes"):
            st.experimental_rerun()

    with tab3:
        st.markdown("## The Liquidity Cycle")
        st.markdown("*Every price move follows this 5-stage cycle*")

        stages = [
            {
                "num": "1", "title": "Build Up",
                "color": "#4fc3f7",
                "desc": "Price creates a range or consolidation. Equal lows, trendlines, and support/resistance levels form. Retail traders place predictable stop losses at obvious levels.",
                "signals": ["Price ranging sideways", "Equal Highs or Lows forming", "Volume decreasing"],
                "action": "Identify and mark the liquidity pools forming"
            },
            {
                "num": "2", "title": "Inducement",
                "color": "#ff9800",
                "desc": "Smart Money engineers a move to grab all the liquidity. Price breaks below/above the liquidity pool, triggering retail stops. Early buyers get trapped. Early sellers get trapped.",
                "signals": ["Big candle breaking below equal lows", "Stop hunt wick visible", "Retail panic selling"],
                "action": "Wait — don't enter yet! This is the trap."
            },
            {
                "num": "3", "title": "Market Shift",
                "color": "#ab47bc",
                "desc": "Internal structure changes from bearish to bullish. CHoCH (Change of Character) occurs. Momentum shifts. Imbalance/FVG left behind by the impulse candle.",
                "signals": ["CHoCH on Weekly/Daily", "Strong bullish candle", "FVG/Imbalance created"],
                "action": "Smart Money is loaded. Prepare for entry."
            },
            {
                "num": "4", "title": "Mitigation",
                "color": "#f5c518",
                "desc": "Price returns to fill the imbalance (FVG) left behind. This is OUR entry point. Price is revisiting the zone where Smart Money filled their orders.",
                "signals": ["Price returning to FVG zone", "Bearish retest on Daily", "Volume lighter on pullback"],
                "action": "🎯 ENTER HERE — This is our trade!"
            },
            {
                "num": "5", "title": "Continuation",
                "color": "#26a69a",
                "desc": "Price moves toward the next Higher High, fulfilling the cycle. New liquidity builds for the next cycle. Trailing stop follows Higher Lows.",
                "signals": ["Higher Highs and Higher Lows forming", "Momentum increasing", "Previous HH target reached"],
                "action": "Trail your stop behind Higher Lows. Let it run."
            },
        ]

        for stage in stages:
            with st.expander(f"Stage {stage['num']}: {stage['title']}", expanded=False):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.markdown(f"<div style='border-left: 4px solid {stage['color']}; padding-left: 15px;'>{stage['desc']}</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown("**Signals to watch:**")
                    for sig in stage['signals']:
                        st.markdown(f"• {sig}")
                with c3:
                    st.markdown("**Your action:**")
                    st.markdown(f"<div style='background: #1a2744; padding: 10px; border-radius: 8px; color: {stage['color']};'><b>{stage['action']}</b></div>", unsafe_allow_html=True)

    with tab4:
        st.markdown("## Three Timeframes — One Decision")

        tfs = [
            {
                "tf": "Monthly (TF1)", "role": "The Big Picture",
                "color": "#4fc3f7",
                "tasks": [
                    "Identify Main Push (HH and HL)",
                    "Calculate 50% retracement level",
                    "Define Discount vs Premium zones",
                    "Confirm we are in a strong bullish trend",
                ],
                "question": "Is there a strong bullish trend?",
                "analogy": "Checking the weather for the whole week. Sets context for everything."
            },
            {
                "tf": "Weekly (TF2)", "role": "The Setup",
                "color": "#ff9800",
                "tasks": [
                    "Confirm Change of Character (CHoCH)",
                    "Find valid Demand Zones",
                    "Verify zone freshness",
                    "Monitor pullback progress",
                ],
                "question": "Has the pullback started and where is the zone?",
                "analogy": "Checking tomorrow's forecast. Narrows down the opportunity."
            },
            {
                "tf": "Daily (TF3)", "role": "The Entry",
                "color": "#26a69a",
                "tasks": [
                    "Wait for price to enter Weekly Demand Zone",
                    "Confirm momentum shift on Daily",
                    "Identify RIFC (entry candle)",
                    "Place entry, stop and target",
                ],
                "question": "Is price at the zone and confirming reversal?",
                "analogy": "Checking the hourly forecast. The precise moment to act."
            },
        ]

        for tf in tfs:
            st.markdown(f"""
<div style='background: #1a2744; border: 1px solid #2a3f6f; border-radius: 10px; 
padding: 20px; margin: 10px 0; border-left: 5px solid {tf["color"]};'>
<h3 style='color: {tf["color"]}; margin: 0;'>{tf["tf"]} — {tf["role"]}</h3>
<p style='color: #8892a4; font-style: italic; margin: 5px 0;'>"{tf["question"]}"</p>
</div>
""", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 1])
            with c1:
                st.markdown("**Tasks on this timeframe:**")
                for task in tf['tasks']:
                    st.markdown(f"✓ {task}")
            with c2:
                st.markdown("**Analogy:**")
                st.markdown(f"*{tf['analogy']}*")
            st.markdown("")

    with tab5:
        st.markdown("## Frequently Asked Questions")

        faqs = [
            ("What if price doesn't reach 50%?",
             "We miss the trade — and that's perfectly fine! There will always be new setups. Never chase price into the Premium Zone. The strategy only works when we buy cheap."),
            ("Can I trade the same stock twice?",
             "Only if a new fresh Demand Zone has formed after the previous one was used. A zone can only be traded ONCE. After first touch, it's invalidated."),
            ("What if the Extreme Zone breaks?",
             "If price breaks and closes below the Extreme Zone with momentum, the entire setup is invalidated. This means the Main Push is likely over and a new bearish phase has begun."),
            ("How many trades can I have open?",
             "Maximum 6 trades simultaneously ($18,000 / $3,000 = 6). Never hold more than one position in the same stock at the same time."),
            ("What's the difference between Decisional and Extreme zones?",
             "Decisional = the zone that directly caused the Main Push (broke previous HH). Extreme = zone near the Previous HL, deepest discount. We prefer Decisional first, use Extreme as backup."),
            ("When do I move my stop to breakeven?",
             "After price reaches the 3:1 target level. At that point, move your stop to your entry price. This guarantees you cannot lose on the trade."),
            ("Should I take partial profits?",
             "Take profits at 3:1 to lock in gains, then trail your stop behind Weekly Higher Lows to let the rest run toward the Previous Higher High."),
            ("What if the zone is very wide?",
             "Buy fewer shares. Risk is always fixed at $150 maximum. If the zone is wide, the risk per share is large, so you simply buy fewer shares to keep total risk at $150."),
            ("Why avoid Energy stocks?",
             "Energy is heavily driven by oil prices and geopolitical news, making price action unpredictable and market structure unreliable. Our backtest showed only 54.5% win rate in Energy — barely above random."),
            ("How often does a setup occur?",
             "Across our optimised 79-stock universe, roughly 1-3 quality setups per week. This strategy is about quality over quantity — few trades, but high probability."),
        ]

        for question, answer in faqs:
            with st.expander(f"❓ {question}"):
                st.markdown(f"<div class='info-box'>{answer}</div>", unsafe_allow_html=True)
