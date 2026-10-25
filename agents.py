"""Deterministic research-agent summaries. Not predictive guarantees."""
import numpy as np
import pandas as pd

def run_research_agents(df: pd.DataFrame, adx_min: int = 20):
    if len(df) < 30:
        return [{"agent":"Data quality agent","finding":"Not enough candles for meaningful indicator summaries.","caveat":"Upload more historical data before research."}]
    last = df.iloc[-1]
    close = float(last["close"])
    atr = float(last["atr"]) if pd.notna(last.get("atr")) else np.nan
    adx = float(last["adx"]) if pd.notna(last.get("adx")) else np.nan
    ema20 = float(last["ema20"]) if pd.notna(last.get("ema20")) else np.nan
    ema50 = float(last["ema50"]) if pd.notna(last.get("ema50")) else np.nan
    return [
      {"agent":"Price-action agent","finding":f"Latest close {close:.3f}; recent 20-candle high {df['high'].tail(20).max():.3f}; low {df['low'].tail(20).min():.3f}.","caveat":"Descriptive structure is not a signal by itself."},
      {"agent":"Quant / volatility agent","finding":f"Latest ATR(14): {atr:.4f}; ADX(14): {adx:.2f}. "+("ADX is at/above the selected threshold." if np.isfinite(adx) and adx >= adx_min else "ADX is below the threshold or unavailable."),"caveat":"ADX measures trend strength, not direction or probability of profit."},
      {"agent":"Trend agent","finding":f"Close {close:.3f}; EMA(20) {ema20:.3f}; EMA(50) {ema50:.3f}.","caveat":"Moving averages lag and require empirical validation."},
      {"agent":"Volatility-regime agent","finding":f"Latest candle range {float(last['high']-last['low']):.3f}; median range over latest 100 candles {(df['high']-df['low']).tail(100).median():.3f}.","caveat":"Large candles may represent opportunity or event risk."},
      {"agent":"Risk agent","finding":"No trade approved. Risk sizing needs entry, stop distance, contract specification and account constraints.","caveat":"No broker-specific lot sizing or order placement is enabled."},
      {"agent":"News agent","finding":"No timestamped news feed is connected.","caveat":"Do not invent headlines or allow future-news leakage in historical tests."}
    ]
