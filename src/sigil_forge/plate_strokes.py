"""Stroke-faithful planetary plate digitizations (multi-stroke geometry).

Coordinate spaces:
  - ``kamea_cells``: same as successive seal paths (col+0.5, row+0.5), range ~0..n
  - ``unit_box``: normalized 0..1, mapped to kamea cell space as (x*n, y*n)

Fidelity labels are honest: scholarly vectorizations of the Western ceremonial
plate tradition (Agrippa Book II / Barrett Magus lineage), not unique MS claims
and not Goetic/Enochian authority seals.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from sigil_forge.kamea import KAMEA_SQUARES
from sigil_forge.paths import skill_root

PLATE_REL = Path("references") / "planetary-plate-strokes.json"
PLATE_CORPUS_ID = "planetary_plate_strokes_v1"

KIND_ROLE = {
    "traditional_seal": "traditional_seal",
    "intelligence_character": "intelligence_character",
    "spirit_character": "spirit_character",
}


@lru_cache(maxsize=1)
def load_plate_corpus() -> dict[str, Any]:
    path = skill_root() / PLATE_REL
    if not path.is_file():
        return {
            "plate_corpus_id": PLATE_CORPUS_ID,
            "entries": {},
            "missing": True,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    return data


def plate_corpus_path() -> Path:
    return skill_root() / PLATE_REL


def _find_cell(square: list[list[int]], number: int) -> tuple[int, int] | None:
    for r, row in enumerate(square):
        for c, val in enumerate(row):
            if val == number:
                return r, c
    return None


def successive_path_cells(planet: str) -> list[list[float]]:
    """Cell-center path 1..n² in kamea_cells space."""
    key = planet.strip().lower()
    square = KAMEA_SQUARES[key]
    n_max = len(square) ** 2
    path: list[list[float]] = []
    for v in range(1, n_max + 1):
        cell = _find_cell(square, v)
        if cell is None:
            continue
        r, c = cell
        path.append([float(c + 0.5), float(r + 0.5)])
    return path


def kamea_frame_stroke(order: int) -> list[list[float]]:
    """Outer square of the kamea in cell-corner coordinates (0..n)."""
    n = float(order)
    return [[0.0, 0.0], [n, 0.0], [n, n], [0.0, n], [0.0, 0.0]]


def traditional_plate_strokes(planet: str) -> dict[str, Any]:
    """Plate-style traditional seal: successive path + frame + start/end ticks."""
    key = planet.strip().lower()
    square = KAMEA_SQUARES[key]
    n = len(square)
    main = successive_path_cells(key)
    frame = kamea_frame_stroke(n)
    strokes: list[list[list[float]]] = []
    if main:
        strokes.append(main)
    strokes.append(frame)
    # Start tick at cell 1, end tick at cell n² (short orthogonal marks)
    if main:
        x0, y0 = main[0]
        x1, y1 = main[-1]
        tick = 0.25
        strokes.append([[x0 - tick, y0], [x0 + tick, y0]])
        strokes.append([[x0, y0 - tick], [x0, y0 + tick]])
        strokes.append([[x1 - tick, y1], [x1 + tick, y1]])
        strokes.append([[x1, y1 - tick], [x1, y1 + tick]])
    return {
        "planet": key,
        "kind": "traditional_seal",
        "coordinate_space": "kamea_cells",
        "construction": "successive_plus_frame_plate_v1",
        "strokes": strokes,
        "primary_path": main,
        "successive_values": list(range(1, n * n + 1)),
        "claimed_historical_status": "stroke_digitization_plate_v1",
        "fidelity": "scholarly_stroke_digitization",
        "source": (
            "Agrippa Book II successive seal path + kamea frame presentation "
            "as shown on Western ceremonial plates (Barrett Magus lineage)"
        ),
        "plate_corpus_id": PLATE_CORPUS_ID,
        "generated": True,
    }


def unit_to_kamea_cells(
    strokes: list[list[list[float]]], order: int
) -> list[list[list[float]]]:
    """Map unit_box strokes (0..1) into kamea_cells space (0..order)."""
    n = float(order)
    out: list[list[list[float]]] = []
    for poly in strokes:
        out.append([[float(p[0]) * n, float(p[1]) * n] for p in poly])
    return out


def resolve_plate_entry(planet: str, kind: str) -> dict[str, Any] | None:
    """Return plate stroke payload for planet/kind, or None."""
    key = planet.strip().lower()
    kind = (kind or "").strip().lower()
    if key not in KAMEA_SQUARES:
        return None
    if kind == "traditional_seal":
        return traditional_plate_strokes(key)

    data = load_plate_corpus()
    entries = data.get("entries") or {}
    planet_ent = entries.get(key) or {}
    role = planet_ent.get(kind)
    if not role:
        return None
    strokes = role.get("strokes")
    if not strokes:
        return None
    space = (role.get("coordinate_space") or "unit_box").strip()
    order = len(KAMEA_SQUARES[key])
    if space == "unit_box":
        cells = unit_to_kamea_cells(strokes, order)
    elif space == "kamea_cells":
        cells = [[[float(p[0]), float(p[1])] for p in poly] for poly in strokes]
    else:
        return None
    primary = cells[0] if cells else []
    return {
        "planet": key,
        "kind": kind,
        "coordinate_space": "kamea_cells",
        "source_coordinate_space": space,
        "construction": role.get("construction") or "stroke_digitization_v1",
        "strokes": cells,
        "primary_path": primary,
        "successive_values": list(role.get("cell_anchors") or []),
        "claimed_historical_status": "stroke_digitization_plate_v1",
        "fidelity": role.get("fidelity") or "scholarly_stroke_digitization",
        "source": role.get("source")
        or data.get("source")
        or "planetary-plate-strokes.json",
        "plate_corpus_id": data.get("plate_corpus_id") or PLATE_CORPUS_ID,
        "entity_name_latin": role.get("entity_name_latin"),
        "entity_number": role.get("entity_number"),
        "notes": list(role.get("notes") or []),
        "generated": False,
    }


def flatten_primary(strokes: list[list[list[float]]]) -> list[list[float]]:
    """First non-empty stroke as primary path (back-compat single path)."""
    for poly in strokes:
        if len(poly) >= 2:
            return poly
    return strokes[0] if strokes else []
