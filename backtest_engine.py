"""Transparent candle-based EMA cross backtest; analysis only."""
import pandas as pd
import numpy as np
from quant_engine import normalize_ohlcv, add_indicators

def backtest_ema_cross(raw, initial_cash=10000.0, risk_pct=0.25, stop_atr=2.0,
                       target_r=2.0, fee_bps=2.0, slippage_bps=3.0):
    """Long-only EMA20/50 cross. Conservative stop-first same-bar handling.
    Entry next bar open, ATR stop, target R, end-of-data liquidation, costs on fills.
    Fractional quantity is for research only; no live order recommendation.
    """
    if not 0 < risk_pct <= 2: raise ValueError("risk_pct must be >0 and <=2.")
    df=add_indicators(normalize_ohlcv(raw))
    df["fast"]=df.close.ewm(span=20,adjust=False).mean()
    df["slow"]=df.close.ewm(span=50,adjust=False).mean()
    cash=float(initial_cash); pos=None; trades=[]; equity=[]
    for i in range(1,len(df)):
        prev,bar=df.iloc[i-1],df.iloc[i]; ts=df.index[i]
        if pos:
            stop_hit=bar.low<=pos["stop"]; target_hit=bar.high>=pos["target"]
            reason=None
            if stop_hit: exit_price,reason=pos["stop"],"stop"
            elif target_hit: exit_price,reason=pos["target"],"target"
            elif i==len(df)-1: exit_price,reason=float(bar.close),"end_of_data"
            if reason:
                fill=exit_price*(1-slippage_bps/10000)
                gross=(fill-pos["entry"])*pos["qty"]
                fees=(pos["entry"]*pos["qty"]+fill*pos["qty"])*fee_bps/10000
                pnl=gross-fees-pos["entry"]*pos["qty"]*slippage_bps/10000
                cash+=pnl
                trades.append({"entry_time":str(pos["entry_time"]),"exit_time":str(ts),"entry":pos["entry"],
                    "exit":fill,"stop":pos["stop"],"target":pos["target"],"qty":pos["qty"],
                    "reason":reason,"pnl":pnl,"risk_dollars":pos["risk_dollars"]})
                pos=None
        cross=prev.fast<=prev.slow and bar.fast>bar.slow
        if pos is None and cross and i<len(df)-1 and pd.notna(bar.atr) and bar.atr>0:
            entry=float(df.iloc[i+1].open)*(1+slippage_bps/10000)
            stop=entry-float(bar.atr)*stop_atr; rps=entry-stop
            risk=cash*risk_pct/100; qty=min(risk/rps,max(cash,0)/max(entry,1e-12))
            if qty>0 and rps>0:
                pos={"entry":entry,"entry_time":df.index[i+1],"stop":stop,"target":entry+rps*target_r,
                     "qty":qty,"risk_dollars":risk}
        equity.append({"time":str(ts),"equity":cash})
    t=pd.DataFrame(trades)
    if t.empty: return {"trades":0,"net_pnl":0.0,"win_rate_pct":0.0,"profit_factor":None,"max_drawdown":0.0,"final_equity":cash},t,pd.DataFrame(equity)
    pnl=t.pnl; gains=float(pnl[pnl>0].sum()); losses=float(-pnl[pnl<0].sum())
    eq=float(initial_cash)+pnl.cumsum(); dd=eq.cummax()-eq
    return {"trades":len(t),"net_pnl":float(pnl.sum()),"win_rate_pct":float((pnl>0).mean()*100),
      "profit_factor":None if losses==0 else gains/losses,"max_drawdown":float(dd.max()),
      "final_equity":float(initial_cash+pnl.sum()),"cost_model":"fee and slippage basis points"},t,pd.DataFrame(equity)
