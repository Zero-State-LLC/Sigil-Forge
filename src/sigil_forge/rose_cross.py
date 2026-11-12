"""Golden Dawn Rose Cross path — 22 Hebrew petals.

Traces a name through the traditional 22-petal rose arrangement. Latin input
is transliterated to Hebrew via the shared minimal map used for kamea gematria.
Produces ordered coordinates, start marker, and terminal marker.

Distinct from kamea name paths and from planetary seals.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from kamea import HEBREW_VALUES, transliterate_latin_to_hebrew

# Traditional GD-style order of Hebrew letters on the rose petals (Aleph→Tav).
# 22 letters, one per petal.
ROSE_PETALS: tuple[str, ...] = (
    "א",
    "ב",
    "ג",
    "ד",
    "ה",
    "ו",
    "ז",
    "ח",
    "ט",
    "י",
    "כ",
    "ל",
    "מ",
    "נ",
    "ס",
    "ע",
    "פ",
    "צ",
    "ק",
    "ר",
    "ש",
    "ת",
)

ROSE_SLOTS = len(ROSE_PETALS)  # 22
assert ROSE_SLOTS == 22
_PETAL_INDEX = {h: i for i, h in enumerate(ROSE_PETALS)}


@dataclass
class RoseCrossPath:
    method_id: str
    hebrew_sequence: list[str]
    petal_indices: list[int]
    coordinates: list[list[float]]
    start_marker: list[float]
    terminal_marker: list[float]
    transliteration_system: str
    claimed_historical_status: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def petal_point(
    index: int,
    *,
    cx: float = 50.0,
    cy: float = 50.0,
    radius: float = 32.0,
) -> tuple[float, float]:
    """Petal 0 (Aleph) at top (-pi/2); clockwise by index."""
    i = int(index) % ROSE_SLOTS
    angle = -math.pi / 2.0 + (2.0 * math.pi * i) / ROSE_SLOTS
    return (cx + radius * math.cos(angle), cy + radius * math.sin(angle))


def build_rose_path(
    text: str,
    *,
    cx: float = 50.0,
    cy: float = 50.0,
    radius: float = 32.0,
    max_points: int = 22,
) -> tuple[list[tuple[float, float]], list[int]]:
    """Compatibility helper: return (points, petal_indices) for layout fusion.

    Uses Hebrew transliteration + petal lookup (not latin-mod-22).
    """
    art = build_rose_cross_path(text, cx=cx, cy=cy, radius=radius, max_points=max_points)
    pts = [(p[0], p[1]) for p in art.coordinates]
    return pts, list(art.petal_indices)


def build_rose_cross_path(
    text: str,
    *,
    cx: float = 50.0,
    cy: float = 50.0,
    radius: float = 32.0,
    max_points: int = 22,
) -> RoseCrossPath:
    """Full Rose Cross path with start/terminal markers and provenance."""
    hebrew, notes = transliterate_latin_to_hebrew(text)
    # Also accept already-Hebrew characters in input
    for ch in text:
        if ch in HEBREW_VALUES and ch not in hebrew:
            hebrew.append(ch)
    if not hebrew:
        raise ValueError(
            "NOT_COMPUTABLE: Rose Cross requires transliterable name letters"
        )
    hebrew = hebrew[:max_points]
    indices: list[int] = []
    coords: list[list[float]] = []
    for h in hebrew:
        if h not in _PETAL_INDEX:
            # Final forms map to base
            base = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}.get(h, h)
            if base not in _PETAL_INDEX:
                notes.append(f"skip_hebrew:{h!r}")
                continue
            h = base
        idx = _PETAL_INDEX[h]
        indices.append(idx)
        x, y = petal_point(idx, cx=cx, cy=cy, radius=radius)
        coords.append([x, y])
    if len(coords) < 1:
        raise ValueError("NOT_COMPUTABLE: no rose petals after mapping")
    start = list(coords[0])
    terminal = list(coords[-1])
    # Small outward tick markers for start (open circle offset) / terminal
    start_marker = [start[0], start[1] - 2.5]
    terminal_marker = [terminal[0], terminal[1] + 2.5]
    return RoseCrossPath(
        method_id="rose_cross.hebrew_petal_path",
        hebrew_sequence=hebrew[: len(indices)],
        petal_indices=indices,
        coordinates=coords,
        start_marker=start_marker,
        terminal_marker=terminal_marker,
        transliteration_system="latin_to_hebrew_minimal_v1",
        claimed_historical_status="historically_aligned_gd_style",
        notes=notes
        + [
            "22 Hebrew petals; path is name-trace not kamea path",
            "Start/terminal markers are geometric only (no letter labels in public SVG)",
        ],
    )


# Back-compat aliases used by older tests/docs
def letters_for_rose(text: str) -> list[str]:
    heb, _ = transliterate_latin_to_hebrew(text)
    return heb


def letter_to_slot(ch: str) -> int:
    """Deprecated latin slot helper — prefer petal index via Hebrew."""
    if ch in _PETAL_INDEX:
        return _PETAL_INDEX[ch]
    heb, _ = transliterate_latin_to_hebrew(ch)
    if heb and heb[0] in _PETAL_INDEX:
        return _PETAL_INDEX[heb[0]]
    if ch and ch[0].isalpha():
        return (ord(ch[0].lower()) - ord("a")) % ROSE_SLOTS
    return 0
