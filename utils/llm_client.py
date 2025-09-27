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
        model_kwargs = {"reasoning_effort": reasoning_effort}

        # Initialize ChatOpenAI (LangChain), extra kwargs are passed through
        self.llm = ChatOpenAI(model=model, temperature=temperature, model_kwargs=model_kwargs)

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

        resp = self.llm.invoke([system, human])
        text = resp.content.strip()
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
        system = SystemMessage(
            content=(
                "You are a risk-control assistant. Using price/volume history, recent news, and Stage 1 attention points, decide if this stock needs attention."
                " Apply simple objective signals (heat, news pulses, price change, volume spikes) and produce a clear boolean result."
                " Return only JSON: attention_needed (boolean), severity ('watch'|'alert'), reasons (<=4), email {subject, body (<=10 lines)}."
            )
        )

        import json

        human = HumanMessage(content=json.dumps(item, ensure_ascii=False))
        resp = self.llm.invoke([system, human])
        text = resp.content.strip()
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
