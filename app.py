import streamlit as st

import auth

st.set_page_config(
    page_title="Smart Money Strategy",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0d1b2a; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #1a2744; }
    [data-testid="stSidebar"] * { color: #cadcfc !important; }
    
    /* Headers */
    h1, h2, h3 { color: #4fc3f7 !important; }
    p, li, label { color: #cadcfc !important; }
    
    /* Metric cards */
    [data-testid="metric-container"] {
        background-color: #1a2744;
        border: 1px solid #2a3f6f;
        border-radius: 10px;
        padding: 15px;
    }
    [data-testid="metric-container"] label { color: #8892a4 !important; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] { 
        color: #4fc3f7 !important; font-size: 2rem !important; 
    }
    
    /* Dataframes */
    [data-testid="stDataFrame"] { background-color: #1a2744; }
    
    /* Buttons */
    .stButton > button {
        background-color: #1e2761;
        color: #4fc3f7;
        border: 1px solid #4fc3f7;
        border-radius: 8px;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #4fc3f7;
        color: #0d1b2a;
    }
    
    /* Info boxes */
    .info-box {
        background-color: #1a2744;
        border-left: 4px solid #4fc3f7;
        padding: 15px 20px;
        border-radius: 0 8px 8px 0;
        margin: 10px 0;
    }
    .success-box {
        background-color: #1a2744;
        border-left: 4px solid #26a69a;
        padding: 15px 20px;
        border-radius: 0 8px 8px 0;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #1a2744;
        border-left: 4px solid #ff9800;
        padding: 15px 20px;
        border-radius: 0 8px 8px 0;
        margin: 10px 0;
    }
    .info-box, .info-box *,
    .success-box, .success-box *,
    .warning-box, .warning-box * {
        color: #cadcfc !important;
    }
    .info-box b, .success-box b, .warning-box b { color: #4fc3f7 !important; }

    /* Selectbox and inputs */
    .stSelectbox > div, .stNumberInput > div {
        background-color: #1a2744 !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #1a2744 !important;
        border-color: #2a3f6f !important;
    }
    div[data-baseweb="select"] * { color: #cadcfc !important; }
    div[data-baseweb="select"] input::placeholder { color: #8892a4 !important; opacity: 1 !important; }
    div[data-baseweb="tag"] { background-color: #2a3f6f !important; }

    /* Selectbox dropdown popover (rendered outside the widget in a portal) */
    div[data-baseweb="popover"] { background-color: #1a2744 !important; }
    div[data-baseweb="popover"] ul,
    div[data-baseweb="popover"] li,
    div[data-baseweb="popover"] [role="option"] {
        background-color: #1a2744 !important;
        color: #cadcfc !important;
    }
    div[data-baseweb="popover"] li:hover,
    div[data-baseweb="popover"] [role="option"]:hover,
    div[data-baseweb="popover"] [aria-selected="true"] {
        background-color: #2a3f6f !important;
        color: #ffffff !important;
    }
    
    /* Progress bar */
    .stProgress > div > div { background-color: #4fc3f7; }
    
    /* Divider */
    hr { border-color: #2a3f6f; }

    /* Table */
    thead tr th { background-color: #1e2761 !important; color: #4fc3f7 !important; }
    tbody tr:nth-child(even) { background-color: #1a2744 !important; }
    tbody tr:nth-child(odd) { background-color: #0d1b2a !important; }
    td { color: #cadcfc !important; }
</style>
""", unsafe_allow_html=True)

authenticator = auth.require_login()

# Sidebar navigation
st.sidebar.title("📈 Smart Money")
st.sidebar.markdown(f"Logged in as **{st.session_state['name']}**")
authenticator.logout("Logout", "sidebar")
st.sidebar.markdown("---")

pages = {
    "🏠 Home": "home",
    "🔍 Backtester": "backtest",
    "📊 Results Analysis": "results",
    "🔎 Trade Inspector": "trade_inspector",
    "🎯 Daily Screener": "screener",
    "📡 Forward Test Tracker": "forward_test",
    "📐 Risk Calculator": "risk",
    "📚 Strategy Guide": "guide",
}

selection = st.sidebar.radio("Navigation", list(pages.keys()))

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style='color: #8892a4; font-size: 12px;'>
<b style='color: #4fc3f7;'>Strategy Stats</b><br>
Win Rate: 92%<br>
Avg RR: 2.1x<br>
EV: +1.86R/trade<br>
Stocks: 79 optimised
</div>
""", unsafe_allow_html=True)

# Route to pages
page = pages[selection]

if page == "home":
    from pages import home
    home.show()
elif page == "backtest":
    from pages import backtest
    backtest.show()
elif page == "results":
    from pages import results
    results.show()
elif page == "trade_inspector":
    from pages import trade_inspector
    trade_inspector.show()
elif page == "screener":
    from pages import screener
    screener.show()
elif page == "forward_test":
    from pages import forward_test
    forward_test.show()
elif page == "risk":
    from pages import risk_calc
    risk_calc.show()
elif page == "guide":
    from pages import guide
    guide.show()
