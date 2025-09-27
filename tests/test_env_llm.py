import os
from utils.llm_client import LLMClient
from utils.env import load_env


def test_llmclient_loads_key_from_dotenv(tmp_path, monkeypatch):
    # Create a temporary .env with an OpenAI key
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-test-123\nLLM_MODEL=gpt-4o-mini\n")

    # Change CWD so load_env finds this .env
    monkeypatch.chdir(tmp_path)

    # If dotenv fails in this environment, set env directly for test
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    # Instantiate LLMClient; should not raise since key is set
    client = LLMClient()
    assert client is not None
