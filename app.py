import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from quant_engine import normalize_ohlcv, add_indicators, run_orb_backtest
from agents import run_research_agents

st.set_page_config(page_title="Gold Quant Desk", page_icon="📈", layout="wide")
st.title("🟡 Gold Quant Desk")
st.caption("Multi-agent XAUUSD research lab · Phase 1: historical research only · No live orders")

with st.sidebar:
    st.header("Research settings")
    symbol = st.text_input("Symbol", "XAUUSD")
    timeframe = st.selectbox("Candle timeframe", ["1min", "5min", "15min", "1h"], index=1)
    risk_usd = st.number_input("Illustrative risk per trade ($)", min_value=1.0, value=100.0, step=25.0)
    reward_r = st.number_input("Target (R multiple)", min_value=0.25, value=2.0, step=0.25)
    adx_min = st.slider("ADX minimum", min_value=5, max_value=40, value=20)
    st.info("Research only. No broker integration or live orders are enabled.")

uploaded = st.file_uploader("Upload historical OHLCV CSV", type=["csv"])
st.markdown("Expected columns: `time` (or `datetime`/`timestamp`), `open`, `high`, `low`, `close`; `volume` is optional.")

if uploaded:
    try:
        raw = pd.read_csv(uploaded)
        df = add_indicators(normalize_ohlcv(raw))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Candles", f"{len(df):,}")
        c2.metric("From", str(df.index.min()))
        c3.metric("To", str(df.index.max()))
        c4.metric("Median range", f"{(df['high'] - df['low']).median():.3f}")
        st.subheader("Closing price")
        st.line_chart(df[["close"]].tail(500), height=220)
        with st.expander("Inspect uploaded data"):
            st.dataframe(df.tail(100), use_container_width=True)

        st.subheader("Specialist agents")
        if st.button("Run research agents", type="primary"):
            for item in run_research_agents(df, adx_min=adx_min):
                with st.container(border=True):
                    st.markdown(f"**{item['agent']}**")
                    st.write(item["finding"])
                    st.caption(item["caveat"])

        st.subheader("Opening-range breakout experiment")
        st.write("Exploratory baseline: New York 01:00–01:15 range followed by a close-confirmed breakout.")
        tz_name = st.text_input("Timezone of CSV timestamps", "America/New_York")
        spread = st.number_input("Assumed spread (price units)", min_value=0.0, value=0.20, step=0.01, format="%.3f")
        slippage = st.number_input("Assumed slippage per side (price units)", min_value=0.0, value=0.05, step=0.01, format="%.3f")
        if st.button("Run ORB backtest"):
            result, trades = run_orb_backtest(df, timezone_name=tz_name, risk_usd=risk_usd,
                                               target_r=reward_r, adx_min=adx_min,
                                               spread=spread, slippage=slippage)
            a, b, c, d = st.columns(4)
            a.metric("Trades", result["trades"])
            b.metric("Estimated net P&L", f"${result['net_pnl']:.2f}")
            c.metric("Profit factor", "—" if result["profit_factor"] is None else f"{result['profit_factor']:.2f}")
            d.metric("Max drawdown", f"${result['max_drawdown']:.2f}")
            st.warning("Candle-based research prototype, not tick-level broker simulation. If stop and target are touched in the same candle, the stop is assumed first. Verify data timezone and cost units.")
            if not trades.empty:
                st.dataframe(trades, use_container_width=True)
                st.download_button("Download trade log CSV", trades.to_csv(index=False),
                                   file_name="gold_orb_trades.csv", mime="text/csv")
    except Exception as exc:
        st.error(f"Could not process this CSV: {exc}")
else:
    st.info("Upload historical XAUUSD candles to start. No fabricated example performance is shown.")
    agents = [
        ("📰 News agent", "Live news is not connected yet; this agent reports the missing feed honestly."),
        ("🕯️ Price-action agent", "Summarises candle structure, recent highs/lows and breakout context."),
        ("📊 Quant agent", "Calculates ATR, ADX, moving averages and volatility statistics."),
        ("🛡️ Risk agent", "Checks hypothetical risk assumptions; does not calculate broker-specific lot size yet."),
        ("🕒 Session agent", "Session analysis requires correctly timestamped, timezone-aware data."),
        ("👁️ Trade monitor", "Future phase: monitors demo positions through a separate persistent worker."),
    ]
    cols = st.columns(3)
    for i, (name, desc) in enumerate(agents):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{name}**")
                st.write(desc)

st.divider()
st.caption(f"Build timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · No credentials should be entered into this prototype.")
