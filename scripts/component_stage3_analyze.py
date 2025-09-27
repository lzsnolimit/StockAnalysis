import os
import sys
from typing import Dict, Any, List, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure project root is on sys.path when running as a script
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from utils.io_helpers import read_json, write_json
from utils.env import load_env


def stage3_analyze(enriched: Dict[str, Any], llm) -> Dict[str, Any]:
    """Sequential analysis (single-thread)."""
    items: List[Dict[str, Any]] = []
    alerts: List[Dict[str, Any]] = []
    for item in enriched.get("items", []):
        decision = llm.attention_decision(item)
        analyzed = {**item, "analysis": decision}
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


def stage3_analyze_threaded(
    enriched: Dict[str, Any],
    workers: int,
    llm_factory: Callable[[], Any],
) -> Dict[str, Any]:
    """Analyze concurrently using a thread pool.

    Creates a separate LLM client per worker via llm_factory to avoid thread-safety issues.
    Preserves input order in the output.
    """
    src_items: List[Dict[str, Any]] = enriched.get("items", [])
    analyzed_items: List[Dict[str, Any]] = [None] * len(src_items)  # type: ignore
    alerts: List[Dict[str, Any]] = []

    def task(idx_item: Tuple[int, Dict[str, Any]]):
        idx, item = idx_item
        llm = llm_factory()
        decision = llm.attention_decision(item)
        analyzed = {**item, "analysis": decision}
        alert = None
        if decision.get("attention_needed"):
            alert = {
                "ticker": item.get("ticker"),
                "severity": decision.get("severity"),
                "reasons": decision.get("reasons", []),
                "email_subject": (decision.get("email") or {}).get("subject", ""),
                "email_body": (decision.get("email") or {}).get("body", ""),
            }
        return idx, analyzed, alert

    with ThreadPoolExecutor(max_workers=max(1, int(workers or 1))) as ex:
        futures = [ex.submit(task, (i, it)) for i, it in enumerate(src_items)]
        for fut in as_completed(futures):
            idx, analyzed, alert = fut.result()
            analyzed_items[idx] = analyzed
            if alert:
                alerts.append(alert)

    items = [it for it in analyzed_items if it is not None]
    return {"items": items, "alerts": alerts}


def main() -> None:
    from utils.llm_client import LLMClient
    from scripts.db_writer import write_run_and_alerts

    # Load .env so env variables like STAGE3_WORKERS apply
    load_env()
    input_path = os.environ.get("STAGE3_INPUT", "outputs/stage2_enriched.json")
    output_path = os.environ.get("STAGE3_OUTPUT", "outputs/stage3_analyzed.json")
    # Default to 10 workers if not specified
    workers = int(os.environ.get("STAGE3_WORKERS", "10"))

    enriched = read_json(input_path)

    if workers > 1:
        analyzed = stage3_analyze_threaded(enriched, workers=workers, llm_factory=lambda: LLMClient())
    else:
        analyzed = stage3_analyze(enriched, LLMClient())

    write_json(output_path, analyzed)
    # Persist to DB using DB_PATH/SQLITE_PATH from .env
    run_id = write_run_and_alerts(None, analyzed)
    print(f"Stage3: analyzed {len(analyzed.get('items', []))} items with workers={workers} -> {output_path}; stored run_id={run_id}")


if __name__ == "__main__":
    main()
