import os
from typing import Optional


def load_env(env_path: Optional[str] = None) -> None:
    """Load environment variables from a `.env` file.

    Behavior:
    - If `python-dotenv` is available, use it to load `.env`.
    - Regardless of availability, attempt a manual parse of `.env` to ensure keys are present.
    """
    # Try python-dotenv first (best-effort)
    try:
        from dotenv import load_dotenv, find_dotenv
        if env_path:
            load_dotenv(env_path, override=False)
            candidate = env_path
        else:
            # find .env walking up from CWD
            found = find_dotenv(usecwd=True)
            if found:
                load_dotenv(found, override=False)
                candidate = found
            else:
                load_dotenv(override=False)
                candidate = os.path.join(os.getcwd(), ".env")
    except Exception:
        candidate = env_path or os.path.join(os.getcwd(), ".env")

    # Manual parse fallback (always attempt)
    path = candidate
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    if k and (k not in os.environ or os.environ.get(k) in (None, "")):
                        os.environ[k] = v
        except Exception:
            pass
