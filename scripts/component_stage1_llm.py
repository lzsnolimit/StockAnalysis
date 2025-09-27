import os
import sys
from typing import List, Dict, Any

# Ensure project root is on sys.path when running as a script
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from utils.io_helpers import read_json, write_json
from utils.ticker_utils import normalize_ticker

def _fallback_top10_from_posts(posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    import re
    stop = {"I", "IT", "USA", "ALL", "DD", "YOLO", "WSB", "AI"}
    ticker_stats: Dict[str, Dict[str, Any]] = {}
    pattern = re.compile(r"\$?[A-Za-z]{1,5}(?:\.[A-Za-z]{1,3})?")

    for p in posts[:500]:
        title = p.get("title", "") or ""
        body = p.get("selftext", "") or ""
        score = int(p.get("score") or 0)
        comments = int(p.get("num_comments") or 0)
        link = p.get("permalink", "") or ""
        text = f"{title} {body}"
        for m in pattern.findall(text):
            t = normalize_ticker(m)
            if not t or t in stop:
                continue
            st = ticker_stats.setdefault(t, {"mentions": 0, "score": 0, "comments": 0, "sources": []})
            st["mentions"] += 1
            st["score"] += score
            st["comments"] += comments
            if link and len(st["sources"]) < 3 and link not in st["sources"]:
                st["sources"].append(link)

    ranked = []
    for t, st in ticker_stats.items():
        heat = st["mentions"] * 1.0 + st["score"] * 0.002 + st["comments"] * 0.001
        ranked.append((t, heat, st))
    ranked.sort(key=lambda x: x[1], reverse=True)
    items = []
    for t, heat, st in ranked[:10]:
        points = ["Reddit讨论热度较高", "帖子评分与评论较多"]
        items.append({
            "ticker": t,
            "attention_points": points,
            "sources": st["sources"],
            "heat_score": round(heat, 3),
        })
    return {"items": items}


def stage1_top10_from_posts(posts: List[Dict[str, Any]], llm) -> Dict[str, Any]:
    """Run LLM to get top10 tickers and attention points, normalize tickers, cap to 10.

    llm must implement: top10_from_posts(posts) -> {"items": [...]}.
    """
    result = llm.top10_from_posts(posts)
    items = []
    for item in (result.get("items") or [])[:10]:
        t_raw = item.get("ticker")
        t = normalize_ticker(t_raw or "")
        if not t:
            continue
        points = item.get("attention_points") or []
        if isinstance(points, list):
            points = [str(p).strip() for p in points if str(p).strip()]
        else:
            points = []
        sources = item.get("sources") or []
        if isinstance(sources, list):
            sources = [str(s) for s in sources][:3]
        else:
            sources = []
        heat = item.get("heat_score")
        try:
            heat = float(heat) if heat is not None else None
        except Exception:
            heat = None
        items.append({
            "ticker": t,
            "attention_points": points,
            "sources": sources,
            "heat_score": heat,
        })
    if items:
        return {"items": items}
    # Fallback: regex-based extraction and ranking
    return _fallback_top10_from_posts(posts)


def main() -> None:
    from utils.llm_client import LLMClient

    input_path = os.environ.get("STAGE1_INPUT", "outputs/wallstreetbets_normalized.json")
    output_path = os.environ.get("STAGE1_OUTPUT", "outputs/stage1_top10.json")
    posts = read_json(input_path)
    client = LLMClient()
    data = stage1_top10_from_posts(posts, client)
    write_json(output_path, data)
    print(f"Stage1: wrote {len(data.get('items', []))} items to {output_path}")


if __name__ == "__main__":
    main()
