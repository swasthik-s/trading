# Gold Quant Desk

A Streamlit research lab for studying XAUUSD with specialist, evidence-based research modules.

## Deploy on Streamlit Community Cloud
1. Open https://share.streamlit.io/
2. Select **New app**.
3. Choose repository `swasthik-s/trading`, branch `main`, entry point `app.py`.
4. Deploy.

## Included
- Upload historical OHLCV CSV
- ATR(14), ADX(14), EMA(20), EMA(50)
- Price-action, quant/volatility, trend, news-status and risk research agents
- Exploratory 01:00-01:15 New York opening-range breakout experiment
- Downloadable trade log

CSV columns: `time` (or `datetime`, `timestamp`, `date`), `open`, `high`, `low`, `close`; optional `volume`.

## Important limitations
This is a research prototype only. It does not place orders or connect to a broker. The news agent has no live feed. The candle-based backtest is not tick-accurate and cannot faithfully model broker spreads, contract sizing, swaps, latency or slippage. Validate timestamp timezone, data quality and costs before interpreting results. In the backtest, risk is a normalized dollar assumption, not Pepperstone lot sizing. Stop is assumed hit first if stop and target are touched in the same bar.

Streamlit Community Cloud can sleep; it should not be relied on for guaranteed continuous monitoring or trading. Add a persistent worker only after research validation.

Never commit API keys, broker credentials or secrets.
