"""
Demand Zone Chart: a single combined daily chart for any symbol showing
every zone find_demand_zones_v2 currently finds (EXTREME + all DECISIONAL),
the monthly push (HL->HH), BOS level, 50% retracement, and current price -
the same picture as pages/trade_inspector.py's per-trade charts, but for
one live symbol lookup instead of a specific backtested trade.
"""
import streamlit as st
import pandas as pd

from data_store import get_history, query_rows
from pages.trade_inspector import _base_candlestick, _add_zone, _add_hline

EXTREME_COLOR = 'rgba(94, 200, 242, 0.16)'
EXTREME_COLOR_REFINED = 'rgba(94, 200, 242, 0.32)'
DECISIONAL_COLOR = 'rgba(179, 136, 255, 0.16)'
DECISIONAL_COLOR_REFINED = 'rgba(179, 136, 255, 0.32)'
CURRENT_ZONE_COLOR = 'rgba(255, 152, 0, 0.34)'
PUSH_COLOR = '#5ec8f2'
BOS_COLOR = '#b388ff'
FIFTY_COLOR = '#7e93ad'
NOW_COLOR = '#f2f6fc'


def _zone_color(zone_type, weekly_refined, is_current):
    if is_current:
        return CURRENT_ZONE_COLOR
    if zone_type == 'EXTREME':
        return EXTREME_COLOR_REFINED if weekly_refined else EXTREME_COLOR
    return DECISIONAL_COLOR_REFINED if weekly_refined else DECISIONAL_COLOR


def _zone_status(price, low, high):
    if low <= price <= high:
        return 'INSIDE'
    return 'BELOW' if price < low else 'ABOVE'


def build_figure(symbol, df, zones):
    """Pure chart-building logic (no Streamlit calls) - a candlestick chart
    with every zone in `zones` overlaid, the monthly push arrow, BOS/50%
    lines and current price. `zones` is the raw list of dict rows from
    find_demand_zones_v2. Returns (fig, current_price, zones_sorted)."""
    current_price = round(float(df['Close'].iloc[-1]), 2)
    push = zones[0]  # HL/HH/BOS/50% are the same across all rows in one call
    hl_date, hl_price = push['out_hl_date'], float(push['out_hl_price'])
    hh_date, hh_price = push['out_hh_date'], float(push['out_hh_price'])
    fifty_pct, bos_level = float(push['out_fifty_pct']), float(push['out_bos_level'])
    push_pct = float(push['out_push_pct'])

    fig = _base_candlestick(
        df, f"{symbol} — Daily Chart | Two-Pass Demand Zones: Daily + Weekly Refinement"
    )
    fig.update_layout(height=640)

    zones_sorted = sorted(zones, key=lambda z: float(z['out_final_low']))
    summary_lines = [f"<b>{symbol} — Two-Pass Refinement</b>", "Daily + Weekly Timeframes", "─" * 28]
    for z in zones_sorted:
        low, high = float(z['out_final_low']), float(z['out_final_high'])
        status = _zone_status(current_price, low, high)
        is_current = status == 'INSIDE'
        label = f"{z['out_zone_type']} #{z['out_zone_num']}"
        refined_tag = " (W)" if z['out_weekly_refined'] else ""
        _add_zone(fig, df, low, high, _zone_color(z['out_zone_type'], z['out_weekly_refined'], is_current),
                   label, show_boundary_labels=False)
        now_tag = "  <-- NOW" if is_current else ""
        summary_lines.append(f"{label}{refined_tag}: ${low:,.2f}–${high:,.2f}{now_tag}")

    _add_hline(fig, hl_price, PUSH_COLOR, f"HL ${hl_price:,.2f}", yshift=-14)
    _add_hline(fig, hh_price, PUSH_COLOR, f"HH ${hh_price:,.2f}", yshift=14)
    _add_hline(fig, bos_level, BOS_COLOR, f"BOS ${bos_level:,.2f}")
    _add_hline(fig, fifty_pct, FIFTY_COLOR, f"50% ${fifty_pct:,.2f}")
    _add_hline(fig, current_price, NOW_COLOR, f"Now ${current_price:,.2f}")

    fig.add_annotation(
        x=str(hh_date), y=hh_price, ax=str(hl_date), ay=hl_price,
        xref='x', yref='y', axref='x', ayref='y',
        showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=2, arrowcolor=PUSH_COLOR,
        text=f"Main Push +{push_pct:.1f}%", font=dict(size=11, color=PUSH_COLOR),
        bgcolor='rgba(26,39,68,0.85)',
    )

    summary_lines.append("─" * 28)
    summary_lines.append(f"Current: ${current_price:,.2f}")
    fig.add_annotation(
        x=0.01, y=0.98, xref='paper', yref='paper', xanchor='left', yanchor='top',
        showarrow=False, align='left', font=dict(size=11, color='#cadcfc', family='monospace'),
        bgcolor='rgba(10,16,32,0.85)', bordercolor='#2a3f6f', borderwidth=1, borderpad=8,
        text="<br>".join(summary_lines),
    )
    return fig, current_price, zones_sorted


def show():
    st.title("📐 Demand Zone Chart")
    st.markdown("Two-pass demand zones (daily + weekly refinement) for any symbol, "
                "via the `find_demand_zones_v2` stored procedure.")
    st.markdown("---")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        symbol = st.text_input("Symbol", "TSLA").strip().upper()
    with col2:
        min_push_pct = st.slider("Min Push %", 10, 150, 20,
                                  help="Minimum monthly HL->HH push size to qualify a zone set")
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        load = st.button("📊 Load Chart", use_container_width=True)

    if not load and 'dz_chart_symbol' not in st.session_state:
        st.info("Enter a symbol and click Load Chart.")
        return
    if load:
        st.session_state['dz_chart_symbol'] = symbol
        st.session_state['dz_chart_push'] = min_push_pct
    symbol = st.session_state.get('dz_chart_symbol', symbol)
    min_push_pct = st.session_state.get('dz_chart_push', min_push_pct)

    with st.spinner(f"Loading {symbol}..."):
        df = get_history(symbol, '1d')
        if df is None or len(df) < 10:
            st.warning(f"No cached price history for {symbol}.")
            return
        zones = query_rows(
            "SELECT * FROM find_demand_zones_v2(%s, %s, %s, %s)",
            (symbol, df.index.min().date(), df.index.max().date(), float(min_push_pct)),
        )

    if not zones:
        st.warning(f"No qualifying zone set found for {symbol} at Min Push % >= {min_push_pct}. "
                   "Try lowering the Min Push % slider.")
        return

    fig, current_price, zones_sorted = build_figure(symbol, df, zones)

    st.plotly_chart(fig, use_container_width=True)
    st.caption("Solid fill = weekly-refined zone. Fainter fill = daily-only zone. "
               "Drag to pan, scroll/pinch to zoom.")

    st.markdown("#### Zone Detail")
    table_rows = [{
        'Zone': f"{z['out_zone_type']} #{z['out_zone_num']}",
        'Low': float(z['out_final_low']), 'High': float(z['out_final_high']),
        'Weekly Refined': bool(z['out_weekly_refined']),
        'Status': _zone_status(current_price, float(z['out_final_low']), float(z['out_final_high'])),
    } for z in zones_sorted]
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
