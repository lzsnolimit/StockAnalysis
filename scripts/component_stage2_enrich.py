import os
import sys
from typing import Dict, Any

# Ensure project root is on sys.path when running as a script
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from utils.io_helpers import read_json, write_json
from providers.yfinance_client import fetch_quote, fetch_history_1d


def stage2_enrich(stage1: Dict[str, Any]) -> Dict[str, Any]:
    items = []
    for item in stage1.get("items", []):
        ticker = item.get("ticker")
        data: Dict[str, Any] = {"quote": {}, "history_1d": []}
        try:
            q = fetch_quote(ticker)
            h = fetch_history_1d(ticker)
            data["quote"] = q
            data["history_1d"] = h
        except Exception:
            data["error"] = True
        items.append({
            "ticker": ticker,
            "attention_points": item.get("attention_points", []),
            "sources": item.get("sources", []),
            "heat_score": item.get("heat_score"),
            "data": data,
        })
    return {"items": items}


def main() -> None:
    input_path = os.environ.get("STAGE2_INPUT", "outputs/stage1_top10.json")
    output_path = os.environ.get("STAGE2_OUTPUT", "outputs/stage2_enriched.json")
    stage1 = read_json(input_path)
    enriched = stage2_enrich(stage1)
    write_json(output_path, enriched)
    print(f"Stage2: enriched {len(enriched.get('items', []))} items -> {output_path}")


if __name__ == "__main__":
    main()
