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

STATUS_EMOJI = {
    'INSIDE ZONE': '🟢', 'ENTRY TOMORROW': '🎯', 'READY': '🟡',
    'APPROACHING': '🟠', 'WATCHING': '🔴', 'BELOW ZONE': '❌',
    'ZONE TOO WIDE': '⚪', 'LOW RR': '⚪',
}
PRIORITY = {
    'ENTRY TOMORROW': 0, 'INSIDE ZONE': 1, 'READY': 2, 'APPROACHING': 3,
    'WATCHING': 4, 'ZONE TOO WIDE': 5, 'LOW RR': 5, 'BELOW ZONE': 6,
}


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

    col1, col2 = st.columns([1, 3])
    with col1:
        scan_date = st.selectbox("Scan date", dates, format_func=lambda d: d.strftime('%Y-%m-%d (%a)'))
    with col2:
        status_filter = st.multiselect(
            "Filter by status", list(STATUS_EMOJI.keys()),
            help="Leave empty to show every status",
        )

    df = load_watchlist(scan_date)
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

    st.dataframe(
        show_df[['symbol', 'Status', 'current_price', 'zone_low', 'zone_high', 'zone_type',
                 'weekly_refined', 'distance_pct', 'retracement_pct', 'push_pct', 'rr_ratio']],
        use_container_width=True, hide_index=True, height=520,
    )

    csv = df.to_csv(index=False)
    st.download_button(
        "📥 Download CSV", csv, f"demand_zone_watchlist_{scan_date}.csv", "text/csv",
    )
