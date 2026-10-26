"""Alpaca paper-only adapter. All order submission is hard-pinned to paper-api."""
import os
import pandas as pd

PAPER_URL = "https://paper-api.alpaca.markets"

def secret(name):
    try:
        import streamlit as st
        value = st.secrets.get(name, None)
        if value: return str(value).strip()
    except Exception: pass
    return os.getenv(name, "").strip()

def credentials():
    return secret("ALPACA_API_KEY"), secret("ALPACA_SECRET_KEY")

def clients():
    key, sec = credentials()
    if not key or not sec:
        raise RuntimeError("Add paper-account ALPACA_API_KEY and ALPACA_SECRET_KEY to Streamlit Secrets.")
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.trading.client import TradingClient
    return TradingClient(key, sec, paper=True), StockHistoricalDataClient(key, sec)

def account_snapshot():
    trade, _ = clients()
    a, c = trade.get_account(), trade.get_clock()
    return {"account":{"status":str(a.status),"cash":float(a.cash),"equity":float(a.equity),
        "buying_power":float(a.buying_power),"trading_blocked":bool(a.trading_blocked)},
        "clock":{"is_open":bool(c.is_open),"next_open":str(c.next_open),"next_close":str(c.next_close)},
        "positions":[{"symbol":p.symbol,"qty":float(p.qty),"side":str(p.side),
          "market_value":float(p.market_value),"avg_entry_price":float(p.avg_entry_price),
          "unrealized_pl":float(p.unrealized_pl)} for p in trade.get_all_positions()],
        "orders":[{"id":str(o.id),"symbol":o.symbol,"side":str(o.side),"qty":str(o.qty),
          "type":str(o.type),"status":str(o.status),"submitted_at":str(o.submitted_at)}
          for o in trade.get_orders()[:100]]}

def get_assets(limit=10000):
    trade, _ = clients()
    assets = trade.get_all_assets()
    rows=[]
    for a in assets:
        if str(a.status).lower().endswith("active") and a.tradable and str(a.asset_class).lower().endswith("us_equity"):
            rows.append({"symbol":a.symbol,"name":a.name,"exchange":str(a.exchange),
              "tradable":bool(a.tradable),"fractionable":bool(getattr(a,"fractionable",False)),
              "shortable":bool(getattr(a,"shortable",False))})
    return (pd.DataFrame(rows).drop_duplicates("symbol").sort_values("symbol").head(int(limit))
            if rows else pd.DataFrame())

def historical_bars(symbols, start, end, timeframe="5Min", feed="iex"):
    _, data=clients()
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    tfs={"1Min":TimeFrame.Minute,"5Min":TimeFrame(5,TimeFrameUnit.Minute),
         "15Min":TimeFrame(15,TimeFrameUnit.Minute),"1Hour":TimeFrame.Hour,"1Day":TimeFrame.Day}
    if timeframe not in tfs: raise ValueError("Unsupported timeframe.")
    syms=[str(s).strip().upper() for s in symbols if str(s).strip()]
    if not syms: raise ValueError("Provide at least one symbol.")
    req=StockBarsRequest(symbol_or_symbols=syms,timeframe=tfs[timeframe],start=start,end=end,feed=feed,limit=10000)
    result=data.get_stock_bars(req).df
    if result is None or result.empty:
        return pd.DataFrame(columns=["timestamp","symbol","open","high","low","close","volume"])
    result=result.reset_index()
    result.columns=[str(c).lower() for c in result.columns]
    return result[["timestamp","symbol","open","high","low","close","volume"]].sort_values(["symbol","timestamp"])

def scan_snapshots(limit=100, feed="iex"):
    """Rank active/tradable assets by latest daily dollar volume; broad-universe scan."""
    _, data=clients()
    assets=get_assets(10000)
    if assets.empty: return pd.DataFrame()
    syms=assets.symbol.tolist()
    rows=[]
    from alpaca.data.requests import StockSnapshotRequest
    for i in range(0,len(syms),200):
        try: snaps=data.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=syms[i:i+200],feed=feed))
        except Exception: continue
        for symbol,snap in snaps.items():
            bar=getattr(snap,"daily_bar",None); prev=getattr(snap,"prev_daily_bar",None)
            if bar is None or not getattr(bar,"close",None): continue
            close=float(bar.close); pc=float(prev.close) if prev is not None and getattr(prev,"close",None) else None
            volume=float(getattr(bar,"volume",0) or 0)
            rows.append({"symbol":symbol,"price":close,"volume":volume,"dollar_volume":close*volume,
              "change_pct":((close/pc)-1)*100 if pc else None})
    out=pd.DataFrame(rows)
    return out.sort_values("dollar_volume",ascending=False).head(int(limit)).reset_index(drop=True) if not out.empty else out

def submit_paper_market_order(symbol, side, qty, max_notional, approved):
    """Paper-only market order with explicit approval, notional cap, and tradability checks."""
    if not approved: raise RuntimeError("Blocked: explicit approval is required.")
    if PAPER_URL != "https://paper-api.alpaca.markets": raise RuntimeError("Paper endpoint safety check failed.")
    symbol=str(symbol).strip().upper(); side=str(side).strip().lower(); qty=float(qty)
    if not symbol.isalnum() or side not in {"buy","sell"} or qty<=0: raise ValueError("Invalid symbol, side or quantity.")
    if qty>10000: raise ValueError("Hard quantity cap is 10,000 shares.")
    trade,data=clients()
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.data.requests import StockSnapshotRequest
    asset=trade.get_asset(symbol)
    if not asset.tradable or not str(asset.asset_class).lower().endswith("us_equity"):
        raise RuntimeError("Blocked: asset is not a tradable US equity.")
    snap=data.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=[symbol],feed="iex"))[symbol]
    last=getattr(getattr(snap,"latest_trade",None),"price",None) or getattr(getattr(snap,"daily_bar",None),"close",None)
    if not last: raise RuntimeError("Blocked: no current price available.")
    notional=float(last)*qty
    if notional>float(max_notional): raise RuntimeError("Blocked: estimated notional exceeds configured cap.")
    if trade.get_account().trading_blocked: raise RuntimeError("Blocked: account is trading-blocked.")
    req=MarketOrderRequest(symbol=symbol,qty=qty,side=OrderSide.BUY if side=="buy" else OrderSide.SELL,time_in_force=TimeInForce.DAY)
    o=trade.submit_order(order_data=req)
    return {"id":str(o.id),"symbol":symbol,"side":side,"qty":qty,"estimated_notional":notional,
      "status":str(o.status),"paper_endpoint":PAPER_URL}
