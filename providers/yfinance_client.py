from typing import Dict, Any, List

import datetime as dt

import yfinance as yf
import requests


def _yf_symbol(ticker: str) -> str:
    """Map normalized ticker to Yahoo Finance symbol.

    Example: BRK.B -> BRK-B; BF.B -> BF-B.
    """
    return ticker.replace(".", "-")


def fetch_quote(ticker: str) -> Dict[str, Any]:
    symbol = _yf_symbol(ticker)
    t = yf.Ticker(symbol)
    quote: Dict[str, Any] = {}

    # Try fast_info first
    try:
        fi = t.fast_info
        price = fi.get("last_price")
        prev = fi.get("previous_close")
        if price is not None:
            quote["price"] = price
        if prev is not None:
            quote["previous_close"] = prev
        cur = fi.get("currency")
        if cur is not None:
            quote["currency"] = cur
        mcap = fi.get("market_cap")
        if mcap is not None:
            quote["market_cap"] = mcap
        vol = fi.get("last_volume") or fi.get("volume")
        if vol is not None:
            quote["volume"] = vol
    except Exception:
        pass

    # Fallback to info
    try:
        info = t.info
        if quote.get("price") is None and info.get("regularMarketPrice") is not None:
            quote["price"] = info.get("regularMarketPrice")
        if quote.get("previous_close") is None and info.get("regularMarketPreviousClose") is not None:
            quote["previous_close"] = info.get("regularMarketPreviousClose")
        if quote.get("currency") is None and info.get("currency") is not None:
            quote["currency"] = info.get("currency")
        if quote.get("market_cap") is None and info.get("marketCap") is not None:
            quote["market_cap"] = info.get("marketCap")
        if quote.get("volume") is None and info.get("regularMarketVolume") is not None:
            quote["volume"] = info.get("regularMarketVolume")
    except Exception:
        pass

    # Symbol and timestamp
    quote["symbol"] = symbol
    quote["timestamp"] = dt.datetime.utcnow().isoformat() + "Z"

    # Change pct
    price = quote.get("price")
    prev = quote.get("previous_close")
    try:
        if price is not None and prev not in (None, 0):
            quote["change_pct"] = (float(price) - float(prev)) / float(prev) * 100.0
    except Exception:
        quote["change_pct"] = None

    # Fallback via recent history if price/previous_close missing
    if quote.get("price") is None or quote.get("previous_close") is None or quote.get("volume") is None:
        try:
            df = t.history(period="5d", interval="1d")
            if df is not None and len(df) > 0:
                last = df.tail(1)
                prev = df.tail(2)[:1]
                last_close = float(last["Close"].iloc[0]) if "Close" in last else None
                prev_close = float(prev["Close"].iloc[0]) if len(prev) > 0 and "Close" in prev else None
                volume = int(last["Volume"].iloc[0]) if "Volume" in last else None
                if quote.get("price") is None and last_close is not None:
                    quote["price"] = last_close
                if quote.get("previous_close") is None and prev_close is not None:
                    quote["previous_close"] = prev_close
                if quote.get("volume") is None and volume is not None:
                    quote["volume"] = volume
        except Exception:
            pass

    # Final fallback via Yahoo Finance quote API
    if quote.get("price") is None or quote.get("previous_close") is None:
        try:
            url = "https://query1.finance.yahoo.com/v7/finance/quote"
            headers = {"User-Agent": "StockAnalysis/1.0 (yfinance fallback)"}
            resp = requests.get(url, params={"symbols": symbol}, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = (data.get("quoteResponse", {}) or {}).get("result", [])
            if results:
                r0 = results[0]
                price = r0.get("regularMarketPrice")
                prev = r0.get("regularMarketPreviousClose")
                currency = r0.get("currency")
                mcap = r0.get("marketCap")
                vol = r0.get("regularMarketVolume")
                if quote.get("price") is None and price is not None:
                    quote["price"] = float(price)
                if quote.get("previous_close") is None and prev is not None:
                    quote["previous_close"] = float(prev)
                if quote.get("currency") is None and currency is not None:
                    quote["currency"] = currency
                if quote.get("market_cap") is None and mcap is not None:
                    quote["market_cap"] = float(mcap)
                if quote.get("volume") is None and vol is not None:
                    quote["volume"] = int(vol)
        except Exception:
            pass

    return quote


def fetch_history_1d(ticker: str, period: str = "1y") -> List[Dict[str, Any]]:
    symbol = _yf_symbol(ticker)
    t = yf.Ticker(symbol)
    try:
        df = t.history(period=period, interval="1d")
    except Exception:
        return []

    records: List[Dict[str, Any]] = []
    if df is None:
        return records
    try:
        if len(df) == 0:
            return records
    except Exception:
        return records
    try:
        df = df.reset_index()
    except Exception:
        return records
    # Normalize column names across yfinance versions
    def val(row, key):
        return float(row.get(key)) if row.get(key) is not None else None

    try:
        itr = df.iterrows()
    except Exception:
        return records
    for _, row in itr:
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


def fetch_intraday_1m(ticker: str, day_range: str = "1d") -> List[Dict[str, Any]]:
    """Fetch today's 1-minute bars. Try yfinance first, then Yahoo chart API as fallback.

    Returns a list of records: {datetime, open, high, low, close, volume}
    """
    symbol = _yf_symbol(ticker)
    t = yf.Ticker(symbol)
    # Try yfinance intraday
    try:
        df = t.history(period="1d", interval="1m")
    except Exception:
        df = None

    records: List[Dict[str, Any]] = []
    if df is not None:
        try:
            has_data = len(df) > 0
        except Exception:
            has_data = False
        if has_data:
            try:
                df = df.reset_index()
            except Exception:
                df = None
        if df is not None:
            try:
                itr = df.iterrows()
            except Exception:
                itr = []
            for _, row in itr:
                dt_val = row.get("Datetime") or row.get("Date") or row.get("date")
                if isinstance(dt_val, dt.datetime):
                    dt_str = dt_val.replace(tzinfo=None).isoformat() + "Z"
                else:
                    dt_str = str(dt_val)
                rec = {
                    "datetime": dt_str,
                    "open": float(row.get("Open")) if row.get("Open") is not None else None,
                    "high": float(row.get("High")) if row.get("High") is not None else None,
                    "low": float(row.get("Low")) if row.get("Low") is not None else None,
                    "close": float(row.get("Close")) if row.get("Close") is not None else None,
                    "volume": int(row.get("Volume")) if row.get("Volume") is not None else None,
                }
                records.append(rec)
            if records:
                return records

    # Fallback: Yahoo chart API v8
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol
        headers = {"User-Agent": "StockAnalysis/1.0 (intraday fallback)"}
        resp = requests.get(url, params={"range": day_range, "interval": "1m"}, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        result = (data.get("chart", {}) or {}).get("result", [])
        if result:
            r0 = result[0]
            ts = r0.get("timestamp", [])
            quotes = ((r0.get("indicators", {}) or {}).get("quote", []) or [{}])[0]
            opens = quotes.get("open", [])
            highs = quotes.get("high", [])
            lows = quotes.get("low", [])
            closes = quotes.get("close", [])
            vols = quotes.get("volume", [])
            for i in range(min(len(ts), len(closes))):
                tsec = ts[i]
                dt_str = dt.datetime.utcfromtimestamp(tsec).isoformat() + "Z"
                rec = {
                    "datetime": dt_str,
                    "open": float(opens[i]) if i < len(opens) and opens[i] is not None else None,
                    "high": float(highs[i]) if i < len(highs) and highs[i] is not None else None,
                    "low": float(lows[i]) if i < len(lows) and lows[i] is not None else None,
                    "close": float(closes[i]) if i < len(closes) and closes[i] is not None else None,
                    "volume": int(vols[i]) if i < len(vols) and vols[i] is not None else None,
                }
                records.append(rec)
    except Exception:
        pass

    return records
