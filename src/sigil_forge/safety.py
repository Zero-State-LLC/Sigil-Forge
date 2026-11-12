"""Lightweight keyword/heuristic safety gate for intent text (v1).

Prefer false negatives over blocking mundane engineering language
(e.g. "kill process"). Harmful categories require multi-word patterns.
"""

from __future__ import annotations

import re

# (compiled pattern, reason) — patterns matched case-insensitively on
# whitespace-normalized text. Multi-word only; single tokens like "kill"
# alone are intentionally not blocked.
_RULES: list[tuple[re.Pattern[str], str]] = [
    # --- Violence against others ---
    (
        re.compile(
            r"\b("
            r"murder\s+\w+"
            # Optional determiner so "kill my neighbor" / "kill the boss" match;
            # non-person objects ("kill process", "kill the theme") stay allowed.
            r"|kill\s+(?:(?:my|the|a|an|our|their)\s+)?(him|her|them|you|someone|"
            r"somebody|people|neighbor|neighbours?|boss|partner|wife|husband|"
            r"friend|enemy|enemies|family|parents?|child|children|kids?|baby|"
            r"babies|everyone|anybody|anyone)\b"
            r"|assassinate\s+\w+"
            r"|stab\s+(?:(?:my|the|a|an|our|their)\s+)?(him|her|them|someone|"
            r"somebody|\w+\s+to\s+death)\b"
            r"|shoot\s+(?:(?:my|the|a|an|our|their)\s+)?(him|her|them|someone|"
            r"somebody)\b"
            r"|poison\s+(?:(?:my|the|a|an|our|their)\s+)?(him|her|them|someone|"
            r"somebody)\b"
            r"|hurt\s+(him|her|them|someone|somebody|people)\b"
            r"|harm\s+(him|her|them|someone|somebody|people|others)\b"
            r"|violence\s+against"
            r")",
            re.I,
        ),
        "refused: violence against others",
    ),
    # --- Self-harm ---
    (
        re.compile(
            r"\b("
            r"kill\s+myself"
            r"|end\s+my\s+life"
            r"|take\s+my\s+own\s+life"
            r"|commit\s+suicide"
            r"|suicide\s+(plan|note|method|attempt|ideation)"
            r"|self[-\s]?harm"
            r"|cut\s+myself"
            r"|hang\s+myself"
            r"|hurt\s+myself"
            r")",
            re.I,
        ),
        "refused: self-harm",
    ),
    # --- Non-consensual control ---
    (
        re.compile(
            r"\b("
            r"force\s+\w+\s+to\s+love"
            r"|make\s+(him|her|them|someone)\s+(love|obey|submit|want)\s+me"
            r"|force\s+(him|her|them|someone)\s+to\s+(love|obey|submit|want)"
            r"|control\s+(his|her|their|someone'?s?)\s+(mind|will|thoughts)"
            r"|non[-\s]?consensual\s+control"
            r"|compel\s+\w+\s+to\s+love"
            r"|bind\s+\w+\s+to\s+(me|my\s+will)"
            r"|enslave\s+(him|her|them|someone)"
            r")",
            re.I,
        ),
        "refused: non-consensual control",
    ),
    # --- Child exploitation ---
    (
        re.compile(
            r"\b("
            r"(child|children|minor|minors|underage|preteen|pre-teen|"
            r"toddler|infant|pedophil\w*)\b.{0,40}\b("
            r"sex|sexual|porn|nude|naked|molest|rape|exploit)"
            r"|(sex|sexual|porn|nude|naked|molest|rape|exploit)\w*"
            r".{0,40}\b(child|children|minor|minors|underage|preteen|"
            r"pre-teen|toddler|infant|pedophil\w*)"
            r"|child\s+porn"
            r"|csam\b"
            r")",
            re.I | re.S,
        ),
        "refused: child exploitation",
    ),
]


def check_intent(text: str) -> tuple[bool, str]:
    """Return (ok, reason). ok=False means refuse; reason explains why.

    Empty/None text is allowed through (normalize/construct handle emptiness).
    Matching is case-insensitive on collapsed whitespace.
    """
    if text is None:
        return True, ""
    s = re.sub(r"\s+", " ", str(text)).strip()
    if not s:
        return True, ""
    for pattern, reason in _RULES:
        if pattern.search(s):
            return False, reason
    return True, ""
