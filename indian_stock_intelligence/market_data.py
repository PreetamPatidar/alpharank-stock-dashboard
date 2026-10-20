"""Direct Yahoo Finance HTTP adapter. No yfinance cache or SQL database used."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import numpy as np
import pandas as pd
import requests

SOURCE = "Yahoo Finance public chart and quote endpoints (unofficial; no API key)"
TIMEOUT_SECONDS = 20


def normalize_symbol(symbol: str, exchange: str) -> str:
    clean = symbol.strip().upper()
    for suffix in (".NS", ".BO"):
        if clean.endswith(suffix):
            clean = clean[:-len(suffix)]
    if not clean or not clean.replace("&", "").replace("-", "").replace("_", "").isalnum():
        raise ValueError("Enter a valid exchange symbol, for example RELIANCE or TCS.")
    if exchange not in {"NSE", "BSE"}:
        raise ValueError("Choose NSE or BSE.")
    return clean + (".NS" if exchange == "NSE" else ".BO")


def _request_yahoo_payload(ticker: str) -> tuple[requests.Session, dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"})
    chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    try:
        response = session.get(chart_url, params={"range": "5y", "interval": "1d", "events": "div,splits"}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json().get("chart", {})
        result = payload.get("result")
        if not result:
            detail = (payload.get("error") or {}).get("description") or "No matching instrument or history was returned."
            raise ValueError(f"Yahoo Finance returned no data for {ticker}: {detail}")
        return session, result[0]
    except requests.RequestException as exc:
        raise ConnectionError(f"Could not reach Yahoo Finance for {ticker}: {exc}") from exc


def _get_raw(module: dict, field: str) -> Any:
    value = module.get(field)
    if isinstance(value, dict) and "raw" in value:
        return value["raw"]
    return value


def _fundamentals(session: requests.Session, ticker: str) -> tuple[dict, str | None]:
    """Query the unofficial quoteSummary endpoint with a short-lived in-memory crumb."""
    try:
        # Yahoo currently requires a cookie/crumb for this unofficial endpoint.
        try:
            session.get("https://fc.yahoo.com", timeout=TIMEOUT_SECONDS)
        except requests.RequestException:
            pass
        session.get(f"https://finance.yahoo.com/quote/{ticker}", timeout=TIMEOUT_SECONDS)
        crumb_response = session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=TIMEOUT_SECONDS)
        crumb_response.raise_for_status()
        crumb = crumb_response.text.strip()
        if not crumb:
            return {}, "Yahoo did not return an authentication crumb; fundamentals are unavailable."
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
        response = session.get(url, params={"modules": "price,summaryDetail,defaultKeyStatistics,financialData,assetProfile", "crumb": crumb}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        result = (response.json().get("quoteSummary", {}).get("result") or [None])[0]
        if not result:
            return {}, "Yahoo returned no company-detail modules; fundamentals are unavailable."
        price = result.get("price", {})
        summary = result.get("summaryDetail", {})
        stats = result.get("defaultKeyStatistics", {})
        financial = result.get("financialData", {})
        profile = result.get("assetProfile", {})
        fields = {
            "longName": price.get("longName"), "shortName": price.get("shortName"),
            "currency": _get_raw(price, "currency"), "marketCap": _get_raw(price, "marketCap"),
            "trailingPE": _get_raw(summary, "trailingPE"), "forwardPE": _get_raw(summary, "forwardPE"),
            "priceToBook": _get_raw(stats, "priceToBook"), "beta": _get_raw(stats, "beta"),
            "dividendYield": _get_raw(summary, "dividendYield"),
            "returnOnEquity": _get_raw(financial, "returnOnEquity") or _get_raw(stats, "returnOnEquity"),
            "revenueGrowth": _get_raw(financial, "revenueGrowth"),
            "earningsGrowth": _get_raw(financial, "earningsGrowth"),
            "operatingMargins": _get_raw(financial, "operatingMargins"),
            "profitMargins": _get_raw(financial, "profitMargins"),
            "debtToEquity": _get_raw(financial, "debtToEquity"),
            "totalDebt": _get_raw(financial, "totalDebt"), "totalCash": _get_raw(financial, "totalCash"),
            "freeCashflow": _get_raw(financial, "freeCashflow"),
            "operatingCashflow": _get_raw(financial, "operatingCashflow"),
            "totalRevenue": _get_raw(financial, "totalRevenue"),
            "sector": profile.get("sector"), "industry": profile.get("industry"),
        }
        return {k: v for k, v in fields.items() if v is not None}, None
    except (requests.RequestException, ValueError) as exc:
        return {}, f"Company-detail endpoint unavailable ({exc}); analysis will show missing fundamentals."


def load_security(symbol: str, exchange: str) -> dict:
    ticker = normalize_symbol(symbol, exchange)
    session, chart = _request_yahoo_payload(ticker)
    timestamps = chart.get("timestamp") or []
    quote = (chart.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = (chart.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") or quote.get("close") or []
    if not timestamps or not adjusted:
        raise ValueError(f"Yahoo Finance returned no usable closing prices for {ticker}.")
    count = min(len(timestamps), len(adjusted))
    index = pd.to_datetime(timestamps[:count], unit="s", utc=True).tz_convert("Asia/Kolkata")
    hist = pd.DataFrame({
        "Open": (quote.get("open") or [None] * count)[:count],
        "High": (quote.get("high") or [None] * count)[:count],
        "Low": (quote.get("low") or [None] * count)[:count],
        "Close": adjusted[:count],
        "Volume": (quote.get("volume") or [None] * count)[:count],
    }, index=index).dropna(subset=["Close"])
    if hist.empty:
        raise ValueError(f"Yahoo Finance returned no valid price observations for {ticker}.")

    info, fundamental_warning = _fundamentals(session, ticker)
    session.close()
    closes = hist["Close"].astype(float)
    returns = closes.pct_change().dropna()
    rolling20, rolling50, rolling200 = (closes.rolling(n).mean() for n in (20, 50, 200))
    latest = float(closes.iloc[-1])
    trailing_returns = returns.tail(252)
    volatility = float(trailing_returns.std() * np.sqrt(252)) if len(trailing_returns) > 1 else None
    drawdown = closes / closes.cummax() - 1
    drawdown_1y = float(drawdown.tail(252).min()) if len(drawdown) else None
    return_6m = float(latest / closes.iloc[max(0, len(closes) - 126)] - 1) if len(closes) > 1 else None

    delta = closes.diff()
    average_gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    average_loss = -delta.clip(upper=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    rsi = float(100 - 100 / (1 + relative_strength.iloc[-1])) if pd.notna(relative_strength.iloc[-1]) else None

    ma20 = float(rolling20.iloc[-1]) if len(closes) >= 20 else None
    ma50 = float(rolling50.iloc[-1]) if len(closes) >= 50 else None
    ma200 = float(rolling200.iloc[-1]) if len(closes) >= 200 else None
    momentum = None
    if ma200 is not None and ma20 is not None and ma50 is not None:
        momentum = (50 if latest > ma20 else 0) + (50 if latest > ma50 > ma200 else (25 if latest > ma200 else 0))

    meta = chart.get("meta", {})
    info.setdefault("longName", meta.get("longName"))
    info.setdefault("shortName", meta.get("shortName"))
    info.setdefault("currency", meta.get("currency", "INR"))
    info.setdefault("sector", info.get("industry", "Not reported"))
    technical = {"current_price": latest, "ma20": ma20, "ma50": ma50, "ma200": ma200,
        "rsi14": rsi, "annualized_volatility": volatility, "max_drawdown_1y": drawdown_1y,
        "return_6m": return_6m, "momentum_score": momentum}
    market_timestamp = hist.index[-1]
    retrieved_at = datetime.now(timezone.utc)
    warnings = [x for x in (fundamental_warning,) if x]
    return {"symbol": ticker, "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector") or info.get("industry") or "Not reported",
        "currency": info.get("currency") or "INR", "info": info, "history": hist,
        "technical": technical, "retrieved_at": retrieved_at, "market_timestamp": market_timestamp,
        "observations": len(hist), "source": SOURCE, "warnings": warnings}
