import os
import json
from utils.io_helpers import write_json, read_json
from scripts.component_stage1_llm import stage1_top10_from_posts


class FakeLLM:
    def top10_from_posts(self, posts):
        # Deterministic fake output for testing
        return {
            "items": [
                {
                    "ticker": "AAPL",
                    "attention_points": ["新品发布会", "营收增长"],
                    "sources": ["/r/wsb/aapl1"],
                    "heat_score": 8.5,
                },
                {
                    "ticker": "$TSLA",
                    "attention_points": ["交付量数据", "FSD 进展"],
                    "sources": ["/r/wsb/tsla1", "/r/wsb/tsla2"],
                    "heat_score": 7.2,
                },
                {
                    "ticker": "invalid!",
                    "attention_points": ["should be ignored"],
                    "sources": [],
                    "heat_score": 3.0,
                },
            ]
        }


def test_stage1_top10_normalization(tmp_path):
    # Prepare minimal normalized posts fixture
    posts = [
        {"title": "AAPL to the moon", "score": 100, "num_comments": 50, "permalink": "/r/wsb/aapl1"},
        {"title": "TSLA new FSD", "score": 80, "num_comments": 40, "permalink": "/r/wsb/tsla1"},
    ]

    llm = FakeLLM()
    result = stage1_top10_from_posts(posts, llm)
    assert "items" in result
    items = result["items"]
    # invalid ticker filtered out
    assert len(items) == 2

    # normalized tickers
    assert items[0]["ticker"] == "AAPL"
    assert items[1]["ticker"] == "TSLA"

    # points and sources present
    for it in items:
        assert isinstance(it["attention_points"], list)
        assert isinstance(it["sources"], list)

    # Write output and verify file content
    out_file = tmp_path / "stage1_top10.json"
    write_json(str(out_file), result)
    loaded = read_json(str(out_file))
    assert loaded == result

