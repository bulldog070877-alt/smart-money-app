import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from data_store import get_history

CANDLE_UP = '#3ecf8e'
CANDLE_DOWN = '#f0616b'
ZONE_WIDE_COLOR = 'rgba(232, 176, 74, 0.14)'
ZONE_TIGHT_COLOR = 'rgba(232, 176, 74, 0.38)'

# Overlay line/marker colors - deliberately avoid green/red so nothing here
# gets mistaken for the candlestick up/down coloring.
PUSH_COLOR = '#5ec8f2'      # blue - push structure (HH/HL, 50% level)
CHOCH_COLOR = '#b388ff'     # violet - CHoCH marker
TOUCH_COLOR = '#e8b04b'     # gold - zone touch marker (matches zone fill)
ENTRY_COLOR = '#f2f6fc'     # near-white - entry price/date, the pivot point
TARGET_COLOR = '#26c6da'    # cyan - target line + WIN marker/shading
STOP_COLOR = '#ff9800'      # orange - stop line + LOSS marker/shading
PENDING_COLOR = '#8a7bd8'   # muted violet - pending shading
LINE_DASH = 'dot'

FIELD_LABELS = {
    'symbol': 'Symbol', 'sector': 'Sector',
    'push_date': 'Push High Date', 'push_low_date': 'Push Low Date',
    'push_high': 'Push High ($)', 'push_low': 'Push Low ($)', 'push_pct': 'Push %',
    '50pct_level': '50% Level ($)', 'choch_date': 'CHoCH Date',
    'retracement_pct': 'Retracement %', 'touch_date': 'Zone Touch Date',
    'entry_date': 'Entry Date', 'entry_price': 'Entry Price ($)',
    'stop_loss': 'Stop Loss ($)', 'target': 'Target ($)',
    'zone_type': 'Zone Type', 'zone_low': 'Zone Low ($)', 'zone_high': 'Zone High ($)',
    'zone_low_wide': 'Wide Zone Low ($)', 'zone_high_wide': 'Wide Zone High ($)',
    'zone_width_pct': 'Zone Width %', 'risk': 'Risk ($)', 'risk_pct': 'Risk %',
    'reward': 'Reward ($)', 'rr_ratio': 'Risk : Reward', 'max_high': 'Max High (window)',
    'min_low': 'Min Low (window)', 'outcome': 'Outcome',
    'exit_price': 'Exit Price ($)', 'exit_date': 'Exit Date',
}


def _val(row, key):
    v = row.get(key) if hasattr(row, 'get') else None
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return v


def _date(row, key):
    v = _val(row, key)
    if v is None:
        return None
    try:
        return pd.Timestamp(v)
    except (ValueError, TypeError):
        return None


def _is_zone_daily(row):
    return _date(row, 'touch_date') is not None


def _base_candlestick(df, title):
    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        increasing_line_color=CANDLE_UP, decreasing_line_color=CANDLE_DOWN,
        increasing_fillcolor=CANDLE_UP, decreasing_fillcolor=CANDLE_DOWN,
        name=title,
    )])
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color='#cadcfc')),
        height=340,
        margin=dict(l=10, r=10, t=36, b=10),
        xaxis_rangeslider_visible=False,
        template='plotly_dark',
        paper_bgcolor='#1a2744',
        plot_bgcolor='#1a2744',
        font=dict(color='#cadcfc'),
        showlegend=False,
    )
    fig.update_xaxes(gridcolor='#2a3f6f')
    fig.update_yaxes(gridcolor='#2a3f6f')
    return fig


def _add_zone(fig, low, high, color, label):
    if low is None or high is None:
        return
    fig.add_hrect(y0=low, y1=high, fillcolor=color, line_width=0, layer='below',
                   annotation_text=label, annotation_position='top left',
                   annotation_font=dict(size=10, color='#e8b04b'))


def _add_hline(fig, y, color, label):
    if y is None:
        return
    fig.add_hline(y=y, line_dash=LINE_DASH, line_color=color, line_width=1.5,
                  annotation_text=label, annotation_position='right',
                  annotation_font=dict(size=10, color=color))


