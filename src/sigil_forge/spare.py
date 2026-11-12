"""Spare method family — letter monogram is the shipped deterministic default.

Spare's corpus describes multiple sigilization methods; this module models a
family. Only ``letter_monogram`` is fully deterministic here. Other modes are
registered with honest determinism labels (see ontology.SPARE_MODES).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ontology import SPARE_MODES

_VOWELS = set("aeiouy")

DEFAULT_SPARE_MODE = "letter_monogram"


def letter_sequence(normalized: str) -> list[str]:
    """Spare letter_monogram: a–z, strip vowels, unique first-seen."""
    chars = re.findall(r"[a-z]", normalized.lower())
    out: list[str] = []
    seen: set[str] = set()
    for ch in chars:
        if ch in _VOWELS:
            continue
        if ch in seen:
            continue
        seen.add(ch)
        out.append(ch)
    return out


def reduce_letters(normalized: str) -> str:
    return "".join(letter_sequence(normalized))


@dataclass
class SpareResult:
    mode: str
    determinism: str
    status: str
    spare_letters: str
    letter_sequence: list[str]
    semantic_verification: str
    notes: list[str] = field(default_factory=list)
    artifact: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "determinism": self.determinism,
            "status": self.status,
            "spare_letters": self.spare_letters,
            "letter_sequence": self.letter_sequence,
            "semantic_verification": self.semantic_verification,
            "notes": self.notes,
            "artifact": self.artifact,
            "family": "intent_compression",
            "method_id": f"spare.{self.mode}",
        }


def run_spare(
    normalized: str,
    *,
    mode: str = DEFAULT_SPARE_MODE,
    intent_digest: str | None = None,
) -> SpareResult:
    """Execute a Spare family mode.

    ``letter_monogram`` — deterministic reduction.
    ``pictorial`` / ``automatic_form`` / ``phonetic_mantric`` — assisted seeds
    with semantic verification NOT_COMPUTABLE (digest-bound provenance only).
    """
    mode = (mode or DEFAULT_SPARE_MODE).strip().lower()
    if mode not in SPARE_MODES:
        raise ValueError(
            f"unknown spare mode {mode!r}; allowed: {', '.join(SPARE_MODES)}"
        )
    meta = SPARE_MODES[mode]
    seq = letter_sequence(normalized)
    letters = "".join(seq)

    if mode == "letter_monogram":
        return SpareResult(
            mode=mode,
            determinism=meta["determinism"],
            status=meta["status"],
            spare_letters=letters,
            letter_sequence=seq,
            semantic_verification="VERIFIED_geometry_from_letters",
            notes=["Default deterministic Spare letter-monogram method"],
        )

    # Assisted / deferred modes: produce provenance-bound seed material only
    seed = (intent_digest or "")[:16]
    artifact = {
        "kind": f"spare_{mode}_seed",
        "digest_prefix": seed,
        "letter_scaffold": letters,
        "constraints": {
            "do_not_claim_deterministic_geometry": True,
            "semantic_meaning": "NOT_COMPUTABLE",
        },
    }
    return SpareResult(
        mode=mode,
        determinism=meta["determinism"],
        status=meta["status"],
        spare_letters=letters,
        letter_sequence=seq,
        semantic_verification="NOT_COMPUTABLE",
        notes=[
            f"Spare mode {mode}: assisted/deferred — provenance verified via digest binding only",
            "Not equivalent to letter_monogram geometry",
        ],
        artifact=artifact,
    )
