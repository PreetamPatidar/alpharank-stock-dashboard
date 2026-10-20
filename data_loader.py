"""
Data Fetching Module for Multi-Factor Stock Analysis using yfinance
Supports Global (US) and Indian (NSE & BSE) Equities.
Provides parallelized multi-threaded batch fetching, local disk caching,
and pre-built indices (Nifty 50, Nifty 500, Sensex, Sectoral, and full NSE Master directory).
"""

import os
import json
import time
from typing import Dict, List, Tuple, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf
import pandas as pd
import numpy as np

# Cache directory & file
CACHE_DIR = os.path.join(os.path.dirname(__file__), "data")
CACHE_FILE = os.path.join(CACHE_DIR, "metrics_cache.json")
CACHE_TTL_SECONDS = 12 * 3600  # 12 hours cache


# SENSEX 30 constituents
SENSEX_30_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "ITC", "SBIN",
    "LT", "HINDUNILVR", "AXISBANK", "KOTAKBANK", "BAJFINANCE", "MARUTI", "TITAN",
    "SUNPHARMA", "TATASTEEL", "TATAMOTORS", "NTPC", "POWERGRID", "ULTRACEMCO",
    "ASIANPAINT", "M&M", "HCLTECH", "TECHM", "INDUSINDBK", "BAJAJFINSV", "NESTLEIND",
    "JSWSTEEL", "WIPRO"
]

GLOBAL_WATCHLISTS = {
    "🇺🇸 Magnificent Seven": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
    "🇺🇸 S&P 500 Tech Leaders": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "ADBE", "INTC", "CSCO"],
    "🇺🇸 Dow Jones Top Picks": ["JNJ", "PG", "JPM", "V", "UNH", "HD", "MCD", "WMT", "CAT", "BA"],
    "🇺🇸 Semiconductor Titans": ["NVDA", "TSM", "ASML", "AVGO", "AMD", "QCOM", "TXN", "INTC", "MU", "ARM"],
    "🇺🇸 EV & Clean Mobility": ["TSLA", "RIVN", "LCID", "NIO", "BYDDY", "F", "GM", "TM"],
    "🇺🇸 High Dividend Aristocrats": ["PG", "KO", "PEP", "ABBV", "CVX", "XOM", "O", "T", "VZ", "BMY"],
}


def load_master_nse_directory() -> pd.DataFrame:
    """
    Loads all registered NSE listed companies (~2,619 stocks) from local CSV.
    """
    csv_path = os.path.join(CACHE_DIR, "nse_master.csv")
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            return df
        except Exception as e:
            print(f"Error reading nse_master.csv: {e}")
            
    return pd.DataFrame(columns=["symbol", "company_name", "series", "nse_ticker", "bse_ticker"])


def load_index_tickers(filename: str, exchange: str = "NSE") -> List[str]:
    """
    Helper to load ticker list from index CSV files in data/
    """
    csv_path = os.path.join(CACHE_DIR, filename)
    col = "nse_ticker" if exchange.upper() == "NSE" else "bse_ticker"
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            if col in df.columns:
                return df[col].dropna().tolist()
            elif "Symbol" in df.columns:
                suffix = ".NS" if exchange.upper() == "NSE" else ".BO"
                return (df["Symbol"].str.strip() + suffix).tolist()
        except Exception as e:
            print(f"Error loading {filename}: {e}")
    return []


