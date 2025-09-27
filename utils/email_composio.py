import os
from typing import List, Dict, Any, Optional

from utils.env import load_env


def _load_recipients() -> List[str]:
    """Load recipients from env `ALERT_RECIPIENTS` (comma-separated) or `config/subscribers.csv`."""
    load_env()
    env_val = os.environ.get("ALERT_RECIPIENTS")
    if env_val:
        return [e.strip() for e in env_val.split(",") if e.strip()]
    path = os.environ.get("SUBSCRIBERS_CSV", "config/subscribers.csv")
    emails: List[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    emails.append(s)
    except Exception:
        pass
    return emails


def send_email_via_composio(subject: str, body: str, recipients: List[str], user_id: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    """Send email via Composio + OpenAI tools to all recipients; returns a summary dict.

    Uses tool-enabled chat completion to trigger `GMAIL_SEND_EMAIL`.
    """
    load_env()
    from composio import Composio
    from openai import OpenAI

    openai = OpenAI()
    composio = Composio()
    user_id = (user_id or os.environ.get("COMPOSIO_USER_ID") or "default-user").strip()
    model = model or os.environ.get("LLM_MODEL") or "gpt-5"

    tools = composio.tools.get(user_id=user_id, tools=["GMAIL_SEND_EMAIL"])

    results: Dict[str, Any] = {"sent": [], "errors": []}
    for rcpt in recipients:
        prompt = f"Please send an email to {rcpt} with the subject '{subject}' and the body '{body}'"
        try:
            completion = openai.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                tools=tools,
            )
            res = composio.provider.handle_tool_calls(user_id=user_id, response=completion)
            results["sent"].append({"recipient": rcpt, "result": res})
        except Exception as e:
            results["errors"].append({"recipient": rcpt, "error": str(e)})
    return results


def send_stage3_emails(analyzed: Dict[str, Any]) -> Dict[str, Any]:
    """Send emails for all attention-needed items in a Stage3 analyzed payload."""
    recipients = _load_recipients()
    if not recipients:
        return {"sent": [], "errors": [{"error": "no recipients configured"}]}
    items = analyzed.get("items", [])
    summary: Dict[str, Any] = {"sent": [], "errors": []}
    for item in items:
        decision = (item.get("analysis") or {})
        if not decision.get("attention_needed"):
            continue
        email = decision.get("email") or {}
        subj = email.get("subject") or f"Attention: {item.get('ticker')}"
        body = email.get("body") or ""
        try:
            result = send_email_via_composio(subj, body, recipients)
            summary["sent"].append({"ticker": item.get("ticker"), "result": result})
        except Exception as e:
            summary["errors"].append({"ticker": item.get("ticker"), "error": str(e)})
    return summary

