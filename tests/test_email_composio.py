import sys
import types

from utils.email_composio import send_stage3_emails


def make_composio_stub():
    stub = types.SimpleNamespace()
    calls = []
    stub.CALLS = calls

    class Tools:
        def get(self, user_id=None, tools=None):
            return [{"slug": "GMAIL_SEND_EMAIL"}]

    class Provider:
        def handle_tool_calls(self, user_id=None, response=None):
            calls.append({"user_id": user_id, "response": response})
            return {"status": "ok"}

    class Composio:
        def __init__(self):
            self.tools = Tools()
            self.provider = Provider()

    stub.Composio = Composio
    return stub


def make_openai_stub():
    stub = types.SimpleNamespace()

    class Completions:
        def create(self, model=None, messages=None, tools=None):
            return {"ok": True, "model": model, "messages": messages, "tools": tools}

    class Chat:
        def __init__(self):
            self.completions = Completions()

    class OpenAI:
        def __init__(self):
            self.chat = Chat()

    stub.OpenAI = OpenAI
    return stub


def test_send_stage3_emails(monkeypatch):
    # Monkeypatch environment
    monkeypatch.setenv("ALERT_RECIPIENTS", "a@example.com,b@example.com")
    monkeypatch.setenv("COMPOSIO_USER_ID", "user123")
    monkeypatch.setenv("LLM_MODEL", "gpt-5")

    # Inject stub modules so no real network/tools are called
    monkeypatch.setitem(sys.modules, "composio", make_composio_stub())
    monkeypatch.setitem(sys.modules, "openai", make_openai_stub())

    analyzed = {
        "items": [
            {
                "ticker": "AAPL",
                "analysis": {
                    "attention_needed": True,
                    "email": {"subject": "Subj AAPL", "body": "Body AAPL"},
                },
            },
            {"ticker": "TSLA", "analysis": {"attention_needed": False}},
            {
                "ticker": "MSFT",
                "analysis": {
                    "attention_needed": True,
                    "email": {"subject": "Subj MSFT", "body": "Body MSFT"},
                },
            },
        ]
    }

    summary = send_stage3_emails(analyzed)
    assert len(summary.get("errors", [])) == 0
    assert len(summary.get("sent", [])) == 2  # two attention-needed items

    # Each sent entry should have two recipients dispatched
    for entry in summary["sent"]:
        result = entry.get("result") or {}
        assert len(result.get("sent", [])) == 2
        assert entry["ticker"] in {"AAPL", "MSFT"}

    # Tool calls recorded: attention items (2) * recipients (2) = 4
    calls = sys.modules["composio"].CALLS
    assert len(calls) == 4

