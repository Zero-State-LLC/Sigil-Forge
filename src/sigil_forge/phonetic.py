"""Phonetic / mantric sigil compression (non-visual channel).

Compresses intent text to a stable syllable/phoneme-like sequence for
multi-modal carriers. Deterministic string algorithm — semantic meaning is
NOT_COMPUTABLE; provenance binds to intent_digest.
"""

from __future__ import annotations

import re
from typing import Any

_VOWELS = set("aeiouy")


def compress_phonetic(normalized: str) -> list[str]:
    """Reduce to consonant clusters + optional trailing vowel markers.

    Example: "i maintain calm focus" → clusters like "m", "nt", "n", "c", "lm", ...
    Unique-first pass on cluster tokens for stability.
    """
    s = re.sub(r"[^a-z\s]", "", (normalized or "").lower())
    tokens: list[str] = []
    for word in s.split():
        cluster = []
        for ch in word:
            if ch in _VOWELS:
                if cluster:
                    tokens.append("".join(cluster))
                    cluster = []
                # mark vowel nucleus lightly
                tokens.append(f"*{ch}")
            else:
                cluster.append(ch)
        if cluster:
            tokens.append("".join(cluster))
    # unique first-seen (including *vowel markers)
    out: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def build_phonetic_artifact(
    normalized: str,
    *,
    intent_digest: str,
    mode: str = "phonetic_mantric",
) -> dict[str, Any]:
    seq = compress_phonetic(normalized)
    return {
        "kind": "phonetic_sigil",
        "mode": mode,
        "family": "intent_compression",
        "method_id": f"spare.{mode}",
        "determinism": "deterministic_sequence",
        "semantic_verification": "NOT_COMPUTABLE",
        "intent_digest": intent_digest,
        "phoneme_sequence": seq,
        "mantric_form": "-".join(seq),
        "notes": [
            "Phonetic compression is a carrier scaffold, not magical efficacy",
            "No audio file generated in v0.5 (JSON only)",
        ],
    }
