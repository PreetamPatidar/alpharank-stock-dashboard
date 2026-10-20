# Bharat Equity Research

A local Streamlit research app for NSE/BSE equities. It fetches prices and available company details on demand, displays technical/risk context and an explainable screening score, and writes local JSON/CSV files. It does not use a database, require an account, or place trades.

## Run locally

Python 3.10+ and internet access are required.

```powershell
cd E:\stockMarketSoftware\indian_stock_intelligence
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL Streamlit prints, choose NSE or BSE, and enter a symbol. The default file storage directory is `data/` beside the app. Set `STOCK_DATA_DIR` to change it.

## Local files

- `data/app_state.json`: watchlist, score history, alert rules, and alert events.
- `data/snapshots/<exchange>_<symbol>.json`: latest available company/quote inputs and provenance.
- `data/price_history/<exchange>_<symbol>.csv`: downloaded adjusted price history.

These are ordinary editable files. Back up the `data/` directory to preserve them. The app no longer reads the previous `bharat_equity.db` file; it is left untouched as a legacy file.

Docker Compose is optional and runs a single app container with a persistent file volume:

```powershell
docker compose up --build -d
```

## Yahoo Finance

The app requests chart and company-detail data directly from Yahoo Finance's public web endpoints. These are undocumented endpoints, and no API key is used. Yahoo's official developer API catalogue does not list a stock-price API; its documented API credentials cover other services such as Fantasy Sports and Yahoo sign-in. A Yahoo Finance market-data API key cannot be configured here because Yahoo does not document such a key for this data. [Yahoo Developer APIs](https://developer.yahoo.com/api/) · [Yahoo OAuth API requests](https://developer.yahoo.com/oauth2/guide/apirequests/)

If you have a third-party API subscription/key (for example, a marketplace vendor that republishes Yahoo Finance data), send its provider name and API documentation. The adapter must match that vendor's endpoint and terms; do not paste the secret into source files. The current Yahoo endpoints are unofficial, may change or fail, and are not approved for redistribution or public commercial use. NSE data access and distribution are subject to its subscriber agreement and data policy: [NSE Data Sharing & Usage Policy](https://www.nseindia.com/static/market-data/nse-data-policy).

## Limitations

The score and scenario ranges are experimental research aids, not investment recommendations or validated forecasts. This local single-user version has no authentication, scheduled refresh, email alerts, licensed data feed, or multi-user isolation. Keep it on a trusted machine; obtain licensed data and review applicable requirements before public distribution.