def _add_vline(fig, x, color, label):
    if x is None:
        return
    fig.add_vline(x=x, line_dash=LINE_DASH, line_color=color, line_width=1.5,
                  annotation_text=label, annotation_position='top',
                  annotation_font=dict(size=10, color=color))


def show():
    st.title("🔎 Trade Inspector")
    st.markdown("Pick a trade from your backtest results and see exactly what happened, "
                "month by week by day.")
    st.markdown("---")

    uploaded = st.file_uploader(
        "Upload backtest CSV (or use results from the Backtester page)", type=['csv']
    )
    if uploaded:
        df = pd.read_csv(uploaded)
        st.success(f"✅ Loaded {len(df)} setups from uploaded file")
    elif 'backtest_results' in st.session_state:
        df = st.session_state['backtest_results']
        st.info(f"📊 Using results from Backtester: {len(df)} setups")
    else:
        df = None

    if df is None or len(df) == 0:
        st.markdown("""
<div class='info-box'>
Run a backtest or upload a results CSV to inspect individual trades here.
</div>
""", unsafe_allow_html=True)
        return

    st.markdown("#### Select a trade")
    st.caption("Click a row to inspect that trade below.")
    display_cols = [c for c in [
        'symbol', 'sector', 'push_date', 'entry_date', 'entry_price',
        'stop_loss', 'target', 'rr_ratio', 'outcome',
    ] if c in df.columns]
    event = st.dataframe(
        df[display_cols], use_container_width=True, height=300, hide_index=True,
        on_select="rerun", selection_mode="single-row",
    )
    selected_rows = event.selection['rows'] if event and event.selection else []
    if not selected_rows:
        return

    row = df.iloc[selected_rows[0]]
    symbol = row['symbol']
    is_zd = _is_zone_daily(row)

    st.markdown("---")
    outcome = str(_val(row, 'outcome') or '').lower()
    header = f"{symbol} — {_val(row, 'push_date')}"
    if 'win' in outcome:
        st.success(f"✅ **{header}** — WIN  (R:R {_val(row, 'rr_ratio')})")
    elif 'loss' in outcome:
        st.error(f"❌ **{header}** — LOSS  (R:R {_val(row, 'rr_ratio')})")
    else:
        st.warning(f"⏳ **{header}** — {outcome.upper() or 'PENDING'}  (R:R {_val(row, 'rr_ratio')})")

    with st.spinner(f"Loading price history for {symbol}..."):
        df_monthly = get_history(symbol, '1mo')
        df_weekly = get_history(symbol, '1wk')
        df_daily = get_history(symbol, '1d')

    if df_monthly is None or df_weekly is None or df_daily is None:
        st.warning("Couldn't load enough price history for this symbol to build the charts.")
        return

    push_date = _date(row, 'push_date')
    push_low_date = _date(row, 'push_low_date') or push_date
    entry_date = _date(row, 'entry_date') or push_date
    exit_date = _date(row, 'exit_date')
    touch_date = _date(row, 'touch_date')
    choch_date = _date(row, 'choch_date')

    push_high = _val(row, 'push_high')
    push_low = _val(row, 'push_low')
    fifty_pct = _val(row, '50pct_level')
    zone_low = _val(row, 'zone_low')
    zone_high = _val(row, 'zone_high')
    zone_low_wide = _val(row, 'zone_low_wide') or zone_low
    zone_high_wide = _val(row, 'zone_high_wide') or zone_high
    entry_price = _val(row, 'entry_price')
    stop_loss = _val(row, 'stop_loss')
    target = _val(row, 'target')

    # ---------- Monthly: full push context ----------
    m_start = push_low_date - pd.Timedelta(days=120)
    m_end = (exit_date or entry_date or push_date) + pd.Timedelta(days=90)
    fig_m = _base_candlestick(df_monthly, "Monthly — Push context")
    fig_m.update_xaxes(range=[m_start, m_end])
    _add_zone(fig_m, zone_low_wide, zone_high_wide, ZONE_WIDE_COLOR, "Demand zone")
    _add_hline(fig_m, push_high, PUSH_COLOR, "Push High")
    _add_hline(fig_m, push_low, PUSH_COLOR, "Push Low")
    if fifty_pct:
        _add_hline(fig_m, fifty_pct, '#7e93ad', "50% level")
    _add_vline(fig_m, push_date, PUSH_COLOR, "HH")
    _add_vline(fig_m, push_low_date, PUSH_COLOR, "HL")
    st.plotly_chart(fig_m, use_container_width=True)
    st.caption("Drag to pan, scroll/pinch to zoom — the full cached history is loaded, not just this window.")

    # ---------- Weekly: precise demand zone ----------
    w_start = push_low_date - pd.Timedelta(days=14)
    w_end = (exit_date or entry_date or push_date) + pd.Timedelta(days=45)
    fig_w = _base_candlestick(df_weekly, "Weekly — Demand zone")
    fig_w.update_xaxes(range=[w_start, w_end])
    _add_zone(fig_w, zone_low_wide, zone_high_wide, ZONE_TIGHT_COLOR, "Demand zone")
    _add_vline(fig_w, push_date, PUSH_COLOR, "Push High")
    if choch_date:
        _add_vline(fig_w, choch_date, CHOCH_COLOR, "CHoCH")
    if touch_date:
        _add_vline(fig_w, touch_date, TOUCH_COLOR, "Touch")
    _add_vline(fig_w, entry_date, ENTRY_COLOR, "Entry")
    st.plotly_chart(fig_w, use_container_width=True)

    # ---------- Daily: entry, stop/target, outcome ----------
    d_start = entry_date - pd.Timedelta(days=5)
    default_end = entry_date + pd.Timedelta(days=15)
    d_end = max(exit_date, default_end) if exit_date else default_end
    d_end = d_end + pd.Timedelta(days=5)  # buffer after resolution
    fig_d = _base_candlestick(df_daily, "Daily — Entry & outcome")
    fig_d.update_xaxes(range=[d_start, d_end])
    _add_zone(fig_d, zone_low_wide, zone_high_wide, ZONE_WIDE_COLOR, "Weekly zone")
    if is_zd and zone_low != zone_low_wide:
        _add_zone(fig_d, zone_low, zone_high, ZONE_TIGHT_COLOR, "Tightened zone")
    _add_hline(fig_d, entry_price, ENTRY_COLOR, "Entry")
    _add_hline(fig_d, stop_loss, STOP_COLOR, "Stop")
    _add_hline(fig_d, target, TARGET_COLOR, "Target")
    _add_vline(fig_d, entry_date, ENTRY_COLOR, "Entry")

    if 'win' in outcome:
        _add_vline(fig_d, exit_date, TARGET_COLOR, "WIN")
        if exit_date:
            fig_d.add_vrect(x0=entry_date, x1=exit_date, fillcolor='rgba(38,198,218,0.10)', line_width=0)
    elif 'loss' in outcome:
        _add_vline(fig_d, exit_date, STOP_COLOR, "LOSS")
        if exit_date:
            fig_d.add_vrect(x0=entry_date, x1=exit_date, fillcolor='rgba(255,152,0,0.10)', line_width=0)
    else:
        fig_d.add_vrect(x0=entry_date, x1=default_end, fillcolor='rgba(138,123,216,0.09)', line_width=0)

    st.plotly_chart(fig_d, use_container_width=True)

    # ---------- Stats ----------
    st.markdown("#### 📋 Trade Details")
    stats_rows = [
        {'Field': FIELD_LABELS.get(k, k), 'Value': row[k]}
        for k in row.index
        if k in FIELD_LABELS and _val(row, k) is not None
    ]
    st.dataframe(pd.DataFrame(stats_rows), use_container_width=True, height=min(400, 40 + 35 * len(stats_rows)), hide_index=True)
