"""Fuse Spare monogram + kamea path + bind/rose into a single layout."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from bind_runes import build_bind_polylines
from kamea import (
    DEFAULT_KAMEA_ENCODING,
    KAMEA_SQUARES,
    build_kamea_path,
    select_square,
)
from rose_cross import build_rose_cross_path
from spare import run_spare

# Canvas is always 0..100
CANVAS = 100.0
VIEW_BOX = (0.0, 0.0, CANVAS, CANVAS)

_MONOGRAM_CX = CANVAS / 2.0
_MONOGRAM_CY = CANVAS / 2.0
_MONOGRAM_RADIUS = 40.0

_INNER_LO = 0.35 * CANVAS
_INNER_HI = 0.65 * CANVAS
_INNER_SPAN = _INNER_HI - _INNER_LO


@dataclass(frozen=True)
class Layout:
    monogram_points: list[tuple[float, float]]
    kamea_points: list[tuple[float, float]]
    view_box: tuple[float, float, float, float]
    spare_letters: str
    square_name: str
    bind_polylines: list[list[tuple[float, float]]] = field(default_factory=list)
    bind_runes: list[str] = field(default_factory=list)
    rose_points: list[tuple[float, float]] = field(default_factory=list)
    rose_slots: list[int] = field(default_factory=list)
    rose_start_marker: list[float] = field(default_factory=list)
    rose_terminal_marker: list[float] = field(default_factory=list)
    kamea_provenance: dict[str, Any] = field(default_factory=dict)
    rose_provenance: dict[str, Any] = field(default_factory=dict)
    spare_result: dict[str, Any] = field(default_factory=dict)
    planetary_seal_path: list[tuple[float, float]] = field(default_factory=list)
    planetary_seal_strokes: list[list[tuple[float, float]]] = field(default_factory=list)
    planetary_seal: dict[str, Any] = field(default_factory=dict)


def _monogram_on_circle(letters: list[str]) -> list[tuple[float, float]]:
    n = len(letters)
    if n == 0:
        return []
    pts: list[tuple[float, float]] = []
    for i in range(n):
        angle = -math.pi / 2.0 + (2.0 * math.pi * i) / n
        x = _MONOGRAM_CX + _MONOGRAM_RADIUS * math.cos(angle)
        y = _MONOGRAM_CY + _MONOGRAM_RADIUS * math.sin(angle)
        pts.append((x, y))
    return pts


def _scale_unit_path(
    raw: list[tuple[float, float]] | list[list[float]], square_name: str
) -> list[tuple[float, float]]:
    if not raw:
        return []
    order = len(KAMEA_SQUARES[square_name])
    if order <= 0:
        return []
    out: list[tuple[float, float]] = []
    for item in raw:
        x, y = float(item[0]), float(item[1])
        sx = _INNER_LO + (x / order) * _INNER_SPAN
        sy = _INNER_LO + (y / order) * _INNER_SPAN
        out.append((sx, sy))
    return out


def build_layout(
    normalized: str,
    digest_hex: str,
    square_override: str | None = None,
    *,
    kamea_encoding: str = DEFAULT_KAMEA_ENCODING,
    spare_mode: str = "letter_monogram",
    include_planetary_seal: bool = False,
    planetary_seal_kind: str = "traditional_seal",
    planetary_geometry: str = "auto",
) -> Layout:
    """Compose multi-method layout on canvas 0..100."""
    spare_res = run_spare(normalized, mode=spare_mode, intent_digest=digest_hex)
    letters = spare_res.letter_sequence
    spare = spare_res.spare_letters
    # Monogram geometry only for letter_monogram mode
    mono = _monogram_on_circle(letters) if spare_mode == "letter_monogram" else []

    square_name = select_square(digest_hex, override=square_override)
    kamea_prov = build_kamea_path(
        letters=normalized,
        square_name=square_name,
        encoding=kamea_encoding,
        letter_list=letters if kamea_encoding.startswith("latin") else None,
    )
    raw_pts = [(p[0], p[1]) for p in kamea_prov.path]
    kamea = _scale_unit_path(raw_pts, square_name)

    bind_polys, bind_runes = build_bind_polylines(spare, cx=50.0, cy=50.0, scale=11.0)

    rose_prov_dict: dict[str, Any] = {}
    rose_pts: list[tuple[float, float]] = []
    rose_slots: list[int] = []
    start_m: list[float] = []
    term_m: list[float] = []
    try:
        rose = build_rose_cross_path(normalized, cx=50.0, cy=50.0, radius=32.0)
        rose_prov_dict = rose.to_dict()
        rose_pts = [(p[0], p[1]) for p in rose.coordinates]
        rose_slots = list(rose.petal_indices)
        start_m = list(rose.start_marker)
        term_m = list(rose.terminal_marker)
    except ValueError as exc:
        rose_prov_dict = {"error": str(exc), "method_id": "rose_cross.hebrew_petal_path"}

    seal_path: list[tuple[float, float]] = []
    seal_strokes: list[list[tuple[float, float]]] = []
    seal_dict: dict[str, Any] = {}
    if include_planetary_seal:
        from planetary_seals import seal_for

        art = seal_for(
            square_name,
            kind=planetary_seal_kind,
            digest_hex=digest_hex,
            geometry=planetary_geometry,
        )
        seal_dict = art.to_dict()
        raw_strokes = art.strokes or ([art.path] if art.path else [])
        for poly in raw_strokes:
            scaled = _scale_unit_path([(p[0], p[1]) for p in poly], square_name)
            if scaled:
                seal_strokes.append(scaled)
        seal_path = (
            seal_strokes[0]
            if seal_strokes
            else _scale_unit_path([(p[0], p[1]) for p in art.path], square_name)
        )

    return Layout(
        monogram_points=mono,
        kamea_points=kamea,
        view_box=VIEW_BOX,
        spare_letters=spare,
        square_name=square_name,
        bind_polylines=bind_polys,
        bind_runes=bind_runes,
        rose_points=rose_pts,
        rose_slots=rose_slots,
        rose_start_marker=start_m,
        rose_terminal_marker=term_m,
        kamea_provenance=kamea_prov.to_dict(),
        rose_provenance=rose_prov_dict,
        spare_result=spare_res.to_dict(),
        planetary_seal_path=seal_path,
        planetary_seal_strokes=seal_strokes,
        planetary_seal=seal_dict,
    )
