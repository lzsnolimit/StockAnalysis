import types
from scripts.component_stage2_enrich import stage2_enrich


class EmptyTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = {}
        self.info = {}

    def history(self, period="1d", interval="1m"):
        import pandas as pd
        return pd.DataFrame()  # empty to force chart fallback


def test_intraday_yahoo_chart_fallback(monkeypatch):
    import providers.yfinance_client as yc

    def fake_ticker_ctor(symbol):
        return EmptyTicker(symbol)

    monkeypatch.setattr(yc, "yf", types.SimpleNamespace(Ticker=fake_ticker_ctor))

    class Resp:
        def __init__(self, json_data):
            self._json = json_data

        def raise_for_status(self):
            pass

        def json(self):
            return self._json

    def fake_get(url, params=None, headers=None, timeout=None):
        assert params["interval"] == "1m"
        return Resp({
            "chart": {
                "result": [
                    {
                        "timestamp": [1727425800, 1727425860],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [100.0, 100.5],
                                    "high": [100.6, 100.7],
                                    "low": [99.9, 100.2],
                                    "close": [100.4, 100.6],
                                    "volume": [1000, 1200],
                                }
                            ]
                        },
                    }
                ]
            }
        })

    # Patch the requests.get used inside providers module
    monkeypatch.setattr(yc.requests, "get", fake_get, raising=False)

    stage1 = {"items": [{"ticker": "AAPL"}]}
    enriched = stage2_enrich(stage1)
    intraday = enriched["items"][0]["data"]["intraday_1m"]
    assert isinstance(intraday, list) and len(intraday) == 2
    assert set(intraday[0].keys()) == {"datetime", "open", "high", "low", "close", "volume"}
