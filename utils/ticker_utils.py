import re
from typing import Optional


_VALID_RE = re.compile(r"^[A-Z]{1,5}(?:\.[A-Z]{1,3})?$")


def normalize_ticker(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.strip().upper()
    if t.startswith("$"):
        t = t[1:]
    # Basic validation (e.g., BRK.B allowed)
    if _VALID_RE.match(t):
        return t
    return None