def get_available_watchlists(exchange: str = "NSE") -> Dict[str, List[str]]:
    """
    Returns comprehensive watchlist mapping based on exchange preference.
    """
    suffix = ".NS" if exchange.upper() == "NSE" else ".BO"
    
    indian_watchlists = {
        "🇮🇳 NIFTY 50 (India Benchmark)": load_index_tickers("nifty50.csv", exchange),
        "🇮🇳 BSE SENSEX 30 (Top Bluechips)": [f"{sym}{suffix}" for sym in SENSEX_30_SYMBOLS],
        "🇮🇳 NIFTY Next 50 (Emerging Bluechips)": load_index_tickers("nifty_next50.csv", exchange),
        "🇮🇳 NIFTY Bank Leaders": load_index_tickers("nifty_bank.csv", exchange),
        "🇮🇳 NIFTY IT Leaders": load_index_tickers("nifty_it.csv", exchange),
        "🇮🇳 NIFTY Auto Leaders": load_index_tickers("nifty_auto.csv", exchange),
        "🇮🇳 NIFTY Pharma Leaders": load_index_tickers("nifty_pharma.csv", exchange),
        "🇮🇳 NIFTY FMCG Leaders": load_index_tickers("nifty_fmcg.csv", exchange),
        "🇮🇳 NIFTY Energy Leaders": load_index_tickers("nifty_energy.csv", exchange),
        "🇮🇳 NIFTY Metal Leaders": load_index_tickers("nifty_metal.csv", exchange),
        "🇮🇳 NIFTY Midcap 150": load_index_tickers("nifty_midcap150.csv", exchange),
        "🇮🇳 NIFTY 500 (Broad Market Top 500)": load_index_tickers("nifty500.csv", exchange),
    }
    
    # Filter out any empty lists
    clean_indian = {k: v for k, v in indian_watchlists.items() if v}
    
    # Combined with global
    combined = {**clean_indian, **GLOBAL_WATCHLISTS}
    return combined


# Backward compatibility
WATCHLISTS = get_available_watchlists("NSE")


def _read_disk_cache() -> Dict[str, Any]:
    """Reads persistent cache from disk."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _write_disk_cache(cache_data: Dict[str, Any]):
    """Writes persistent cache to disk safely."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f)
    except Exception as e:
        print(f"Cache write error: {e}")


def format_ticker_symbol(symbol: str, default_exchange: str = "NSE") -> str:
    """
    Standardizes ticker symbol with appropriate exchange suffix.
    E.g. 'RELIANCE' -> 'RELIANCE.NS' (for NSE) or 'RELIANCE.BO' (for BSE).
    Leaves symbols that already have suffixes (like .NS, .BO) untouched.
    """
    clean = symbol.strip().upper()
    if not clean:
        return ""
    if "." in clean:
        return clean  # already has suffix
        
    # Check if it's an Indian symbol or user specified exchange
    if default_exchange.upper() == "BSE":
        return f"{clean}.BO"
    elif default_exchange.upper() == "NSE":
        return f"{clean}.NS"
    return clean


