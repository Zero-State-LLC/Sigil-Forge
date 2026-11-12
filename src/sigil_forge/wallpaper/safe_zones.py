"""Device safe zones as normalized rectangles (x, y, width, height in 0–1)."""

from __future__ import annotations

from typing import Any

# Zones the sigil should avoid overlapping when possible.
SAFE_ZONES: dict[str, list[dict[str, Any]]] = {
    "phone_lock": [
        {"name": "clock", "x": 0.15, "y": 0.06, "width": 0.70, "height": 0.12},
        {"name": "dynamic_island", "x": 0.30, "y": 0.02, "width": 0.40, "height": 0.05},
        {"name": "notifications", "x": 0.08, "y": 0.22, "width": 0.84, "height": 0.28},
        {"name": "gesture_bar", "x": 0.25, "y": 0.94, "width": 0.50, "height": 0.04},
    ],
    "phone_home": [
        {"name": "status_bar", "x": 0.0, "y": 0.0, "width": 1.0, "height": 0.06},
        {"name": "icon_grid", "x": 0.05, "y": 0.12, "width": 0.90, "height": 0.70},
        {"name": "dock", "x": 0.05, "y": 0.86, "width": 0.90, "height": 0.10},
    ],
    "tablet": [
        {"name": "status_bar", "x": 0.0, "y": 0.0, "width": 1.0, "height": 0.05},
        {"name": "dock", "x": 0.1, "y": 0.88, "width": 0.8, "height": 0.08},
    ],
    "desktop": [
        {"name": "menu_bar", "x": 0.0, "y": 0.0, "width": 1.0, "height": 0.04},
        {"name": "taskbar", "x": 0.0, "y": 0.94, "width": 1.0, "height": 0.06},
        {"name": "icon_column", "x": 0.0, "y": 0.06, "width": 0.12, "height": 0.85},
    ],
    "desktop_ultrawide": [
        {"name": "menu_bar", "x": 0.0, "y": 0.0, "width": 1.0, "height": 0.04},
        {"name": "taskbar", "x": 0.0, "y": 0.94, "width": 1.0, "height": 0.06},
        {"name": "icon_column", "x": 0.0, "y": 0.06, "width": 0.08, "height": 0.85},
    ],
}


def zones_for(surface: str) -> list[dict[str, Any]]:
    return list(SAFE_ZONES.get(surface, SAFE_ZONES["desktop"]))


def rects_overlap(
    ax: float,
    ay: float,
    aw: float,
    ah: float,
    bx: float,
    by: float,
    bw: float,
    bh: float,
) -> bool:
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def glyph_bbox_norm(cx: float, cy: float, scale: float) -> tuple[float, float, float, float]:
    """Approximate glyph bounding box from center and scale (square glyph)."""
    half = scale / 2.0
    return (cx - half, cy - half, scale, scale)


def check_safe_zones(
    surface: str, placement_x: float, placement_y: float, scale: float
) -> tuple[str, list[str]]:
    """Return (pass|fail, notes). Soft check — warn on heavy overlap with critical zones."""
    gx, gy, gw, gh = glyph_bbox_norm(placement_x, placement_y, scale)
    notes: list[str] = []
    critical = {"clock", "dynamic_island", "gesture_bar", "dock", "taskbar", "menu_bar"}
    hard_hits = 0
    for z in zones_for(surface):
        if rects_overlap(gx, gy, gw, gh, z["x"], z["y"], z["width"], z["height"]):
            notes.append(f"overlap:{z['name']}")
            if z["name"] in critical:
                hard_hits += 1
    # Allow mild overlaps; fail only if multiple critical zones hit or glyph huge
    if hard_hits >= 2 or (hard_hits >= 1 and scale > 0.42):
        return "fail", notes
    return "pass", notes
