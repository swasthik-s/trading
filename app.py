import streamlit as st
import pandas as pd
import numpy as np
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

from quant_engine import normalize_ohlcv, add_indicators, run_orb_backtest
from agents import run_research_agents

st.set_page_config(page_title="Gold Quant Desk", page_icon="📈", layout="wide")
st.title("🟡 Gold Quant Desk")
st.caption("Multi-agent XAUUSD research lab · Historical research only · No live orders")

with st.sidebar:
    st.header("Research settings")
    symbol = st.text_input("Symbol", "XAUUSD")
    timeframe = st.selectbox("Candle timeframe", ["1min", "5min", "15min", "1h"], index=1)
    risk_usd = st.number_input("Illustrative risk per trade ($)", min_value=1.0, value=100.0, step=25.0)
    reward_r = st.number_input("Target (R multiple)", min_value=0.25, value=2.0, step=0.25)
    adx_min = st.slider("ADX minimum", min_value=5, max_value=40, value=20)
    st.info("Research only. No broker integration or live orders are enabled.")

st.subheader("1. Download historical gold data")
st.write("Fetch free historical XAUUSD candles from Dukascopy and load them directly into the research workspace. No API key is required for this public data source.")
today_utc = datetime.now(timezone.utc).date()
with st.form("history_download_form"):
    d1, d2, d3 = st.columns([1, 1, 1])
    start_date = d1.date_input("Start date (UTC)", value=today_utc - timedelta(days=365), max_value=today_utc - timedelta(days=2))
    end_date = d2.date_input("End date (UTC)", value=today_utc - timedelta(days=1), min_value=start_date, max_value=today_utc - timedelta(days=1))
    output_tf = d3.selectbox("Output timeframe", ["5min", "15min", "30min", "1h", "4h", "1D", "1min"], index=0)
    price_side = st.selectbox("Price side", ["BID", "ASK", "MID"], index=0, help="BID/ASK are one-sided prices; MID averages both sides where available.")
    run_download = st.form_submit_button("Download XAUUSD history", type="primary")

if run_download:
    if start_date >= end_date:
        st.error("End date must be after the start date.")
    elif (end_date - start_date).days > 1096:
        st.error("For Streamlit Cloud stability, download at most 3 years per request.")
    elif symbol.strip().upper() not in ("XAUUSD", "XAU/USD", "XAU-USD"):
        st.error("The automatic Dukascopy downloader currently supports XAUUSD only. Set Symbol to XAUUSD.")
    else:
        duka = shutil.which("duka")
        if not duka:
            st.error("The Dukascopy downloader CLI is not installed. Check requirements.txt and wait for Streamlit Cloud to finish rebooting.")
        else:
            with st.spinner("Downloading and preparing historical candles. A year can take several minutes; please keep this page open…"):
                try:
                    with tempfile.TemporaryDirectory(prefix="gold_quant_") as tmp:
                        data_dir = str(Path(tmp) / "data")
                        output_path = Path(tmp) / f"XAUUSD_{output_tf}_{start_date}_{end_date}.csv"
                        base = [duka]
                        download_side = "both" if price_side == "MID" else price_side.lower()
                        download_cmd = base + ["download", "XAUUSD", "--from", start_date.isoformat(), "--to", end_date.isoformat(), "--side", download_side, "--data-dir", data_dir, "--rate", "5"]
                        dl = subprocess.run(download_cmd, capture_output=True, text=True, timeout=900)
                        if dl.returncode != 0:
                            details = (dl.stderr or dl.stdout or "Downloader returned an unknown error")[-5000:]
                            raise RuntimeError("Download command failed. " + details)
                        export_cmd = base + ["export", "XAUUSD", "--from", start_date.isoformat(), "--to", end_date.isoformat(), "--data-dir", data_dir, "--side", price_side.lower(), "--resample", output_tf, "-o", str(output_path)]
                        ex = subprocess.run(export_cmd, capture_output=True, text=True, timeout=300)
                        if ex.returncode != 0:
                            details = (ex.stderr or ex.stdout or "Exporter returned an unknown error")[-5000:]
                            raise RuntimeError("Export command failed. " + details)
                        if not output_path.exists() or output_path.stat().st_size == 0:
                            raise RuntimeError("The data provider returned no export for these dates.")
                        csv_bytes = output_path.read_bytes()
                        # Validate before making the dataset available to analysis.
                        check = pd.read_csv(output_path)
                        validated = normalize_ohlcv(check)
                        if len(validated) < 100:
                            raise RuntimeError(f"Only {len(validated)} valid candles were returned. Try a wider date range.")
                        st.session_state["downloaded_gold_csv"] = csv_bytes
                        st.session_state["downloaded_gold_name"] = output_path.name
                        st.session_state["downloaded_gold_source"] = f"Dukascopy · {price_side} · UTC · {start_date} to {end_date} · {output_tf}"
                        st.success(f"Downloaded and validated {len(validated):,} candles.")
                        st.download_button("Save downloaded CSV", data=csv_bytes, file_name=output_path.name, mime="text/csv")
                        st.caption("Source prices are Dukascopy's feed, not Pepperstone's exact quotes. The downloaded file is held in the current app session; download it to keep a copy.")
                except subprocess.TimeoutExpired:
                    st.error("Download timed out. Try a shorter date range (for example, 3–6 months) and retry.")
                except Exception as exc:
                    st.error(f"Automatic download failed: {exc}")

