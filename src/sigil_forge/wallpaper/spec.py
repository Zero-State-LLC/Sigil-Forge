"""Build wallpaper-spec.json contracts from a forge run + presentation options."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wallpaper.profiles import (
    SURFACE_CANVAS,
    SYMBOLIC_THEMES,
    placement_xy,
    resolve_opacity,
    resolve_scale,
)
from wallpaper.safe_zones import zones_for
from wallpaper.seed import file_sha256, wallpaper_seed

SCHEMA_VERSION = "1.0.0"


def load_forge_run(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    packet_path = run_dir / "forge-packet.json"
    if not packet_path.is_file():
        raise ValueError(f"forge-packet.json not found in {run_dir}")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    glyph_svg = run_dir / "glyph.svg"
    if not glyph_svg.is_file():
        # fall back to packet artifacts
        gp = (packet.get("artifacts") or {}).get("svg")
        if gp and Path(gp).is_file():
            glyph_svg = Path(gp)
        else:
            raise ValueError(f"glyph.svg not found in {run_dir}")
    return {
        "packet": packet,
        "packet_path": packet_path,
        "glyph_svg": glyph_svg,
        "run_dir": run_dir,
        "run_id": (packet.get("artifacts") or {}).get("run_id") or run_dir.name,
        "intent_digest": packet.get("intent_digest") or "",
    }


def build_wallpaper_spec(
    run_dir: Path,
    *,
    surface: str = "phone_lock",
    mode: str = "focus",
    intensity: str = "balanced",
    placement: str | None = None,
    symbolic_theme: str = "neutral",
    visual_direction: str = "dark architectural minimalism",
    background_method: str = "procedural",
    embedded_payload: str = "intent_digest",
) -> dict[str, Any]:
    """Build a wallpaper-spec dict (contract before render)."""
    if surface not in SURFACE_CANVAS:
        raise ValueError(f"unknown surface {surface!r}")
    canvas_prof = SURFACE_CANVAS[surface]
    place = placement or str(canvas_prof["placement"])
    scale = resolve_scale(surface, mode)
    opacity = resolve_opacity(mode, intensity)
    theme = SYMBOLIC_THEMES.get(symbolic_theme, SYMBOLIC_THEMES["neutral"])
    cx, cy = placement_xy(place)

    forge = load_forge_run(run_dir)
    glyph_path = forge["glyph_svg"]
    glyph_digest = file_sha256(str(glyph_path))
    intent_digest = forge["intent_digest"]
    if not intent_digest or len(intent_digest) != 64:
        raise ValueError("forge packet missing intent_digest")

    seed = wallpaper_seed(
        intent_digest=intent_digest,
        surface=surface,
        mode=mode,
        symbolic_theme=symbolic_theme,
        schema_version=SCHEMA_VERSION,
    )

    complexity = float(theme.get("complexity", 0.3))
    if intensity == "subtle":
        complexity *= 0.8
    elif intensity == "strong":
        complexity = min(1.0, complexity * 1.2)

    glow = {"subtle": 0.15, "balanced": 0.35, "strong": 0.55}.get(intensity, 0.35)

    spec: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "forge_run_id": forge["run_id"],
            "intent_digest": intent_digest,
            "glyph_path": str(glyph_path),
            "glyph_digest": glyph_digest,
            "forge_packet_path": str(forge["packet_path"]),
        },
        "surface": surface,
        "canvas": {
            "width": int(canvas_prof["width"]),
            "height": int(canvas_prof["height"]),
            "orientation": canvas_prof["orientation"],
            "pixel_ratio": 1.0,
        },
        "composition": {
            "placement": place,
            "x": cx,
            "y": cy,
            "scale": scale,
            "rotation": 0.0,
            "safe_zones": zones_for(surface),
        },
        "presentation": {
            "mode": mode,
            "intensity": intensity,
            "symbolic_theme": symbolic_theme,
            "visual_direction": visual_direction,
            "glyph_opacity": round(opacity, 4),
            "stroke_scale": 1.0,
            "glow_strength": glow,
            "background_complexity": round(complexity, 4),
        },
        "privacy": {
            "plaintext_intent_allowed": False,
            "embedded_payload": embedded_payload,
        },
        "generation": {
            "seed": seed,
            "background_method": background_method,
            "provider": None,
            "model": None,
            "prompt_path": None,
            "glyph_composite_method": "vector_render",
        },
        "artifacts": [],  # filled after render
        "transforms": {
            "allowed": [
                "uniform_scaling",
                "translation",
                "rotation",
                "opacity",
                "stroke_width",
                "glow",
                "shadow",
                "colorization",
                "outer_halo",
            ],
            "forbidden": [
                "add_glyph_strokes",
                "remove_glyph_strokes",
                "move_internal_vertices",
                "change_path_topology",
                "ai_redraw_canonical_geometry",
            ],
        },
    }
    return spec
