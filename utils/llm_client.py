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
        model = model or os.environ.get("LLM_MODEL") or "gpt-4o-mini"

        # ChatOpenAI allows passing base_url via client options if needed; here we use env.
        self.llm = ChatOpenAI(model=model, temperature=temperature)

    def top10_from_posts(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ask LLM to extract top tickers and attention points from normalized posts.

        Returns a dict: {"items": [{"ticker": str, "attention_points": [str], "sources": [str], "heat_score": float}]}
        """
        system = SystemMessage(
            content=(
                "你是金融助手。基于 r/wallstreetbets 的帖子，提取最热的股票并总结需要关注的点。"
                "输出一个 JSON 对象，字段 items 为数组，最多 10 个元素，每个元素包含: "
                "ticker(字符串), attention_points(2-5条简短中文要点), sources(最多3个permalink), heat_score(0-10)。"
                "只输出 JSON，不要其他文本。"
            )
        )

        # Compress posts into a concise prompt to control token usage
        lines: List[str] = []
        for p in posts[:100]:  # cap for POC
            title = p.get("title", "").strip()
            score = p.get("score", 0)
            comments = p.get("num_comments", 0)
            link = p.get("permalink", "")
            lines.append(f"- {title} | score={score} comments={comments} | {link}")
        human = HumanMessage(content="\n".join(lines) or "无帖子")

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
                "你是风控助手。根据行情/历史/新闻与关注点，判断该股票是否需要关注。"
                "采用简化客观规则（热度、新闻脉冲、涨跌幅、成交量异常），但最终给出明确布尔结果。"
                "只输出 JSON：attention_needed(boolean), severity('watch'或'alert'), reasons(<=4条), email{subject, body(<=10行)}。"
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