if "downloaded_gold_csv" in st.session_state:
    st.caption("Current downloaded dataset: " + st.session_state.get("downloaded_gold_source", "Dukascopy historical data"))
    st.download_button("Download current dataset CSV", data=st.session_state["downloaded_gold_csv"],
                       file_name=st.session_state.get("downloaded_gold_name", "xauusd_history.csv"),
                       mime="text/csv", key="download_current_csv")

st.divider()
st.subheader("2. Upload a CSV instead")
uploaded = st.file_uploader("Upload historical OHLCV CSV", type=["csv"], help="Expected columns: time/datetime/timestamp, open, high, low, close; volume optional.")
st.caption("The automatic download above can be used directly here without manually uploading the file.")
st.markdown("Expected columns: `time` (or `datetime`/`timestamp`), `open`, `high`, `low`, `close`; `volume` is optional.")

try:
    if uploaded is not None:
        raw = pd.read_csv(uploaded)
        df = add_indicators(normalize_ohlcv(raw))
        dataset_label = uploaded.name
    elif "downloaded_gold_csv" in st.session_state:
        from io import BytesIO
        raw = pd.read_csv(BytesIO(st.session_state["downloaded_gold_csv"]))
        df = add_indicators(normalize_ohlcv(raw))
        dataset_label = st.session_state.get("downloaded_gold_name", "Downloaded XAUUSD data")
    else:
        df = None

    if df is not None:
        st.subheader("3. Dataset overview")
        st.caption(f"Loaded dataset: {dataset_label}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Candles", f"{len(df):,}")
        c2.metric("From", str(df.index.min()))
        c3.metric("To", str(df.index.max()))
        c4.metric("Median range", f"{(df['high'] - df['low']).median():.3f}")
        st.line_chart(df[["close"]].tail(500), height=220)
        with st.expander("Inspect uploaded/downloaded data"):
            st.dataframe(df.tail(100), use_container_width=True)

        st.subheader("4. Specialist agents")
        if st.button("Run research agents", type="primary"):
            for item in run_research_agents(df, adx_min=adx_min):
                with st.container(border=True):
                    st.markdown(f"**{item['agent']}**")
                    st.write(item["finding"])
                    st.caption(item["caveat"])

        st.subheader("5. Opening-range breakout experiment")
        st.write("Exploratory baseline: New York 01:00–01:15 range followed by a close-confirmed breakout.")
        tz_name = st.text_input("Timezone of CSV timestamps", "UTC" if "downloaded_gold_csv" in st.session_state and uploaded is None else "America/New_York")
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
            st.warning("Candle-based research prototype, not tick-level broker simulation. If stop and target are touched in the same candle, the stop is assumed first. Verify timezone and cost units.")
            if not trades.empty:
                st.dataframe(trades, use_container_width=True)
                st.download_button("Download trade log CSV", trades.to_csv(index=False),
                                   file_name="gold_orb_trades.csv", mime="text/csv")
    else:
        st.info("Download or upload historical XAUUSD candles to begin. No fabricated example performance is shown.")
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
except Exception as exc:
    st.error(f"Could not process this dataset: {exc}")

st.divider()
st.caption(f"Build timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · No credentials should be entered into this prototype.")
