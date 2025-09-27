import types
from scripts.component_stage2_enrich import stage2_enrich


class EmptyTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = {}
        self.info = {}

    def history(self, period="1y", interval="1d"):
        import pandas as pd
        return pd.DataFrame()  # empty to force API fallback


def test_stage2_fallback_yahoo_api(monkeypatch):
    # Monkeypatch yfinance to return empty data
    import providers.yfinance_client as yc

    def fake_ticker_ctor(symbol):
        return EmptyTicker(symbol)

    monkeypatch.setattr(yc, "yf", types.SimpleNamespace(Ticker=fake_ticker_ctor))

    # Monkeypatch requests.get to return a quoteResponse
    class Resp:
        def __init__(self, json_data):
            self._json = json_data

        def raise_for_status(self):
            pass

        def json(self):
            return self._json

    def fake_get(url, params=None, headers=None, timeout=None):
        assert "symbols" in (params or {})
        return Resp({
            "quoteResponse": {
                "result": [
                    {
                        "regularMarketPrice": 123.45,
                        "regularMarketPreviousClose": 120.00,
                        "currency": "USD",
                        "marketCap": 1234567890,
                        "regularMarketVolume": 987654,
                    }
                ]
            }
        })

    monkeypatch.setattr(yc, "requests", types.SimpleNamespace(get=fake_get))

    stage1 = {"items": [{"ticker": "AAPL"}]}
    enriched = stage2_enrich(stage1)
    q = enriched["items"][0]["data"]["quote"]
    assert q.get("price") == 123.45
    assert q.get("previous_close") == 120.00
    assert q.get("currency") == "USD"
    assert q.get("market_cap") == 1234567890.0
    assert q.get("volume") == 987654

