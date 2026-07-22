"""
Cross-page navigation helper.

This app dispatches pages manually via a sidebar radio bound to
st.session_state (see app.py) rather than Streamlit's native multipage
file-based routing, so "linking" to another page means presetting that
radio's session_state value (and any state the target page reads) before
triggering a rerun.
"""
import streamlit as st

DEMAND_ZONE_CHART_LABEL = "🗺️ Demand Zone Chart"


def go_to_demand_zone_chart(symbol, min_push_pct=20):
    """Jump to the Demand Zone Chart page pre-loaded for `symbol`.

    Can't set st.session_state['nav_page'] directly here - by the time a
    page's button-click code runs, the sidebar radio (key="nav_page") has
    already been instantiated earlier in this same script run, and
    Streamlit forbids mutating a widget's key after that. Instead, stash
    the target under a separate key that app.py consumes into 'nav_page'
    at the top of the *next* run, before the radio widget is created."""
    st.session_state['dz_chart_symbol'] = symbol
    st.session_state['dz_chart_push'] = min_push_pct
    st.session_state['_nav_redirect'] = DEMAND_ZONE_CHART_LABEL
    st.rerun()