def fetch_single_ticker_data(ticker_symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    Fetches real-time fundamentals and SMA data for a single stock ticker.
    Utilizes local disk caching for fast repeat loads.
    """
    clean_sym = ticker_symbol.strip().upper()
    if not clean_sym:
        return None

    # Check local disk cache
    now = time.time()
    if use_cache:
        cache = _read_disk_cache()
        if clean_sym in cache:
            cached_item = cache[clean_sym]
            cached_time = cached_item.get("_cached_at", 0)
            if now - cached_time < CACHE_TTL_SECONDS:
                data = cached_item.get("data", {})
                if data:
                    return data

    try:
        t = yf.Ticker(clean_sym)
        info = t.info or {}
        
        # 1-year historical prices for 50 & 200 SMA calculation and charting
        hist = t.history(period="1y")
        
        if hist.empty or len(hist) < 20:
            if not info or ("regularMarketPrice" not in info and "currentPrice" not in info):
                return None

        # Price retrieval
        current_price = (
            info.get("currentPrice") or
            info.get("regularMarketPrice") or
            (hist["Close"].iloc[-1] if not hist.empty else None)
        )
        if current_price is None or pd.isna(current_price):
            return None

        # Moving Averages calculation
        if len(hist) >= 50:
            sma50_calc = float(hist["Close"].rolling(window=50).mean().iloc[-1])
        else:
            sma50_calc = info.get("fiftyDayAverage")

        if len(hist) >= 200:
            sma200_calc = float(hist["Close"].rolling(window=200).mean().iloc[-1])
        else:
            sma200_calc = info.get("twoHundredDayAverage") or (float(hist["Close"].mean()) if len(hist) >= 50 else sma50_calc)

        # Fundamentals
        roe = info.get("returnOnEquity")
        if roe is not None and not pd.isna(roe):
            roe = float(roe)
        else:
            # Fallback derivation for Indian equities (often omitted from top-level info)
            net_income = info.get("netIncomeToCommon")
            book_val = info.get("bookValue")
            shares = info.get("sharesOutstanding")
            de_ratio = info.get("debtToEquity")
            total_debt = info.get("totalDebt")
            
            if net_income and book_val and shares and (book_val * shares) > 0:
                equity = float(book_val) * float(shares)
                roe = float(net_income) / equity
            elif net_income and total_debt and de_ratio and de_ratio > 0:
                # de_ratio is totalDebt / equity * 100
                equity = float(total_debt) / (float(de_ratio) / 100.0)
                roe = float(net_income) / equity
            else:
                roe = None

        debt_to_equity = info.get("debtToEquity")
        if debt_to_equity is not None and not pd.isna(debt_to_equity):
            debt_to_equity = float(debt_to_equity)
        else:
            total_debt = info.get("totalDebt")
            stockholder_equity = info.get("totalStockholderEquity") or info.get("bookValue")
            if total_debt == 0 or total_debt is None:
                debt_to_equity = 0.0
            elif stockholder_equity and stockholder_equity > 0:
                debt_to_equity = (total_debt / stockholder_equity) * 100.0
            else:
                debt_to_equity = None

        trailing_pe = info.get("trailingPE")
        if trailing_pe is None or pd.isna(trailing_pe):
            trailing_pe = info.get("forwardPE")
        else:
            trailing_pe = float(trailing_pe)

        company_name = info.get("shortName") or info.get("longName") or clean_sym
        sector = info.get("sector") or info.get("industry") or "Diversified"
        market_cap = info.get("marketCap") or 0
        currency = info.get("currency") or ("INR" if (".NS" in clean_sym or ".BO" in clean_sym) else "USD")

        result = {
            "ticker": clean_sym,
            "name": company_name,
            "sector": sector,
            "currency": currency,
            "marketCap": market_cap,
            "currentPrice": round(float(current_price), 2),
            "returnOnEquity": roe,
            "debtToEquity": debt_to_equity,
            "trailingPE": round(float(trailing_pe), 2) if trailing_pe is not None else None,
            "sma50": round(float(sma50_calc), 2) if sma50_calc is not None else None,
            "sma200": round(float(sma200_calc), 2) if sma200_calc is not None else None,
        }

        # Save to disk cache
        if use_cache:
            cache = _read_disk_cache()
            cache[clean_sym] = {"_cached_at": now, "data": result}
            _write_disk_cache(cache)

        return result

    except Exception as e:
        print(f"Error fetching {clean_sym}: {e}")
        return None


def fetch_single_ticker_history(ticker_symbol: str) -> pd.DataFrame:
    """
    Fetches 1-year historical price dataframe for plotting interactive technical charts.
    """
    clean_sym = ticker_symbol.strip().upper()
    try:
        t = yf.Ticker(clean_sym)
        hist = t.history(period="1y")
        return hist
    except Exception:
        return pd.DataFrame()


def fetch_batch_data(
    tickers: List[str],
    max_workers: int = 10,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    use_cache: bool = True
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame], List[str]]:
    """
    Fetches financial metrics in parallel using a ThreadPoolExecutor.
    Significantly speeds up multi-stock retrieval (e.g., Nifty 50 in seconds).
    
    Returns:
    - metrics_df: pandas DataFrame containing the metrics
    - histories: dict of {ticker: history_df} for individual deep dive
    - failed_tickers: list of tickers that could not be retrieved
    """
    clean_tickers = list(dict.fromkeys([t.strip().upper() for t in tickers if t.strip()]))
    if not clean_tickers:
        return pd.DataFrame(), {}, []

    data_list = []
    failed_tickers = []
    total = len(clean_tickers)
    completed_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(fetch_single_ticker_data, ticker, use_cache): ticker
            for ticker in clean_tickers
        }
        
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            completed_count += 1
            if progress_callback:
                progress_callback(completed_count, total)
                
            try:
                item = future.result()
                if item is not None:
                    data_list.append(item)
                else:
                    failed_tickers.append(ticker)
            except Exception as e:
                print(f"Exception fetching {ticker}: {e}")
                failed_tickers.append(ticker)

    if not data_list:
        return pd.DataFrame(), {}, failed_tickers

    df = pd.DataFrame(data_list)
    return df, {}, failed_tickers
