import os
import logging
from typing import List, Dict, Any, Optional

from utils.env import load_env


logger = logging.getLogger(__name__)


def _get_log_level() -> int:
    lvl = (os.environ.get("EMAIL_LOG_LEVEL") or "INFO").upper()
    return getattr(logging, lvl, logging.INFO)


def _load_recipients() -> List[str]:
    """Load recipients from env `ALERT_RECIPIENTS` (comma-separated) or `config/subscribers.csv`."""
    load_env()
    env_val = os.environ.get("ALERT_RECIPIENTS")
    if env_val:
        recips = [e.strip() for e in env_val.split(",") if e.strip()]
        logger.log(_get_log_level(), f"Email recipients from env ALERT_RECIPIENTS: {recips}")
        return recips
    path = os.environ.get("SUBSCRIBERS_CSV", "config/subscribers.csv")
    emails: List[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    emails.append(s)
    except Exception as e:
        logger.log(_get_log_level(), f"Failed reading subscribers CSV at {path}: {e}")
    return emails


def send_email_via_composio(subject: str, body: str, recipients: List[str], user_id: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    """Send email via Composio + OpenAI tools to all recipients; returns a summary dict.

    Uses tool-enabled chat completion to trigger `GMAIL_SEND_EMAIL`.
    """
    load_env()
    from composio import Composio
    from openai import OpenAI

    # Configure logger level
    logging.basicConfig(level=_get_log_level())
    dry_run = (os.environ.get("EMAIL_DRY_RUN") or "").strip() not in ("", "0", "false", "False")

    openai = OpenAI()
    composio = Composio()
    user_id = (user_id or os.environ.get("COMPOSIO_USER_ID") or "default-user").strip()
    model = model or os.environ.get("LLM_MODEL") or "gpt-5"

    logger.log(_get_log_level(), f"Preparing email via Composio: user_id={user_id}, model={model}, recipients={recipients}, dry_run={dry_run}")
    tools = composio.tools.get(user_id=user_id, tools=["GMAIL_SEND_EMAIL"])
    logger.log(_get_log_level(), f"Fetched tools: {tools}")

    results: Dict[str, Any] = {"sent": [], "errors": []}
    for rcpt in recipients:
        prompt = f"Please send an email to {rcpt} with the subject '{subject}' and the body '{body}'"
        logger.log(_get_log_level(), f"Dispatching email: recipient={rcpt}, subject={subject}")
        try:
            completion = openai.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                tools=tools,
            )
            logger.log(_get_log_level(), f"OpenAI completion created: {completion}")
            if dry_run:
                logger.log(_get_log_level(), f"EMAIL_DRY_RUN active: skipping provider.handle_tool_calls for recipient={rcpt}")
                res = {"dry_run": True, "recipient": rcpt, "prompt": prompt}
            else:
                res = composio.provider.handle_tool_calls(user_id=user_id, response=completion)
                logger.log(_get_log_level(), f"Provider handled tool calls: {res}")
            results["sent"].append({"recipient": rcpt, "result": res})
        except Exception as e:
            logger.exception(f"Failed to send email to {rcpt}: {e}")
            results["errors"].append({"recipient": rcpt, "error": str(e)})
    return results


def send_stage3_emails(analyzed: Dict[str, Any]) -> Dict[str, Any]:
    """Send emails for all attention-needed items in a Stage3 analyzed payload."""
    recipients = _load_recipients()
    if not recipients:
        logger.log(_get_log_level(), "No email recipients configured; skip sending.")
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
            logger.log(_get_log_level(), f"Sending attention email for {item.get('ticker')}: subject={subj}")
            result = send_email_via_composio(subj, body, recipients)
            summary["sent"].append({"ticker": item.get("ticker"), "result": result})
        except Exception as e:
            logger.exception(f"Error sending attention email for {item.get('ticker')}: {e}")
            summary["errors"].append({"ticker": item.get("ticker"), "error": str(e)})
    return summary
