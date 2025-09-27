import types
from scripts.component_stage2_enrich import stage2_enrich


class FakeTicker:
    def __init__(self, ticker):
        self.ticker = ticker
        self.fast_info = {
            "last_price": 100.0 if ticker == "AAPL" else 200.0,
            "previous_close": 95.0 if ticker == "AAPL" else 205.0,
            "currency": "USD",
            "market_cap": 1_000_000_000,
            "last_volume": 123456,
        }
        self.info = {
            "regularMarketPrice": self.fast_info["last_price"],
            "regularMarketPreviousClose": self.fast_info["previous_close"],
            "currency": "USD",
            "marketCap": self.fast_info["market_cap"],
            "regularMarketVolume": self.fast_info["last_volume"],
        }

    def history(self, period="1y", interval="1d"):
        import pandas as pd
        data = {
            "Date": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")],
            "Open": [10.0, 11.0],
            "High": [12.0, 12.5],
            "Low": [9.5, 10.5],
            "Close": [11.0, 12.0],
            "Volume": [1000, 2000],
        }
        return pd.DataFrame(data)


def test_stage2_enrich_monkeypatch_yfinance(monkeypatch):
    # Monkeypatch yfinance.Ticker
    import providers.yfinance_client as yc

    def fake_ticker_ctor(ticker):
        return FakeTicker(ticker)

    monkeypatch.setattr(yc, "yf", types.SimpleNamespace(Ticker=fake_ticker_ctor))

    stage1 = {
        "items": [
            {"ticker": "AAPL", "attention_points": ["关注点1"], "sources": []},
            {"ticker": "TSLA", "attention_points": ["关注点2"], "sources": []},
        ]
    }

    enriched = stage2_enrich(stage1)
    assert "items" in enriched
    assert len(enriched["items"]) == 2
    for item in enriched["items"]:
        q = item["data"]["quote"]
        assert "price" in q and "previous_close" in q and "timestamp" in q
        h = item["data"]["history_1d"]
        assert isinstance(h, list) and len(h) == 2
        assert set(h[0].keys()) == {"date", "open", "high", "low", "close", "volume"}

