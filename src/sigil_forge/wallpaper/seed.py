"""Deterministic wallpaper generation seeds from forge + presentation config."""

from __future__ import annotations

import hashlib


def wallpaper_seed(
    *,
    intent_digest: str,
    surface: str,
    mode: str,
    symbolic_theme: str,
    schema_version: str = "1.0.0",
) -> int:
    """Derive a stable integer seed (64-bit) for background generation."""
    payload = (
        f"{intent_digest}|{surface}|{mode}|{symbolic_theme}|{schema_version}"
    ).encode("utf-8")
    hex16 = hashlib.sha256(payload).hexdigest()[:16]
    return int(hex16, 16)


def file_sha256(path_or_bytes: str | bytes) -> str:
    h = hashlib.sha256()
    if isinstance(path_or_bytes, bytes):
        h.update(path_or_bytes)
    else:
        with open(path_or_bytes, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    return h.hexdigest()


def wallpaper_payload(
    *,
    intent_digest: str,
    wallpaper_spec_digest: str,
    source_glyph_digest: str,
) -> str:
    """Digest binding for optional wallpaper stego (not plaintext intent)."""
    raw = f"{intent_digest}{wallpaper_spec_digest}{source_glyph_digest}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
