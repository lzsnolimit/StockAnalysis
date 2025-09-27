from typing import Dict, Any, List

import datetime as dt

import yfinance as yf


def fetch_quote(ticker: str) -> Dict[str, Any]:
    t = yf.Ticker(ticker)
    quote: Dict[str, Any] = {}

    # Try fast_info first
    try:
        fi = t.fast_info
        price = fi.get("last_price")
        prev = fi.get("previous_close")
        quote["price"] = price
        quote["previous_close"] = prev
        quote["currency"] = fi.get("currency")
        quote["market_cap"] = fi.get("market_cap")
        quote["volume"] = fi.get("last_volume") or fi.get("volume")
    except Exception:
        pass

    # Fallback to info
    try:
        info = t.info
        quote.setdefault("price", info.get("regularMarketPrice"))
        quote.setdefault("previous_close", info.get("regularMarketPreviousClose"))
        quote.setdefault("currency", info.get("currency"))
        quote.setdefault("market_cap", info.get("marketCap"))
        quote.setdefault("volume", info.get("regularMarketVolume"))
    except Exception:
        pass

    # Timestamp
    quote["timestamp"] = dt.datetime.utcnow().isoformat() + "Z"

    # Change pct
    price = quote.get("price")
    prev = quote.get("previous_close")
    try:
        if price is not None and prev not in (None, 0):
            quote["change_pct"] = (float(price) - float(prev)) / float(prev) * 100.0
    except Exception:
        quote["change_pct"] = None

    return quote


def fetch_history_1d(ticker: str, period: str = "1y") -> List[Dict[str, Any]]:
    t = yf.Ticker(ticker)
    try:
        df = t.history(period=period, interval="1d")
    except Exception:
        return []

    records: List[Dict[str, Any]] = []
    if df is None or len(df) == 0:
        return records
    df = df.reset_index()
    # Normalize column names across yfinance versions
    def val(row, key):
        return float(row.get(key)) if row.get(key) is not None else None

    for _, row in df.iterrows():
        date_val = row.get("Date") or row.get("date")
        if isinstance(date_val, (dt.datetime, dt.date)):
            date_str = dt.datetime.fromtimestamp(date_val.timestamp()).date().isoformat() if hasattr(date_val, "timestamp") else str(date_val)
        else:
            date_str = str(date_val)
        rec = {
            "date": date_str,
            "open": val(row, "Open"),
            "high": val(row, "High"),
            "low": val(row, "Low"),
            "close": val(row, "Close"),
            "volume": int(row.get("Volume")) if row.get("Volume") is not None else None,
        }
        records.append(rec)
    return records

