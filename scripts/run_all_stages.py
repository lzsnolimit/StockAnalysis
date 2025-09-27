import os
import sys
from typing import Dict, Any, List

# Ensure project root is on sys.path when running as a script
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from utils.env import load_env
from utils.io_helpers import read_json, write_json
from utils.llm_client import LLMClient
from scripts.component_stage1_llm import stage1_top10_from_posts
from scripts.component_stage2_enrich import stage2_enrich
from scripts.component_stage3_analyze import stage3_analyze, stage3_analyze_threaded
from scripts.db_writer import write_run_and_alerts
from utils.email_composio import send_stage3_emails, send_stage3_bulk_email
from scripts.component_stage4_notify import stage4_notify


def run_all() -> Dict[str, Any]:
    """Run Stage1 -> Stage2 -> Stage3 in one pass, then send emails and write DB.

    Returns a summary dict with paths and counts.
    """
    load_env()

    # Paths (override via env if needed)
    posts_path = os.environ.get("STAGE1_POSTS_INPUT", "outputs/wallstreetbets_normalized.json")
    stage1_out = os.environ.get("STAGE1_OUTPUT", "outputs/stage1_top10.json")
    stage2_out = os.environ.get("STAGE2_OUTPUT", "outputs/stage2_enriched.json")
    stage3_out = os.environ.get("STAGE3_OUTPUT", "outputs/stage3_analyzed.json")

    # Stage 1: Top10 from posts via LLM
    print(f"[Stage1] Loading posts from {posts_path}")
    posts: List[Dict[str, Any]] = read_json(posts_path)
    llm = LLMClient()
    stage1 = stage1_top10_from_posts(posts, llm)
    write_json(stage1_out, stage1)
    print(f"[Stage1] Wrote {stage1_out} with {len(stage1.get('items', []))} items")

    # Stage 2: Enrich top10 with market data
    print("[Stage2] Enriching Stage1 items")
    stage2 = stage2_enrich(stage1)
    write_json(stage2_out, stage2)
    print(f"[Stage2] Wrote {stage2_out} with {len(stage2.get('items', []))} items")

    # Stage 3: Analyze attention decisions (threaded by default)
    workers = int(os.environ.get("STAGE3_WORKERS", "10"))
    print(f"[Stage3] Analyzing with workers={workers}")
    if workers > 1:
        analyzed = stage3_analyze_threaded(stage2, workers=workers, llm_factory=lambda: LLMClient())
    else:
        analyzed = stage3_analyze(stage2, LLMClient())
    write_json(stage3_out, analyzed)
    attn_count = sum(1 for it in analyzed.get("items", []) if (it.get("analysis") or {}).get("attention_needed"))
    print(f"[Stage3] Wrote {stage3_out}; attention_count={attn_count}")

    # DB write
    run_id = write_run_and_alerts(None, analyzed)
    print(f"[DB] Stored run_id={run_id}")

    # Emails (best-effort)
    try:
        # Default: bulk email; fallback env to per-item if requested
        bulk = (os.environ.get("STAGE3_EMAIL_BULK") or "1").strip() not in ("", "0", "false", "False")
        if bulk:
            mail_summary = send_stage3_bulk_email(analyzed)
        else:
            mail_summary = send_stage3_emails(analyzed)
        sent_count = len(mail_summary.get("sent", []))
        err_count = len(mail_summary.get("errors", []))
        print(f"[Email] sent={sent_count}, errors={err_count}")
    except Exception as e:
        print(f"[Email] dispatch failed: {e}")
        mail_summary = {"sent": [], "errors": [{"error": str(e)}]}

    # Optional Stage4: resend/notify
    try:
        if (os.environ.get("RUN_STAGE4") or "").strip() not in ("", "0", "false", "False"):
            print("[Stage4] Notifying from Stage3 analyzed output")
            stage4_summary = stage4_notify(analyzed)
            out_path = os.environ.get("STAGE4_OUTPUT", "outputs/stage4_email_summary.json")
            write_json(out_path, stage4_summary)
            print(f"[Stage4] Wrote {out_path}; sent={len(stage4_summary.get('sent', []))}, errors={len(stage4_summary.get('errors', []))}")
    except Exception as e:
        print(f"[Stage4] notify failed: {e}")

    return {
        "stage1_output": stage1_out,
        "stage2_output": stage2_out,
        "stage3_output": stage3_out,
        "run_id": run_id,
        "attention_count": attn_count,
        "email_summary": mail_summary,
    }


def main() -> None:
    summary = run_all()
    print("[All] Done:")
    print(summary)


if __name__ == "__main__":
    main()
