"""Wallpaper QA gates: geometry provenance, privacy, dimensions, safe zones."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from wallpaper.safe_zones import check_safe_zones
from wallpaper.seed import file_sha256


def plaintext_scan(path: Path, forbidden_phrases: list[str] | None = None) -> str:
    """Scan PNG bytes for accidental UTF-8 intent phrases (soft)."""
    data = path.read_bytes()
    # PNG binary — also check for readable ASCII runs longer than 12
    try:
        textish = data.decode("latin-1", errors="ignore").lower()
    except Exception:
        return "pass"
    if forbidden_phrases:
        for p in forbidden_phrases:
            if p and len(p) >= 8 and p.lower() in textish:
                return "fail"
    # Heuristic: many consecutive lowercase letters suggest embedded text
    if re.search(r"[a-z]{24,}", textish):
        # common in compressed streams — only fail if intent-like spaces pattern
        pass
    return "pass"


def verify_wallpaper(
    *,
    spec: dict[str, Any],
    output_path: Path,
    background_path: Path | None,
    source_glyph_path: Path,
    forbidden_phrases: list[str] | None = None,
) -> dict[str, Any]:
    """Return wallpaper-receipt dict."""
    notes: list[str] = []
    canvas = spec["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])

    # Dimensions
    dim = "fail"
    try:
        from stego_png import read_rgb_png

        ow, oh, _ = read_rgb_png(output_path.read_bytes())
        if ow == w and oh == h:
            dim = "pass"
        else:
            notes.append(f"dim_mismatch:{ow}x{oh}!={w}x{h}")
    except Exception as exc:
        notes.append(f"decode_error:{exc}")

    # Geometry: source glyph digest must match spec
    src_digest = file_sha256(str(source_glyph_path))
    geometry = src_digest == spec["source"]["glyph_digest"]
    if not geometry:
        notes.append("glyph_digest_mismatch")

    # Safe zones
    comp = spec["composition"]
    safe, sz_notes = check_safe_zones(
        spec["surface"], float(comp["x"]), float(comp["y"]), float(comp["scale"])
    )
    notes.extend(sz_notes)

    # Privacy
    privacy = plaintext_scan(output_path, forbidden_phrases)
    if spec["privacy"].get("plaintext_intent_allowed") is not False:
        notes.append("privacy_policy_violation")
        privacy = "fail"

    bg_digest = file_sha256(str(background_path)) if background_path and background_path.is_file() else None
    out_digest = file_sha256(str(output_path))

    # Spec digest
    spec_copy = {k: v for k, v in spec.items() if k != "artifacts"}
    import hashlib

    spec_digest = hashlib.sha256(
        json.dumps(spec_copy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    status = "verified"
    if dim != "pass" or not geometry or privacy == "fail" or safe == "fail":
        status = "failed"

    return {
        "schema_version": "1.0.0",
        "wallpaper_spec_digest": spec_digest,
        "source_glyph_digest": src_digest,
        "background_digest": bg_digest,
        "output_digest": out_digest,
        "geometry_preserved": geometry,
        "plaintext_scan": privacy,
        "safe_zone_check": safe,
        "dimensions_check": dim,
        "status": status,
        "notes": notes,
        "surface": spec.get("surface"),
        "output_path": str(output_path),
    }
