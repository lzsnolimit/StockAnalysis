from scripts.component_stage3_analyze import stage3_analyze


class FakeLLM:
    def attention_decision(self, item):
        t = item.get("ticker")
        # Simple rule for test: AAPL needs attention, TSLA not
        if t == "AAPL":
            return {
                "attention_needed": True,
                "severity": "alert",
                "reasons": ["价格波动显著", "新闻密集"],
                "email": {
                    "subject": "[Attention] AAPL +3.0% — 事件摘要",
                    "body": "AAPL 近期新闻较多且股价波动，建议关注。",
                },
            }
        return {
            "attention_needed": False,
            "severity": "watch",
            "reasons": ["信号不足"],
            "email": {"subject": "", "body": ""},
        }


def test_stage3_analyze_with_fake_llm():
    enriched = {
        "items": [
            {"ticker": "AAPL", "attention_points": ["新品发布"], "data": {"quote": {"price": 100.0}}},
            {"ticker": "TSLA", "attention_points": ["交付量"], "data": {"quote": {"price": 200.0}}},
        ]
    }
    llm = FakeLLM()
    analyzed = stage3_analyze(enriched, llm)
    assert "items" in analyzed and "alerts" in analyzed
    items = analyzed["items"]
    alerts = analyzed["alerts"]
    assert len(items) == 2
    # Only AAPL triggers alert
    assert len(alerts) == 1
    assert alerts[0]["ticker"] == "AAPL"
    assert alerts[0]["severity"] == "alert"
    assert "email_subject" in alerts[0] and "email_body" in alerts[0]

