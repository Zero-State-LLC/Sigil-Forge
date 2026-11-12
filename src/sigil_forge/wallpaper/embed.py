"""Wallpaper stego binding — digest and sealed vault (product carrier)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from stego_png import DIGEST_LEN, embed_lsb, pack_payload, write_rgb_png
from stego_png import read_rgb_png
from wallpaper.seed import wallpaper_payload


def embed_binding(
    png_path: Path,
    *,
    intent_digest: str,
    wallpaper_spec_digest: str,
    source_glyph_digest: str,
    mode: str = "intent_digest",
    sigil_root: str | None = None,
    sealed_blob: dict[str, Any] | None = None,
) -> str | None:
    """LSB-embed binding into wallpaper PNG.

    mode:
      - none: no-op
      - intent_digest: SF1 digest-only
      - channel_digest: wallpaper_payload digest
      - sf11: digest + sigil_root (public)
      - vault: SF12 public digests + AES-GCM sealed vault (product default)

    Returns new sha256 of file or None if skipped.
    """
    if mode in (None, "none", ""):
        return None
    mode = (mode or "intent_digest").strip().lower()

    try:
        data = png_path.read_bytes()
        w, h, rgb = read_rgb_png(data)
    except Exception:
        return None

    try:
        if mode == "vault":
            if not sealed_blob:
                return None
            from wallpaper.vault import embed_vault_png

            return embed_vault_png(
                png_path,
                intent_digest=intent_digest,
                sigil_root=sigil_root,
                sealed_blob=sealed_blob,
            )

        if mode == "sf11" and sigil_root:
            from stego_envelope import pack_sf11

            payload = pack_sf11(
                intent_digest=intent_digest, sigil_root=sigil_root
            )
        elif mode == "channel_digest":
            digest_hex = wallpaper_payload(
                intent_digest=intent_digest,
                wallpaper_spec_digest=wallpaper_spec_digest,
                source_glyph_digest=source_glyph_digest,
            )
            raw = bytes.fromhex(digest_hex)
            if len(raw) != DIGEST_LEN:
                return None
            payload = pack_payload(raw)
        else:
            # intent_digest / default public
            raw = bytes.fromhex(intent_digest.strip().lower())
            if len(raw) != DIGEST_LEN:
                return None
            payload = pack_payload(raw)

        clean = write_rgb_png(w, h, rgb)
        out = embed_lsb(clean, payload)
        png_path.write_bytes(out)
        from wallpaper.seed import file_sha256

        return file_sha256(str(png_path))
    except Exception:
        return None
