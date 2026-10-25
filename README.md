# Gold Quant Desk

A Streamlit research lab for studying XAUUSD. Research-only: no broker connection or live order placement.

## Deploy on Streamlit Community Cloud
1. Open https://share.streamlit.io/
2. Choose repository `swasthik-s/trading`, branch `main`, entry file `app.py`.
3. If you already deployed it, Streamlit should detect the commit and rebuild because `requirements.txt` changed. Check **Manage app → Logs** if the build fails.

## Automatic historical data download
The dashboard uses the `dukascopy-downloader` package to download public Dukascopy historical XAUUSD data, then exports it as CSV:
- Choose a UTC start/end date and output timeframe.
- Default timeframe is 5 minutes; output options include 1m, 5m, 15m, 30m, 1h and 4h.
- The download is limited to 3 years per request to reduce Streamlit Cloud timeout risk.
- A completed file can be downloaded to your own device and is also loaded into the current app session.
- If a download times out, retry a shorter period (e.g. 3–6 months).

Dukascopy data is not identical to Pepperstone quotes. Keep the source, price side and timezone with any backtest. The downloader may be throttled or temporarily unavailable.

## Manual CSV format
Required columns: `time` (or `datetime`, `timestamp`, `date`), `open`, `high`, `low`, `close`; optional `volume`.

## Included research features
- ATR(14), ADX(14), EMA(20), EMA(50)
- Price-action, quant/volatility, trend, news-status and risk summaries
- Exploratory 01:00–01:15 New York opening-range breakout experiment
- Downloadable trade log

## Important limitations
This is a research prototype only. It does not place orders or connect to a broker. The news agent has no live feed. The candle-based backtest is not tick-accurate and cannot faithfully model broker spreads, contract sizing, swaps, latency or slippage. Validate timestamp timezone, data quality and costs before interpreting results. In the backtest, risk is a normalized dollar assumption, not Pepperstone lot sizing. Stop is assumed hit first if stop and target are touched in the same bar.

Streamlit Community Cloud can sleep; it should not be relied on for guaranteed continuous monitoring or trading. Never commit API keys, broker credentials or secrets.
