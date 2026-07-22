"""
Daily Watchlist for the Demand Zone (SQL Two-Pass) strategy: reads the
pre-computed snapshots the scheduled scan (daily_demand_zone_scan.py ->
scan_universe) writes to demand_zone_watchlist, instead of live-scanning
the S&P 500 in the browser (~500 SQL calls, several minutes) every time
someone opens this page.
"""
import pandas as pd
import psycopg2
import streamlit as st

import data_store
from data_store import get_history, query_rows
from nav import go_to_demand_zone_chart
from pages.demand_zone_chart import build_figure
from strategies.demand_zone_sql import DEFAULT_PARAMS as DZ_DEFAULT_PARAMS

STATUS_EMOJI = {
    'INSIDE ZONE': '🟢', 'ENTRY TOMORROW': '🎯', 'READY': '🟡',
    'APPROACHING': '🟠',
}
PRIORITY = {
    'ENTRY TOMORROW': 0, 'INSIDE ZONE': 1, 'READY': 2, 'APPROACHING': 3,
}

# Non-actionable statuses (far from the zone, or already invalidated) - kept
# in the database for history, but hidden from this page's view.
HIDDEN_STATUSES = ('WATCHING', 'BELOW ZONE', 'ZONE TOO WIDE', 'LOW RR')


@st.cache_data(ttl=300, show_spinner=False)
def load_scan_dates():
    conn = psycopg2.connect(data_store.connection_string())
    try:
        df = pd.read_sql(
            "SELECT DISTINCT scan_date FROM demand_zone_watchlist ORDER BY scan_date DESC LIMIT 60",
            conn,
        )
    finally:
        conn.close()
    return df['scan_date'].tolist()


@st.cache_data(ttl=300, show_spinner=False)
def load_watchlist(scan_date):
    conn = psycopg2.connect(data_store.connection_string())
    try:
        df = pd.read_sql(
            "SELECT symbol, status, current_price, push_high, push_low, push_pct, "
            "fifty_pct, retracement_pct, zone_type, zone_low, zone_high, weekly_refined, "
            "distance_pct, rr_ratio FROM demand_zone_watchlist WHERE scan_date = %(d)s "
            "ORDER BY symbol",
            conn, params={'d': scan_date},
        )
    finally:
        conn.close()
    return df


def show():
    st.title("🗺️ Demand Zone Daily Watchlist")
    st.markdown(
        "Pre-computed daily snapshot for the **Demand Zone (SQL Two-Pass)** strategy "
        "across the S&P 500, written by the scheduled scan "
        "(`.github/workflows/demand_zone_scan.yml`). Reads a saved report instead of "
        "live-scanning 500 symbols in the browser."
    )
    st.markdown("---")

    dates = load_scan_dates()
    if not dates:
        st.markdown("""
<div class='info-box'>
<b>No watchlist snapshots recorded yet.</b><br><br>
Once the scheduled scan has run at least once (or you trigger it manually via
<code>python daily_demand_zone_scan.py</code> / the workflow's "Run workflow"
button), each day's full-universe scan will appear here.
</div>
""", unsafe_allow_html=True)
        return

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        scan_date = st.selectbox("Scan date", dates, format_func=lambda d: d.strftime('%Y-%m-%d (%a)'))
    with col2:
        status_filter = st.multiselect(
            "Filter by status", list(STATUS_EMOJI.keys()),
            help="Leave empty to show every status",
        )
    with col3:
        min_rr = st.number_input(
            "Min RR Ratio", min_value=0.0, max_value=10.0, value=1.5, step=0.1,
            help="Only show rows with reward:risk at or above this",
        )

    df = load_watchlist(scan_date)
    df = df[~df['status'].isin(HIDDEN_STATUSES)]
    df = df[df['rr_ratio'] >= min_rr]
    if status_filter:
        df = df[df['status'].isin(status_filter)]

    if len(df) == 0:
        st.info("No symbols match this filter for the selected scan date.")
        return

    counts = df['status'].value_counts()
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("🎯 Entry Tomorrow", int(counts.get('ENTRY TOMORROW', 0)))
    with c2: st.metric("🟢 Inside Zone", int(counts.get('INSIDE ZONE', 0)))
    with c3: st.metric("🟡 Ready", int(counts.get('READY', 0)))
    with c4: st.metric("🟠 Approaching", int(counts.get('APPROACHING', 0)))

    st.markdown("---")
    st.markdown(f"#### 📋 Watchlist — {scan_date.strftime('%Y-%m-%d')} ({len(df)} symbols)")

    show_df = df.copy()
    show_df['Status'] = show_df['status'].map(lambda s: f"{STATUS_EMOJI.get(s, '')} {s}")
    show_df['_priority'] = show_df['status'].map(lambda s: PRIORITY.get(s, 9))
    show_df = show_df.sort_values(['_priority', 'distance_pct'], na_position='last')

    display_cols = ['symbol', 'Status', 'current_price', 'zone_low', 'zone_high', 'zone_type',
                     'weekly_refined', 'distance_pct', 'retracement_pct', 'push_pct', 'rr_ratio']
    event = st.dataframe(
        show_df[display_cols],
        use_container_width=True, hide_index=True, height=520,
        on_select="rerun", selection_mode="single-row",
    )

    csv = df.to_csv(index=False)
    st.download_button(
        "📥 Download CSV", csv, f"demand_zone_watchlist_{scan_date}.csv", "text/csv",
    )

    st.markdown("---")
    selected_rows = event.selection.rows if event and event.selection else []
    if not selected_rows:
        st.caption("👆 Click a row above to view its Demand Zone chart here, without leaving this page.")
        return

    sel_symbol = show_df[display_cols].iloc[selected_rows[0]]['symbol']
    header_col, link_col = st.columns([4, 1])
    with header_col:
        st.markdown(f"#### 📐 Demand Zone Chart — {sel_symbol}")
    with link_col:
        if st.button("🔗 Open full page", key="dz_watchlist_open_chart", use_container_width=True):
            go_to_demand_zone_chart(sel_symbol, DZ_DEFAULT_PARAMS['MIN_PUSH_PCT'])
    with st.spinner(f"Loading {sel_symbol}..."):
        chart_df = get_history(sel_symbol, '1d')
        if chart_df is None or len(chart_df) < 10:
            st.warning(f"No cached price history for {sel_symbol}.")
            return
        zones = query_rows(
            "SELECT * FROM find_demand_zones_v2(%s, %s, %s, %s)",
            (sel_symbol, chart_df.index.min().date(), chart_df.index.max().date(),
             float(DZ_DEFAULT_PARAMS['MIN_PUSH_PCT'])),
        )
    if not zones:
        st.warning(f"No qualifying zone set found for {sel_symbol} at Min Push % >= "
                   f"{DZ_DEFAULT_PARAMS['MIN_PUSH_PCT']}.")
        return

    fig, _, _ = build_figure(sel_symbol, chart_df, zones)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Solid fill = weekly-refined zone. Fainter fill = daily-only zone. "
               "Drag to pan, scroll/pinch to zoom.")
