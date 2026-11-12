"""Surface / mode / intensity profiles for wallpaper composition."""

from __future__ import annotations

from typing import Any

SURFACES = (
    "phone_lock",
    "phone_home",
    "tablet",
    "desktop",
    "desktop_ultrawide",
)

MODES = ("stealth", "ambient", "focus", "ritual", "immersive")
INTENSITIES = ("subtle", "balanced", "strong")
PLACEMENTS = (
    "center",
    "upper_third",
    "lower_third",
    "left_field",
    "right_field",
    "custom",
)

# Visual salience bands (not raw alpha) — mapped to opacity ranges
MODE_SALIENCE: dict[str, tuple[float, float]] = {
    "stealth": (0.08, 0.20),
    "ambient": (0.20, 0.40),
    "focus": (0.35, 0.60),
    "ritual": (0.60, 0.90),
    "immersive": (0.40, 0.85),
}

# Default canvas sizes (px)
SURFACE_CANVAS: dict[str, dict[str, Any]] = {
    "phone_lock": {
        "width": 1170,
        "height": 2532,
        "orientation": "portrait",
        "scale": 0.32,
        "placement": "lower_third",
    },
    "phone_home": {
        "width": 1170,
        "height": 2532,
        "orientation": "portrait",
        "scale": 0.24,
        "placement": "upper_third",
    },
    "tablet": {
        "width": 2048,
        "height": 2732,
        "orientation": "portrait",
        "scale": 0.28,
        "placement": "center",
    },
    "desktop": {
        "width": 1920,
        "height": 1080,
        "orientation": "landscape",
        "scale": 0.26,
        "placement": "center",
    },
    "desktop_ultrawide": {
        "width": 3440,
        "height": 1440,
        "orientation": "landscape",
        "scale": 0.22,
        "placement": "right_field",
    },
}

SYMBOLIC_THEMES: dict[str, dict[str, Any]] = {
    "neutral": {"complexity": 0.25, "palette": "charcoal_sand"},
    "saturnine": {"complexity": 0.22, "palette": "lead_black"},
    "jovian": {"complexity": 0.30, "palette": "deep_blue_gold"},
    "martial": {"complexity": 0.35, "palette": "iron_crimson"},
    "solar": {"complexity": 0.35, "palette": "amber_radiance"},
    "venusian": {"complexity": 0.30, "palette": "copper_rose"},
    "mercurial": {"complexity": 0.40, "palette": "technical_glass"},
    "lunar": {"complexity": 0.30, "palette": "mist_silver"},
    "custom": {"complexity": 0.30, "palette": "operator"},
}

STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "obsidian": {
        "materials": ["black stone", "brushed mineral"],
        "lighting": ["low directional"],
        "complexity": 0.25,
    },
    "solar": {
        "materials": ["diffuse luminous atmosphere", "metallic highlights"],
        "geometry": ["radial"],
        "complexity": 0.35,
    },
    "lunar": {
        "materials": ["dark glass", "mist", "subtle water"],
        "lighting": ["diffuse"],
        "complexity": 0.30,
    },
    "cyber": {
        "materials": ["dark composite", "technical glass"],
        "geometry": ["restrained grid"],
        "complexity": 0.45,
    },
    "parchment": {
        "materials": ["aged fiber", "ink wash"],
        "complexity": 0.35,
    },
}


def resolve_opacity(mode: str, intensity: str) -> float:
    lo, hi = MODE_SALIENCE.get(mode, (0.25, 0.5))
    mid = (lo + hi) / 2.0
    if intensity == "subtle":
        return lo + 0.15 * (mid - lo)
    if intensity == "strong":
        return mid + 0.7 * (hi - mid)
    return mid


def resolve_scale(surface: str, mode: str) -> float:
    base = float(SURFACE_CANVAS.get(surface, SURFACE_CANVAS["desktop"])["scale"])
    if mode == "stealth":
        return max(0.12, base * 0.85)
    if mode == "ritual":
        return min(0.45, base * 1.15)
    return base


def placement_xy(placement: str) -> tuple[float, float]:
    """Normalized center of glyph placement (0–1)."""
    table = {
        "center": (0.5, 0.5),
        "upper_third": (0.5, 0.28),
        "lower_third": (0.5, 0.72),
        "left_field": (0.28, 0.5),
        "right_field": (0.72, 0.5),
        "custom": (0.5, 0.5),
    }
    return table.get(placement, (0.5, 0.5))
