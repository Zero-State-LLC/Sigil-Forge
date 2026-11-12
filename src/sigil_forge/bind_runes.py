"""Bind-runes craft channel (Elder Futhark → fused stick geometry).

Public historical craft: map latin letters to Elder Futhark where possible,
build simplified stick-figure strokes, and bind them at a shared center with
slight rotational offsets. Not a claim of traditional magical efficacy.
"""

from __future__ import annotations

import math
import re
from typing import Sequence

# Latin → Elder Futhark transliteration (common modern mapping; th/ng digraphs first).
_DIGRAPHS = (("th", "ᚦ"), ("ng", "ᛜ"))
_SINGLE = {
    "a": "ᚨ",
    "b": "ᛒ",
    "c": "ᚲ",
    "d": "ᛞ",
    "e": "ᛖ",
    "f": "ᚠ",
    "g": "ᚷ",
    "h": "ᚺ",
    "i": "ᛁ",
    "j": "ᛃ",
    "k": "ᚲ",
    "l": "ᛚ",
    "m": "ᛗ",
    "n": "ᚾ",
    "o": "ᛟ",
    "p": "ᛈ",
    "q": "ᚲ",
    "r": "ᚱ",
    "s": "ᛊ",
    "t": "ᛏ",
    "u": "ᚢ",
    "v": "ᚹ",
    "w": "ᚹ",
    "x": "ᚲ",
    "y": "ᛃ",
    "z": "ᛉ",
}

# Simplified unit stick paths for each rune glyph (list of polylines in [-1,1] box).
# Geometries are structural proxies for bind composition, not font outlines.
_RUNE_STROKES: dict[str, list[list[tuple[float, float]]]] = {
    "ᚠ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, -0.6), (0.7, -0.9)], [(0.0, -0.1), (0.7, -0.4)]],
    "ᚢ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, 0.2), (0.6, 1.0)]],
    "ᚦ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, -0.5), (0.7, -0.2), (0.0, 0.1)]],
    "ᚨ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, -0.4), (0.7, -0.7)], [(0.0, 0.1), (0.7, -0.2)]],
    "ᚱ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, -0.6), (0.7, -0.9)], [(0.0, -0.1), (0.7, 0.2)]],
    "ᚲ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, -0.2), (0.7, -0.6)]],
    "ᚷ": [[(-0.5, -1.0), (0.5, 1.0)], [(0.5, -1.0), (-0.5, 1.0)]],
    "ᚹ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, -0.5), (0.6, -0.9)], [(0.0, 0.0), (0.6, -0.4)]],
    "ᚺ": [[(0.0, -1.0), (0.0, 1.0)], [(-0.5, -0.3), (0.5, 0.3)]],
    "ᚾ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, -0.3), (0.6, 0.3)]],
    "ᛁ": [[(0.0, -1.0), (0.0, 1.0)]],
    "ᛃ": [[(-0.5, -0.8), (0.5, 0.0), (-0.5, 0.8)]],
    "ᛇ": [[(0.0, -1.0), (0.0, 1.0)], [(-0.4, -0.5), (0.4, 0.5)]],
    "ᛈ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, -0.6), (0.6, -0.3), (0.0, 0.0)]],
    "ᛉ": [[(0.0, -1.0), (0.0, 0.2)], [(-0.5, 1.0), (0.0, 0.2), (0.5, 1.0)]],
    "ᛊ": [[(0.3, -1.0), (-0.3, -0.3), (0.3, 0.3), (-0.3, 1.0)]],
    "ᛏ": [[(0.0, -1.0), (0.0, 1.0)], [(-0.5, -1.0), (0.5, -1.0)]],
    "ᛒ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, -0.7), (0.6, -0.4), (0.0, -0.1)], [(0.0, 0.1), (0.6, 0.4), (0.0, 0.7)]],
    "ᛖ": [[(0.0, -1.0), (0.0, 1.0)], [(-0.5, -0.5), (0.0, 0.0), (-0.5, 0.5)]],
    "ᛗ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, -0.3), (-0.5, 0.3)], [(0.0, -0.3), (0.5, 0.3)]],
    "ᛚ": [[(0.0, -1.0), (0.0, 1.0)], [(0.0, 0.4), (0.5, 1.0)]],
    "ᛜ": [[(-0.5, 0.0), (0.0, -0.7), (0.5, 0.0), (0.0, 0.7), (-0.5, 0.0)]],
    "ᛞ": [[(0.0, -1.0), (0.0, 1.0)], [(-0.5, -0.5), (0.5, 0.5)], [(0.5, -0.5), (-0.5, 0.5)]],
    "ᛟ": [[(0.0, -1.0), (0.0, 1.0)], [(-0.5, -0.3), (0.0, 0.2), (0.5, -0.3)]],
}

_DEFAULT_STROKE = [[(0.0, -1.0), (0.0, 1.0)]]


def latin_to_runes(text: str) -> list[str]:
    """Map latin text to a sequence of Elder Futhark runes (unique order optional)."""
    s = re.sub(r"[^a-z]", "", text.lower())
    out: list[str] = []
    i = 0
    while i < len(s):
        matched = False
        for dig, rune in _DIGRAPHS:
            if s.startswith(dig, i):
                out.append(rune)
                i += len(dig)
                matched = True
                break
        if matched:
            continue
        ch = s[i]
        out.append(_SINGLE.get(ch, "ᛁ"))
        i += 1
    return out


def unique_runes_first_seen(runes: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for r in runes:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _transform(
    strokes: list[list[tuple[float, float]]],
    *,
    cx: float,
    cy: float,
    scale: float,
    angle: float,
) -> list[list[tuple[float, float]]]:
    ca, sa = math.cos(angle), math.sin(angle)
    out: list[list[tuple[float, float]]] = []
    for poly in strokes:
        new_poly: list[tuple[float, float]] = []
        for x, y in poly:
            rx = x * ca - y * sa
            ry = x * sa + y * ca
            new_poly.append((cx + scale * rx, cy + scale * ry))
        out.append(new_poly)
    return out


def build_bind_polylines(
    spare_letters: str,
    *,
    cx: float = 50.0,
    cy: float = 50.0,
    scale: float = 12.0,
    max_runes: int = 8,
) -> tuple[list[list[tuple[float, float]]], list[str]]:
    """Fuse unique runes from spare letters into centered bind strokes.

    Returns (polylines, rune_list_used).
    """
    runes = unique_runes_first_seen(latin_to_runes(spare_letters))[:max_runes]
    if not runes:
        return [], []
    polylines: list[list[tuple[float, float]]] = []
    n = len(runes)
    for i, rune in enumerate(runes):
        strokes = _RUNE_STROKES.get(rune, _DEFAULT_STROKE)
        # Fan angles so bind reads as one composed figure
        angle = (2.0 * math.pi * i) / max(n, 1) * 0.15
        polylines.extend(
            _transform(strokes, cx=cx, cy=cy, scale=scale, angle=angle)
        )
    return polylines, runes
