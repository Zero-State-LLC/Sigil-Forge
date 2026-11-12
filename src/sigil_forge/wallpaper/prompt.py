"""Background-only prompt contract — never invent the canonical glyph."""

from __future__ import annotations

from typing import Any

from wallpaper.profiles import STYLE_PRESETS

NEGATIVE = (
    "text, typography, letters, writing, numbers, watermark, logo, rune, runes, "
    "sigil, occult symbol, magic circle, pentagram, glyph, pseudo-text, "
    "calligraphy, diagram, UI, app icons"
)

UNIVERSAL = """Create a premium symbolic wallpaper background intended to receive a precise
vector sigil as a separate compositing layer.

The image must NOT contain any letters, numbers, readable writing, logos,
glyphs, occult seals, runes, sigils, diagrams, or pseudo-text.

Visual direction:
{visual_direction}

Symbolic atmosphere:
{symbolic_theme}

Mode:
{mode}

Intensity:
{intensity}

Composition requirements:
- preserve a quiet visual field at {sigil_placement}
- reserve approximately {sigil_scale_percent}% of the composition for the
  later placement of a canonical vector glyph
- avoid strong edges crossing the sigil field
- use depth, light, texture, geometry, atmosphere, and material instead of text
- maintain strong large-scale composition at wallpaper viewing distance
- avoid visual clutter
- no borders unless explicitly requested
- no human figures unless explicitly requested

The canonical sigil will be composited later. Do not attempt to invent,
approximate, imitate, or render it.
"""

PHONE_LOCK = """Create a portrait smartphone lock-screen wallpaper background.

Target character:
{visual_direction}

Symbolic theme:
{symbolic_theme}

The design should feel intentional, atmospheric, and visually powerful without
becoming busy.

Composition:
- portrait orientation
- keep the upper clock region visually quiet
- maintain clean negative space around notification regions
- create a deliberate focal field at {sigil_placement}
- the canonical sigil will later occupy approximately {sigil_scale_percent}%
  of canvas width
- use depth and subtle directional lighting to guide the eye toward that field

Do not render:
- text, numbers, letters, symbols, sigils, runes, logos, pseudo-writing

The final vector sigil is added separately after generation.
"""

PHONE_HOME = """Create a subtle portrait smartphone home-screen wallpaper background.

The wallpaper must remain usable beneath app icons and labels.

Theme:
{symbolic_theme}

Mode:
{mode}

Design requirements:
- lower visual contrast than a lock screen
- broad gradients or restrained texture
- limited small-scale detail
- avoid bright hotspots behind icon regions
- keep {sigil_placement} sufficiently clear for a later vector overlay
- maintain depth without competing with interface elements

Do not render any text, glyphs, runes, sigils, symbols, logos, or pseudo-writing.

The canonical sigil will be composited separately and must remain the only
intent-bearing symbol.
"""

DESKTOP = """Create a cinematic but restrained desktop wallpaper background designed around
a separately composited vector sigil.

Canvas:
{width} × {height}

Visual direction:
{visual_direction}

Symbolic atmosphere:
{symbolic_theme}

Mode:
{mode}

Composition:
- establish one dominant quiet field at {sigil_placement}
- reserve clear visual hierarchy for a vector symbol occupying about
  {sigil_scale_percent}% of canvas width
- preserve practical negative space around likely desktop icon and taskbar areas
- prioritize large compositional forms over fine decorative noise
- create depth using atmosphere, texture, material, lighting, geometry, or landscape
- no readable typography
- no generated symbols

The canonical glyph will be placed later and must not be interpreted or
redrawn by the image model.
"""


def build_background_prompt(spec: dict[str, Any], style_preset: str | None = None) -> dict[str, str]:
    """Return {prompt, negative} for background-only generation."""
    pres = spec["presentation"]
    comp = spec["composition"]
    canvas = spec["canvas"]
    surface = spec["surface"]
    scale_pct = int(round(float(comp["scale"]) * 100))

    base_vars = {
        "visual_direction": pres.get("visual_direction") or "dark architectural minimalism",
        "symbolic_theme": pres.get("symbolic_theme") or "neutral",
        "mode": pres.get("mode") or "focus",
        "intensity": pres.get("intensity") or "balanced",
        "sigil_placement": comp.get("placement") or "center",
        "sigil_scale_percent": scale_pct,
        "width": canvas["width"],
        "height": canvas["height"],
    }

    if surface in ("phone_lock",):
        body = PHONE_LOCK.format(**base_vars)
    elif surface in ("phone_home",):
        body = PHONE_HOME.format(**base_vars)
    elif surface in ("desktop", "desktop_ultrawide", "tablet"):
        body = DESKTOP.format(**base_vars)
    else:
        body = UNIVERSAL.format(**base_vars)

    if style_preset and style_preset in STYLE_PRESETS:
        preset = STYLE_PRESETS[style_preset]
        extra = []
        if preset.get("materials"):
            extra.append("Materials: " + ", ".join(preset["materials"]))
        if preset.get("lighting"):
            extra.append("Lighting: " + ", ".join(preset["lighting"]))
        if preset.get("geometry"):
            extra.append("Geometry: " + ", ".join(preset["geometry"]))
        if extra:
            body = body + "\n\nStyle preset (" + style_preset + "):\n- " + "\n- ".join(extra)

    return {"prompt": body.strip() + "\n", "negative": NEGATIVE}
