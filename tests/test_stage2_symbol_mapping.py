import types
from scripts.component_stage2_enrich import stage2_enrich


class CapturingFakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = {
            "last_price": 150.0,
            "previous_close": 148.0,
            "currency": "USD",
            "market_cap": 2_000_000_000,
            "last_volume": 55555,
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


def test_stage2_maps_dot_to_dash(monkeypatch):
    import providers.yfinance_client as yc

    def fake_ticker_ctor(symbol):
        return CapturingFakeTicker(symbol)

    monkeypatch.setattr(yc, "yf", types.SimpleNamespace(Ticker=fake_ticker_ctor))

    stage1 = {"items": [{"ticker": "BRK.B"}]}
    enriched = stage2_enrich(stage1)
    item = enriched["items"][0]
    # Verify quote is populated and symbol used is dash-form
    q = item["data"]["quote"]
    assert q.get("symbol") == "BRK-B"
    assert q.get("price") is not None
    assert q.get("previous_close") is not None
    assert q.get("timestamp") is not None

