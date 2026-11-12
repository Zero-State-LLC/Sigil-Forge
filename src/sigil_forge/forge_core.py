"""Pure deterministic forge core (no filesystem, clock, random, network).

Boundary for future zkVM / verifiable computation: intent + config → geometry
and method digests only. Proof-of-Intent commitments (salted) stay outside —
they use per-run nonces.

Side-effecting work (stego, I/O, wallpaper, sealing) remains in construct.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from crypto_payload import intent_digest
from fuse import Layout, build_layout
from kamea import DEFAULT_KAMEA_ENCODING, KAMEA_SQUARES
from spare import reduce_letters


@dataclass(frozen=True)
class ForgeConfig:
    """Deterministic construction inputs (no secrets, no paths)."""

    mode: str = "creative"
    square: str | None = None
    kamea_encoding: str | None = None
    spare_mode: str = "letter_monogram"
    planetary_seal: bool = False
    planetary_seal_kind: str = "traditional_seal"
    planetary_geometry: str = "auto"
    phonetic: bool = False

    def encoding(self) -> str:
        return (self.kamea_encoding or DEFAULT_KAMEA_ENCODING).strip().lower()


@dataclass
class ForgeCoreResult:
    """Pure outputs of compute_forge."""

    normalized: str
    intent_digest: str
    spare_letters: str
    square_name: str
    square_order: int
    layout: Layout
    kamea_encoding: str
    spare_mode: str
    phonetic_requested: bool
    config: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        """Serializable summary without full layout object."""
        return {
            "normalized": self.normalized,
            "intent_digest": self.intent_digest,
            "spare_letters_len": len(self.spare_letters),
            "square_name": self.square_name,
            "square_order": self.square_order,
            "kamea_encoding": self.kamea_encoding,
            "spare_mode": self.spare_mode,
            "phonetic_requested": self.phonetic_requested,
            "config": self.config,
            "monogram_points": len(self.layout.monogram_points or []),
            "kamea_points": len(self.layout.kamea_points or []),
        }


def compute_forge(normalized: str, config: ForgeConfig | None = None) -> ForgeCoreResult:
    """intent (normalized) + config → deterministic layout.

    Raises ValueError if dual craft is empty (same fail-closed as construct).
    """
    if not isinstance(normalized, str) or not normalized.strip():
        raise ValueError("normalized intent required")
    cfg = config or ForgeConfig()
    if cfg.mode not in ("creative", "practice"):
        raise ValueError(f"mode must be 'creative' or 'practice', got {cfg.mode!r}")

    digest = intent_digest(normalized)
    enc = cfg.encoding()
    layout = build_layout(
        normalized,
        digest,
        square_override=cfg.square,
        kamea_encoding=enc,
        spare_mode=cfg.spare_mode,
        include_planetary_seal=cfg.planetary_seal,
        planetary_seal_kind=cfg.planetary_seal_kind,
        planetary_geometry=cfg.planetary_geometry,
    )
    spare = layout.spare_letters or reduce_letters(normalized)
    square_name = layout.square_name
    order = len(KAMEA_SQUARES[square_name])

    if (not layout.monogram_points and not layout.kamea_points) or (
        not spare and not layout.kamea_points
    ):
        raise ValueError(
            "NOT_COMPUTABLE: no monogram or kamea craft geometry after letter "
            "reduction (e.g. all-vowel / no surviving consonants). Rewrite the "
            "intent in present tense with consonants that survive Spare "
            "reduction (drop vowels/y and duplicate letters), then re-run construct."
        )

    return ForgeCoreResult(
        normalized=normalized,
        intent_digest=digest,
        spare_letters=spare,
        square_name=square_name,
        square_order=order,
        layout=layout,
        kamea_encoding=enc,
        spare_mode=cfg.spare_mode,
        phonetic_requested=bool(cfg.phonetic or cfg.spare_mode == "phonetic_mantric"),
        config=asdict(cfg),
    )
