"""Geometry-locked AI polish prompt builder (agent-only; no image API).

Builds a host-tool prompt package from a procedural layout summary so polish
may change style/medium/lighting/texture only under geometry locks derived
from the master glyph. Does not call any external image API.
"""

from __future__ import annotations

from typing import Any

from policy_lint import assert_no_efficacy


def _seed_from_digest(digest: str) -> int:
    """First 8 hex chars of intent digest → integer seed (gen_seed channel)."""
    hex_part = (digest or "").strip().lower()
    if not hex_part:
        raise ValueError("intent_digest is required for polish seed")
    # Allow full SHA-256 or shorter prefixes; always take first 8 hex digits.
    clean = "".join(c for c in hex_part if c in "0123456789abcdef")
    if len(clean) < 8:
        raise ValueError("intent_digest must provide at least 8 hex characters")
    return int(clean[:8], 16)


def _format_bbox(bbox: Any) -> str | None:
    if bbox is None:
        return None
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        x, y, w, h = bbox[0], bbox[1], bbox[2], bbox[3]
        return f"bbox x={x} y={y} width={w} height={h}"
    if isinstance(bbox, dict):
        x = bbox.get("x", bbox.get("min_x"))
        y = bbox.get("y", bbox.get("min_y"))
        w = bbox.get("width", bbox.get("w"))
        h = bbox.get("height", bbox.get("h"))
        if None not in (x, y, w, h):
            return f"bbox x={x} y={y} width={w} height={h}"
        if "min_x" in bbox and "max_x" in bbox:
            return (
                f"bbox min=({bbox['min_x']},{bbox.get('min_y', '?')}) "
                f"max=({bbox['max_x']},{bbox.get('max_y', '?')})"
            )
    return str(bbox)


def _geometry_lock(layout_summary: dict) -> str:
    """Short text constraints from stroke count / path bbox."""
    parts: list[str] = []
    stroke_count = layout_summary.get("stroke_count")
    if stroke_count is not None:
        parts.append(f"preserve exactly {stroke_count} primary stroke(s)")
    bbox_txt = _format_bbox(layout_summary.get("bbox") or layout_summary.get("path_bbox"))
    if bbox_txt:
        parts.append(f"keep silhouette within {bbox_txt}")
    path_count = layout_summary.get("path_count")
    if path_count is not None:
        parts.append(f"path count={path_count}")
    view_box = layout_summary.get("view_box")
    if view_box is not None:
        parts.append(f"view_box={view_box}")
    if not parts:
        parts.append("preserve master sigil silhouette and stroke topology")
    parts.append("do not rearrange, add, or remove geometric elements of the glyph")
    return "; ".join(parts)


def build_prompt(layout_summary: dict, style: str | None) -> dict:
    """Build a geometry-locked polish prompt package.

    Parameters
    ----------
    layout_summary:
        Dict with at least ``intent_digest`` (hex). Optional keys used for
        locks: ``stroke_count``, ``bbox`` / ``path_bbox``, ``path_count``,
        ``view_box``.
    style:
        Optional medium/style phrase (e.g. ``\"ink on parchment\"``).

    Returns
    -------
    dict with keys:
        prompt, negative, seed (int from first 8 hex of digest), geometry_lock
    """
    if not isinstance(layout_summary, dict):
        raise TypeError("layout_summary must be a dict")

    digest = layout_summary.get("intent_digest") or layout_summary.get("digest") or ""
    seed = _seed_from_digest(str(digest))
    geometry_lock = _geometry_lock(layout_summary)

    style_phrase = (style or "").strip() or "clean line art, subtle material texture"
    prompt = (
        f"Polish a procedural occult sigil as presentation art. "
        f"Style: {style_phrase}. "
        f"Lock geometry: {geometry_lock}. "
        f"Change only style, medium, lighting, and texture; "
        f"the sigil silhouette must remain the same composition."
    )
    negative = (
        "do not add text, letters, numbers, words, watermarks, logos, or captions; "
        "no readable writing; do not invent new glyphs or extra symbols; "
        "do not crop away the master silhouette; no photoreal faces; "
        "no rearranging stroke order into a different figure"
    )

    package = {
        "prompt": prompt,
        "negative": negative,
        "seed": seed,
        "geometry_lock": geometry_lock,
    }
    # style is optional on the package; when provided it is also embedded in prompt.
    if (style or "").strip():
        package["style"] = (style or "").strip()
    for key in ("prompt", "negative", "geometry_lock", "style"):
        val = package.get(key)
        if isinstance(val, str):
            assert_no_efficacy(val, field=f"polish.{key}")
    return package
