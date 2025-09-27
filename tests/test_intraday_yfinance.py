import types
from scripts.component_stage2_enrich import stage2_enrich


class FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = {}
        self.info = {}

    def history(self, period="1d", interval="1m"):
        import pandas as pd
        if period == "1d" and interval == "1m":
            data = {
                "Datetime": [pd.Timestamp("2024-09-27 09:30:00"), pd.Timestamp("2024-09-27 09:31:00")],
                "Open": [100.0, 100.5],
                "High": [100.6, 100.7],
                "Low": [99.9, 100.2],
                "Close": [100.4, 100.6],
                "Volume": [1000, 1200],
            }
            return pd.DataFrame(data)
        # Return empty for other params to avoid interference
        return types.SimpleNamespace(reset_index=lambda: types.SimpleNamespace(iterrows=lambda: []))


def test_intraday_yfinance(monkeypatch):
    import providers.yfinance_client as yc

    def fake_ticker_ctor(symbol):
        return FakeTicker(symbol)

    monkeypatch.setattr(yc, "yf", types.SimpleNamespace(Ticker=fake_ticker_ctor))

    stage1 = {"items": [{"ticker": "AAPL"}]}
    enriched = stage2_enrich(stage1)
    intraday = enriched["items"][0]["data"]["intraday_1m"]
    assert isinstance(intraday, list) and len(intraday) == 2
    assert set(intraday[0].keys()) == {"datetime", "open", "high", "low", "close", "volume"}

