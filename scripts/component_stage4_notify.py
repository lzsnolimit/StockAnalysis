import os
import sys
from typing import Dict, Any

# Ensure project root on path when running as script
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from utils.env import load_env
from utils.io_helpers import read_json, write_json
from utils.email_composio import send_stage3_emails


def stage4_notify(analyzed: Dict[str, Any]) -> Dict[str, Any]:
    """Send emails for Stage3 analyzed attention items and return summary."""
    return send_stage3_emails(analyzed)


def main() -> None:
    load_env()
    input_path = os.environ.get("STAGE4_INPUT") or os.environ.get("STAGE3_OUTPUT", "outputs/stage3_analyzed.json")
    output_path = os.environ.get("STAGE4_OUTPUT", "outputs/stage4_email_summary.json")

    analyzed = read_json(input_path)
    summary = stage4_notify(analyzed)
    write_json(output_path, summary)
    sent_count = len(summary.get("sent", []))
    err_count = len(summary.get("errors", []))
    print(f"Stage4: email summary written to {output_path}; sent={sent_count}, errors={err_count}")


if __name__ == "__main__":
    main()

