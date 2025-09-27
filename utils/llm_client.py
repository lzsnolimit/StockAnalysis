import os
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from utils.env import load_env


class LLMClient:
    """LangChain-based OpenAI client for structured JSON outputs.

    In tests, you can inject a fake client with the same "top10_from_posts" signature.
    """

    def __init__(self, model: str | None = None, temperature: float = 0.0):
        # Load .env (dotenv) to populate environment variables if present
        load_env()
        api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("LLM_API_KEY/OPENAI_API_KEY is required for LLMClient")
        base_url = os.environ.get("LLM_BASE_URL")
        model = model or os.environ.get("LLM_MODEL") or "gpt-5"
        # Reasoning effort (OpenAI reasoning models): low|medium|high
        reasoning_effort = os.environ.get("LLM_REASONING_EFFORT", "medium")

        # Initialize ChatOpenAI; prefer explicit param to avoid warnings, fallback to model_kwargs
        try:
            self.llm = ChatOpenAI(model=model, temperature=temperature, reasoning_effort=reasoning_effort)
        except TypeError:
            self.llm = ChatOpenAI(model=model, temperature=temperature, model_kwargs={"reasoning_effort": reasoning_effort})

    def top10_from_posts(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ask LLM to extract top tickers and attention points from normalized posts.

        Returns a dict: {"items": [{"ticker": str, "attention_points": [str], "sources": [str], "heat_score": float}]}
        """
        system = SystemMessage(
            content=(
                "You are a financial assistant. From recent r/wallstreetbets posts, extract the top 10 tickers and summarize why they are active."
                " Return a pure JSON object with an `items` array (max 10), each element including:"
                " ticker (string), attention_points (2–5 concise bullets), discussion_highlights (2–4 brief points summarizing recent discussions),"
                " sources (up to 3 permalinks), heat_score (0–10)."
                " Only output JSON — no extra text."
            )
        )

        # Provide richer structured inputs for better analysis
        import json
        def clip(s: str, max_len: int = 300) -> str:
            s = (s or "").strip()
            return s if len(s) <= max_len else s[:max_len] + "…"
        payload: List[Dict[str, Any]] = []
        for p in posts[:200]:  # cap input size for cost control
            payload.append({
                "title": p.get("title", ""),
                "selftext": clip(p.get("selftext", ""), 500),
                "score": int(p.get("score") or 0),
                "num_comments": int(p.get("num_comments") or 0),
                "created_utc": p.get("created_utc"),
                "flair": p.get("flair") or p.get("link_flair_text"),
                "permalink": p.get("permalink", ""),
            })
        human = HumanMessage(content=json.dumps({"posts": payload}, ensure_ascii=False))

        try:
            resp = self.llm.invoke([system, human])
            text = resp.content.strip()
        except Exception:
            return {"items": []}
        # Expect valid JSON; if not valid, return empty structure to let caller fallback
        try:
            import json

            data = json.loads(text)
            if not isinstance(data, dict) or "items" not in data:
                return {"items": []}
            return data
        except Exception:
            return {"items": []}

    def attention_decision(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Ask LLM to decide whether the stock needs attention, with severity and email content.

        Input item structure follows Stage 2 enriched JSON for a single ticker.
        Returns: {"attention_needed": bool, "severity": "watch|alert", "reasons": [str], "email": {"subject": str, "body": str}}
        """
        # Strictness control: relaxed | balanced | strict (default: balanced)
        strictness = (os.environ.get("ATTENTION_STRICTNESS") or "balanced").strip().lower()
        if strictness not in {"relaxed", "balanced", "strict"}:
            strictness = "balanced"

        if strictness == "strict":
            criteria = (
                "You are a conservative trading risk assistant.\n"
                "Decide attention conservatively: attention_needed=true ONLY if a MAJOR event OR strong momentum confirmed by multiple signals.\n"
                "CRITERIA:\n"
                "- MAJOR (any one): earnings today/24h; merger/acquisition; regulatory/SEC action; guidance change; severe outage/scandal.\n"
                "- STRONG momentum (need >=2): |change_pct| >= 3%; volume >= 2x recent avg; clear intraday spike vs recent range; AND heat_score >= 8.\n"
                "- MODERATE (need >=3): |change_pct| >= 2.5%; volume >= 1.7x; multi-day trend >8% with rising volume; Stage1 indicates concrete catalyst.\n"
                "Defaults: If uncertain, set attention_needed=false.\n"
            )
        elif strictness == "relaxed":
            criteria = (
                "You are a pragmatic trading risk assistant aiming to surface a few high-confidence items per run.\n"
                "CRITERIA:\n"
                "- attention_needed=true if ANY MAJOR event OR STRONG momentum + social heat OR >=2 MODERATE signals.\n"
                "- MAJOR (any one): earnings today/24h; merger/acquisition; regulatory/SEC action; guidance change; severe outage/scandal.\n"
                "- STRONG + heat (any one): |change_pct| >= 2%; clear intraday spike; heavy options/YOLO flow noted; AND heat_score >= 7.\n"
                "- MODERATE (need >=2): |change_pct| >= 1.5%; volume >= 1.5x; multi-day trend >5% with rising volume; Stage1 discussion indicates concrete catalyst; heat_score >= 8.\n"
                "Defaults: If uncertain but heat_score >= 8 OR attention_points mention earnings/upgrade/downgrade/guidance, prefer attention_needed=true with severity='watch'.\n"
            )
        else:  # balanced
            criteria = (
                "You are a balanced trading risk assistant: avoid being too strict or too lenient.\n"
                "Aim to flag only genuinely notable items.\n"
                "CRITERIA:\n"
                "- attention_needed=true if MAJOR event OR STRONG momentum + heat OR >=2 MODERATE signals.\n"
                "- MAJOR (any one): earnings today/24h; merger/acquisition; regulatory/SEC action; guidance change; severe outage/scandal.\n"
                "- STRONG + heat (need >=1 strong + heat): |change_pct| >= 2.5% OR volume >= 1.7x OR clear intraday spike; AND heat_score >= 7.\n"
                "- MODERATE (need >=2): |change_pct| >= 2%; volume >= 1.5x; multi-day trend >6% with rising volume; Stage1 indicates concrete catalyst; heat_score >= 8.\n"
                "Defaults: If uncertain, set attention_needed=false unless heat_score >= 9 AND catalyst is mentioned — then 'watch'.\n"
            )

        system = SystemMessage(
            content=(
                criteria
                + "\nSeverity: 'alert' only when MAJOR or STRONG signals; else 'watch'.\n"
                + "Output ONLY JSON: {attention_needed:boolean, severity:'watch'|'alert', reasons:<=4 short bullets, email:{subject, body<=10 lines}}."
                + " Keep bullets crisp and grounded in provided data fields (price, change_pct, volume, attention_points)."
            )
        )

        import json

        human = HumanMessage(content=json.dumps(item, ensure_ascii=False))
        try:
            resp = self.llm.invoke([system, human])
            text = resp.content.strip()
        except Exception:
            return {
                "attention_needed": False,
                "severity": "watch",
                "reasons": ["LLM 调用失败"],
                "email": {"subject": "", "body": ""},
            }
        try:
            data = json.loads(text)
            # Minimal validation
            if not isinstance(data, dict) or "attention_needed" not in data:
                return {
                    "attention_needed": False,
                    "severity": "watch",
                    "reasons": ["LLM 输出无效"],
                    "email": {"subject": "", "body": ""},
                }
            return data
        except Exception:
            return {
                "attention_needed": False,
                "severity": "watch",
                "reasons": ["LLM 调用失败"],
                "email": {"subject": "", "body": ""},
            }
