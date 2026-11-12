from __future__ import annotations
import re
import unicodedata


def normalize_intent(text: str) -> str:
    if text is None:
        raise ValueError("intent is required")
    s = unicodedata.normalize("NFKC", str(text))
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    if not s:
        raise ValueError("intent is empty after normalization")
    return s
