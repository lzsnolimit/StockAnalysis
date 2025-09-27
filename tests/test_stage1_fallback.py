from scripts.component_stage1_llm import stage1_top10_from_posts


class EmptyLLM:
    def top10_from_posts(self, posts):
        return {"items": []}


def test_stage1_fallback_extracts_tickers():
    posts = [
        {"title": "AAPL to the moon", "selftext": "I love $AAPL", "score": 50, "num_comments": 20, "permalink": "/r/wsb/aapl1"},
        {"title": "TSLA pumps", "selftext": "TSLA earnings soon", "score": 40, "num_comments": 10, "permalink": "/r/wsb/tsla1"},
        {"title": "BRK.B value", "selftext": "$BRK.B discussion", "score": 30, "num_comments": 5, "permalink": "/r/wsb/brkb1"},
    ]
    llm = EmptyLLM()
    result = stage1_top10_from_posts(posts, llm)
    items = result["items"]
    tickers = [it["ticker"] for it in items]
    assert "AAPL" in tickers
    assert "TSLA" in tickers
    assert "BRK.B" in tickers
    # Check attention points and discussion highlights exist
    assert all(len(it["attention_points"]) >= 2 for it in items)
    assert all(isinstance(it.get("discussion_highlights"), list) and len(it.get("discussion_highlights")) >= 1 for it in items)
