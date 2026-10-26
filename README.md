# Quant Desk

Streamlit research dashboard with an Alpaca US-stock workspace and a separate research-only XAUUSD workspace.

## Alpaca paper trading setup
Deploy this repository to Streamlit Community Cloud. In App Settings > Secrets add:
```toml
ALPACA_API_KEY = "YOUR_PAPER_KEY"
ALPACA_SECRET_KEY = "YOUR_PAPER_SECRET"
```
Use paper-account keys only. The trading client is instantiated with `paper=True`; live-money execution is not implemented.

## Features
- Broad active/tradable US-equity scanner ranked by daily dollar volume.
- Historical stock bars with symbol, timeframe and feed selection.
- Example EMA20/EMA50 backtest with ATR stop, target-R, next-bar entry, stop-first same-candle handling, end-of-data liquidation and configurable fee/slippage assumptions.
- Paper account equity, cash, buying power, positions and orders.
- Explicitly approved paper market order ticket with tradability checks and notional cap.
- Existing XAUUSD research workspace remains separate.

## Limitations
Broad scans may take time and depend on Alpaca API/data entitlements. IEX and SIP feed access differ by plan. The example strategy is not a proven edge; candle data cannot resolve intrabar paths, and all results need out-of-sample validation. Paper trading is simulated. Streamlit Cloud may sleep, so it is not a persistent trading worker.

## Day Trader Skill attribution
Concepts adapted from [Jake Schincariol's Day Trader Skill](https://github.com/Jakeschincariol/day-trader-skill), MIT License. License text preserved at `THIRD_PARTY_LICENSES/Jake-Schincariol-Day-Trader-Skill-MIT.txt`.
