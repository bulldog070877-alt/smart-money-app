import pandas as pd
import psycopg2
import streamlit as st

import data_store
from nav import go_to_demand_zone_chart

RESOLVED = ('win', 'loss', 'pending_positive', 'pending_negative')
OPEN = ('awaiting_entry', 'pending')

STATUS_EMOJI = {
    'awaiting_entry': '⏳', 'pending': '📈',
    'win': '✅', 'loss': '❌',
    'pending_positive': '🟡', 'pending_negative': '🟠',
}
STATUS_LABEL = {
    'awaiting_entry': 'Awaiting Entry', 'pending': 'Open',
    'win': 'Win (hit target)', 'loss': 'Loss (hit stop)',
    'pending_positive': 'Closed +ve (no target hit)', 'pending_negative': 'Closed -ve (no target hit)',
}


@st.cache_data(ttl=300, show_spinner=False)
def load_predictions():
    conn = psycopg2.connect(data_store.connection_string())
    try:
        df = pd.read_sql(
            "SELECT symbol, signal_date, entry_date, entry_price_est, target, stop_loss, "
            "hold_days, zone_type, zone_low, zone_high, weekly_refined, push_pct, rr_ratio, "
            "outcome, exit_price, exit_date, checked_at, created_at "
            "FROM demand_zone_predictions ORDER BY signal_date DESC, symbol",
            conn,
        )
    finally:
        conn.close()
    return df


def show():
    st.title("📡 Demand Zone Forward Test Tracker")
    st.markdown(
        "Live forward-test results for the **Demand Zone (SQL Two-Pass)** "
        "strategy. A GitHub Actions job scans the S&P 500 daily, records "
        "\"entry tomorrow\" signals here, then grades each one against real "
        "price data over its holding period - no hindsight involved."
    )
    st.markdown("---")

    if st.button("🔄 Refresh"):
        load_predictions.clear()

    df = load_predictions()

    if len(df) == 0:
        st.markdown("""
<div class='info-box'>
<b>No predictions recorded yet.</b><br><br>
Once the scheduled scan (.github/workflows/demand_zone_scan.yml) has run at
least once, new signals and their outcomes will appear here.
</div>
""", unsafe_allow_html=True)
        return

    resolved = df[df['outcome'].isin(RESOLVED)]
    open_preds = df[df['outcome'].isin(OPEN)]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total signals", len(df))
    with c2:
        st.metric("Open / awaiting entry", len(open_preds))
    with c3:
        decided = resolved[resolved['outcome'].isin(['win', 'loss'])]
        wins = (decided['outcome'] == 'win').sum()
        hit_rate = f"{wins / len(decided) * 100:.1f}%" if len(decided) else "-"
        st.metric("Hit-target rate", hit_rate, help="Win / (Win + Loss), excludes still-open trades")
    with c4:
        avg_gain = None
        if len(resolved):
            realized_pct = (resolved['exit_price'] - resolved['entry_price_est']) / resolved['entry_price_est'] * 100
            avg_gain = realized_pct.mean()
        st.metric("Avg realized %", f"{avg_gain:.2f}%" if avg_gain is not None else "-")

    st.markdown("---")

    sel_symbol = None

    if len(open_preds):
        st.markdown("### 📈 Open Positions")
        show_df = open_preds.copy()
        show_df['Status'] = show_df['outcome'].map(lambda o: f"{STATUS_EMOJI[o]} {STATUS_LABEL[o]}")
        open_cols = ['symbol', 'Status', 'signal_date', 'entry_date', 'entry_price_est',
                     'target', 'stop_loss', 'hold_days', 'zone_type', 'zone_low', 'zone_high',
                     'weekly_refined', 'rr_ratio']
        open_event = st.dataframe(
            show_df[open_cols], use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row", key="dz_fwd_open_table",
        )
        if open_event and open_event.selection and open_event.selection.rows:
            sel_symbol = show_df.iloc[open_event.selection.rows[0]]['symbol']

    st.markdown("### 📋 Resolved Predictions")
    if len(resolved):
        show_df = resolved.copy()
        show_df['Status'] = show_df['outcome'].map(lambda o: f"{STATUS_EMOJI[o]} {STATUS_LABEL[o]}")
        show_df['Realized %'] = (
            (show_df['exit_price'] - show_df['entry_price_est']) / show_df['entry_price_est'] * 100
        ).round(2)
        resolved_cols = ['symbol', 'Status', 'signal_date', 'entry_date', 'entry_price_est',
                         'exit_price', 'exit_date', 'Realized %', 'zone_type', 'zone_low', 'zone_high',
                         'weekly_refined', 'push_pct', 'rr_ratio']
        resolved_event = st.dataframe(
            show_df[resolved_cols], use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row", key="dz_fwd_resolved_table",
        )
        if resolved_event and resolved_event.selection and resolved_event.selection.rows:
            sel_symbol = show_df.iloc[resolved_event.selection.rows[0]]['symbol']
    else:
        st.info("No predictions have resolved yet - check back after a few trading days.")

    if sel_symbol:
        st.markdown("---")
        if st.button(f"🗺️ View {sel_symbol}'s Demand Zone Chart", key="dz_fwd_view_chart"):
            go_to_demand_zone_chart(sel_symbol)

    with st.expander("ℹ️ How to read this"):
        st.markdown("""
- **Awaiting Entry** — a zone was first touched at yesterday's close; the strategy enters at the next session's open.
- **Open** — position entered, still within its holding window (see `hold_days`), no target/stop hit yet.
- **Win** — the target (`entry x (1 + Target %)`) was hit within the holding window.
- **Loss** — the stop (the zone's low, fixed at signal time) was hit.
- **Closed +ve / -ve** — the holding window ran out with no target/stop hit; sign shows whether the close finished above or below entry.
- **weekly_refined** — whether the zone was confirmed by a matching weekly impulse candle (tighter, higher-conviction zone).
""")
