"""Transparent OHLCV indicators and exploratory opening-range breakout test."""
import numpy as np
import pandas as pd

REQUIRED = ["open","high","low","close"]

def normalize_ohlcv(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    time_col = next((c for c in ["time","datetime","timestamp","date"] if c in df.columns), None)
    if time_col is None:
        raise ValueError("CSV needs a time, datetime, timestamp or date column.")
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    for c in REQUIRED:
        if c not in df.columns:
            raise ValueError(f"Missing required column: {c}")
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df = df.dropna(subset=REQUIRED)
    if (df["high"] < df["low"]).any():
        raise ValueError("Found candles where high is below low.")
    if (df["high"] < df[["open","close"]].max(axis=1)).any() or (df["low"] > df[["open","close"]].min(axis=1)).any():
        raise ValueError("OHLC values are inconsistent.")
    return df

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    prev = out["close"].shift()
    tr = pd.concat([out["high"]-out["low"], (out["high"]-prev).abs(), (out["low"]-prev).abs()], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    up, down = out["high"].diff(), -out["low"].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    plus_di = 100 * plus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / out["atr"].replace(0,np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / out["atr"].replace(0,np.nan)
    dx = 100 * (plus_di-minus_di).abs()/(plus_di+minus_di).replace(0,np.nan)
    out["adx"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["ema50"] = out["close"].ewm(span=50, adjust=False).mean()
    return out

def run_orb_backtest(df, timezone_name="America/New_York", risk_usd=100.0,
                     target_r=2.0, adx_min=20, spread=0.0, slippage=0.0):
    """Research prototype. Three 5m candles define 01:00-01:15 NY OR.
    One trade/day, fixed normalized dollar risk. Stop wins ties within a candle.
    """
    data = df.copy()
    if data.index.tz is None:
        data.index = data.index.tz_localize(timezone_name, ambiguous="NaT", nonexistent="shift_forward")
    else:
        data.index = data.index.tz_convert(timezone_name)
    data = add_indicators(data).dropna(subset=["adx"])
    data["_day"] = data.index.date
    data["_minute"] = data.index.hour*60 + data.index.minute
    trades=[]
    for day, g in data.groupby("_day", sort=True):
        rg = g[(g["_minute"] >= 60) & (g["_minute"] < 75)]
        if len(rg) < 3:
            continue
        rh, rl = float(rg["high"].max()), float(rg["low"].min())
        after = g[g["_minute"] >= 75]
        for ts, bar in after.iterrows():
            if bar["adx"] < adx_min:
                continue
            direction = 1 if bar["close"] > rh and bar["open"] <= rh else -1 if bar["close"] < rl and bar["open"] >= rl else 0
            if not direction:
                continue
            entry = float(bar["close"]) + direction*(spread/2+slippage)
            stop = rl if direction == 1 else rh
            dist = abs(entry-stop)
            if dist <= 0:
                continue
            target = entry + direction*dist*target_r
            outcome=exit_price=exit_time=None
            for t2, b2 in g[g.index>ts].iterrows():
                stop_hit = b2["low"] <= stop if direction==1 else b2["high"] >= stop
                target_hit = b2["high"] >= target if direction==1 else b2["low"] <= target
                if stop_hit:
                    outcome, exit_price, exit_time = "stop", stop, t2
                    break
                if target_hit:
                    outcome, exit_price, exit_time = "target", target, t2
                    break
            if outcome is None:
                continue
            gross_r = (float(exit_price)-entry)*direction/dist
            net_r = gross_r - (spread+2*slippage)/dist
            trades.append({"date":str(day),"entry_time":str(ts),"exit_time":str(exit_time),
              "side":"LONG" if direction==1 else "SHORT","entry":entry,"stop":stop,"target":target,
              "exit":exit_price,"outcome":outcome,"gross_R":gross_r,"net_R_est":net_r,
              "risk_usd_assumed":risk_usd,"net_pnl_est_usd":net_r*risk_usd})
            break
    t=pd.DataFrame(trades)
    if t.empty:
        return {"trades":0,"net_pnl":0.0,"profit_factor":None,"max_drawdown":0.0}, t
    pnl=t["net_pnl_est_usd"]
    gains, losses=pnl[pnl>0].sum(), -pnl[pnl<0].sum()
    equity=pnl.cumsum()
    dd=equity.cummax()-equity
    return {"trades":int(len(t)),"net_pnl":float(pnl.sum()),
            "profit_factor":None if losses==0 else float(gains/losses),
            "max_drawdown":float(dd.max())}, t
