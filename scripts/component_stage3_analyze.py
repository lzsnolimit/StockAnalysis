import os
import sys
from typing import Dict, Any

# Ensure project root is on sys.path when running as a script
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from utils.io_helpers import read_json, write_json


def stage3_analyze(enriched: Dict[str, Any], llm) -> Dict[str, Any]:
    items = []
    alerts = []
    for item in enriched.get("items", []):
        decision = llm.attention_decision(item)
        analyzed = {
            **item,
            "analysis": decision,
        }
        items.append(analyzed)
        if decision.get("attention_needed"):
            alerts.append({
                "ticker": item.get("ticker"),
                "severity": decision.get("severity"),
                "reasons": decision.get("reasons", []),
                "email_subject": (decision.get("email") or {}).get("subject", ""),
                "email_body": (decision.get("email") or {}).get("body", ""),
            })
    return {"items": items, "alerts": alerts}


def main() -> None:
    from utils.llm_client import LLMClient

    input_path = os.environ.get("STAGE3_INPUT", "outputs/stage2_enriched.json")
    output_path = os.environ.get("STAGE3_OUTPUT", "outputs/stage3_analyzed.json")
    enriched = read_json(input_path)
    client = LLMClient()
    analyzed = stage3_analyze(enriched, client)
    write_json(output_path, analyzed)
    print(f"Stage3: analyzed {len(analyzed.get('items', []))} items -> {output_path}")


if __name__ == "__main__":
    main()
