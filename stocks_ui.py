import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from backtest_engine import backtest_ema_cross

def render_stock_workspace():
    st.header("US Stocks - Alpaca paper trading")
    st.caption("Paper account only. Live-money execution is not implemented.")
    from alpaca_engine import credentials
    if not all(credentials()):
        st.warning("Add paper-account keys in Streamlit Cloud Settings > Secrets.")
        st.code('ALPACA_API_KEY = "YOUR_PAPER_KEY"\nALPACA_SECRET_KEY = "YOUR_PAPER_SECRET"',language="toml")
        return
    t=st.tabs(["Account","Broad scanner","Backtest","Paper order"])
    with t[0]:
        if st.button("Refresh paper account"):
            try:
                from alpaca_engine import account_snapshot
                st.session_state["stock_account"]=account_snapshot()
            except Exception as e: st.error(str(e))
        snap=st.session_state.get("stock_account")
        if snap:
            a=snap["account"]; c=snap["clock"]
            x,y,z,w=st.columns(4)
            x.metric("Paper equity","USD "+format(a["equity"],",.2f"))
            y.metric("Cash","USD "+format(a["cash"],",.2f"))
            z.metric("Buying power","USD "+format(a["buying_power"],",.2f"))
            w.metric("Market","OPEN" if c["is_open"] else "CLOSED")
            st.caption("Status: "+a["status"]+" · Next open "+c["next_open"]+" · Next close "+c["next_close"])
            st.subheader("Positions"); st.dataframe(pd.DataFrame(snap["positions"]),use_container_width=True)
            st.subheader("Recent orders"); st.dataframe(pd.DataFrame(snap["orders"]),use_container_width=True)
    with t[1]:
        st.write("Active tradable US equities ranked by daily dollar volume. Snapshot coverage depends on data entitlement.")
        lim=st.selectbox("Display candidates",[25,50,100,200],index=1)
        feed=st.selectbox("Market data feed",["iex","sip"])
        if st.button("Scan broad US market",type="primary"):
            try:
                from alpaca_engine import scan_snapshots
                with st.spinner("Loading assets and requesting snapshots…"):
                    st.session_state["stock_scan"]=scan_snapshots(lim,feed)
                st.session_state["stock_scan_feed"]=feed
            except Exception as e: st.error("Scan failed: "+str(e))
        scan=st.session_state.get("stock_scan")
        if scan is not None:
            st.dataframe(scan,use_container_width=True,hide_index=True)
            if not scan.empty: st.download_button("Download scan CSV",scan.to_csv(index=False),"alpaca_scan.csv","text/csv")
            st.caption("Feed: "+st.session_state.get("stock_scan_feed","iex")+"; candidates are not signals.")
    with t[2]:
        with st.form("stock_hist"):
            symbols=st.text_input("Symbols, up to 25, comma-separated","AAPL,MSFT,NVDA,SPY")
            a,b,c=st.columns(3)
            start=a.date_input("Start date",datetime.now(timezone.utc).date()-timedelta(days=180))
            end=b.date_input("End date",datetime.now(timezone.utc).date()-timedelta(days=1))
            tf=c.selectbox("Timeframe",["5Min","15Min","1Hour","1Day"],index=3)
            feed=st.selectbox("Historical feed",["iex","sip"],key="hist_feed")
            fetch=st.form_submit_button("Fetch historical bars")
        if fetch:
            if start>=end: st.error("End date must be after start date.")
            else:
                try:
                    from alpaca_engine import historical_bars
                    syms=list(dict.fromkeys(s.strip().upper() for s in symbols.split(",") if s.strip()))[:25]
                    bars=historical_bars(syms,datetime.combine(start,datetime.min.time(),tzinfo=timezone.utc),datetime.combine(end,datetime.max.time(),tzinfo=timezone.utc),tf,feed)
                    st.session_state["stock_bars"]=bars
                    st.success("Fetched "+format(len(bars),",")+" bars.")
                except Exception as e: st.error("Historical fetch failed: "+str(e))
        bars=st.session_state.get("stock_bars")
        if bars is not None and not bars.empty:
            sym=st.selectbox("Backtest symbol",sorted(bars.symbol.unique()))
            raw=bars[bars.symbol==sym].rename(columns={"timestamp":"time"})
            st.line_chart(raw.set_index("time")[["close"]],height=180)
            with st.form("stock_bt"):
                a,b,c=st.columns(3)
                cash=a.number_input("Initial equity USD",100.0,10000000.0,10000.0,1000.0)
                risk=b.number_input("Risk percent",0.01,2.0,0.25,0.05)
                atr=c.number_input("Stop ATR",0.25,10.0,2.0,0.25)
                d,e,f=st.columns(3)
                rr=d.number_input("Target R",0.25,10.0,2.0,0.25)
                fee=e.number_input("Fees bps per side",0.0,100.0,2.0,0.5)
                slip=f.number_input("Slippage bps per side",0.0,100.0,3.0,0.5)
                run=st.form_submit_button("Run EMA crossover backtest",type="primary")
            if run:
                try:
                    stats,trades,_=backtest_ema_cross(raw,cash,risk,atr,rr,fee,slip)
                    a,b,c,d=st.columns(4)
                    a.metric("Trades",stats["trades"]); b.metric("Net P&L","USD "+format(stats["net_pnl"],",.2f"))
                    c.metric("Win rate",format(stats["win_rate_pct"],".1f")+"%"); d.metric("Max drawdown","USD "+format(stats["max_drawdown"],",.2f"))
                    st.warning("Example strategy only, not a validated edge. Stop-first assumed if both stop and target touch in one candle. Validate out of sample.")
                    st.dataframe(trades,use_container_width=True)
                    if not trades.empty: st.download_button("Download trade log",trades.to_csv(index=False),"stock_backtest_trades.csv","text/csv")
                except Exception as e: st.error("Backtest failed: "+str(e))
    with t[3]:
        st.warning("This submits a simulated order to the paper account only.")
        with st.form("paper_order"):
            a,b,c=st.columns(3)
            symbol=a.text_input("Ticker","SPY").strip().upper()
            side=b.selectbox("Side",["buy","sell"])
            qty=c.number_input("Shares",0.001,10000.0,1.0,1.0)
            cap=st.number_input("Maximum estimated notional USD",1.0,100000.0,500.0,50.0)
            approved=st.checkbox("I confirm this is a paper order and checked ticker, side and quantity.")
            submit=st.form_submit_button("Submit PAPER order")
        if submit:
            try:
                from alpaca_engine import submit_paper_market_order
                result=submit_paper_market_order(symbol,side,qty,cap,approved)
                st.success("Paper order submitted: "+result["id"]+" · "+side+" "+str(qty)+" "+symbol)
                st.json(result)
            except Exception as e: st.error("Order blocked or failed: "+str(e))
