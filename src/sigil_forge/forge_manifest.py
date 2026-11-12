"""Public forge manifest — hashed into sigil_root (never contains sigil_root)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_forge_manifest(
    *,
    forge_version: str,
    intent_digest: str,
    intent_commitment: str,
    mode: str,
    methods: dict[str, Any],
    channels: list[dict[str, Any]],
    glyph_digest: str | None,
    construction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic public manifest (sorted serialization)."""
    # Strip any accidental root
    methods_clean = {k: v for k, v in (methods or {}).items() if k != "sigil_root"}
    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "forge_engine_version": "1",
        "forge_version": forge_version,
        "intent_digest": (intent_digest or "").lower(),
        "intent_commitment": (intent_commitment or "").lower(),
        "mode": mode,
        "methods": methods_clean,
        "channels": [
            {"id": c.get("id"), "status": c.get("status"), "detail": c.get("detail")}
            for c in (channels or [])
        ],
        "output": {
            "geometry_digest": (glyph_digest or "").lower() or None,
        },
        "construction": construction or {"algorithm_version": "construct-v1"},
    }
    if "sigil_root" in manifest:
        raise ValueError("forge_manifest must not contain sigil_root")
    return manifest


def manifest_digest(manifest: dict[str, Any]) -> str:
    if "sigil_root" in manifest:
        raise ValueError("forge_manifest must not contain sigil_root")
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def write_manifest(path: Any, manifest: dict[str, Any]) -> str:
    from pathlib import Path

    p = Path(path)
    p.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_digest(manifest)
