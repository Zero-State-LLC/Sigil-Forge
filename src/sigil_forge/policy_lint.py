"""Cross-cutting product policy: efficacy language + authority-seal request detection.

Default forge stays intent-compression only. This module does not implement
Goetic/Enochian geometry — it refuses/classifies and lints language.
"""
from __future__ import annotations

import re

# Phrase patterns (case-insensitive). Prefer multi-word to reduce false positives.
_EFFICACY = [
    r"\bthis sigil works\b",
    r"\bit will (manifest|work|cause)\b",
    r"\bguarantees? results?\b",
    r"\bproves? (that )?magic\b",
    r"\bcontacts? spirits?\b",
    r"\bmakes? (him|her|them) (love|obey)\b",
    r"\bsupernatural efficacy\b",
    r"\bwill (definitely|certainly) (manifest|come true)\b",
]

_AUTHORITY = [
    (r"\benochian\b", "enochian_seal"),
    (r"\bwatchtower\b", "enochian_seal"),
    (r"\bsigillum\s+dei\b", "enochian_seal"),
    (r"\bgoetic\b", "goetic_seal"),
    (r"\bgoetia\b", "goetic_seal"),
    (r"\bars\s+goetia\b", "goetic_seal"),
    (r"\blesser\s+key\b", "goetic_seal"),
    (r"\bsolomonic (spirit )?seal\b", "goetic_seal"),
    (r"\bdemonic\s+seal\b", "goetic_seal"),
    (r"\bauthority seal\b", "authority_seal"),
    (r"\bspirit seal of binding\b", "authority_seal"),
    (r"\bspirit seal of\b", "authority_seal"),
]

EFFICACY_PATTERNS = [re.compile(p, re.I) for p in _EFFICACY]
AUTHORITY_SEAL_PATTERNS = [(re.compile(p, re.I), fam) for p, fam in _AUTHORITY]


def lint_efficacy_text(text: str) -> list[str]:
    if not text:
        return []
    hits: list[str] = []
    for pat in EFFICACY_PATTERNS:
        if pat.search(text):
            hits.append(f"efficacy_phrase:{pat.pattern}")
    return hits


def assert_no_efficacy(text: str, *, field: str = "text") -> None:
    hits = lint_efficacy_text(text)
    if hits:
        raise ValueError(f"efficacy_policy_violation field={field}: {hits}")


def detect_authority_seal_request(text: str) -> tuple[bool, str | None]:
    if not text:
        return False, None
    for pat, fam in AUTHORITY_SEAL_PATTERNS:
        if pat.search(text):
            return True, fam
    return False, None
