"""Versioned stego envelopes: SF1, SF11, SF12 (wallpaper vault).

SF1 (v0.10 compat):
  magic SF1\\0 (4) + digest (32) [+ sealed optional]

SF11 (v0.12.1):
  magic SF11 (4) + version u8=1 + flags u8
  + intent_digest (32) + sigil_root (32) + crc32(u32 BE of body before crc)

SF12 (v0.13 wallpaper product):
  magic SF12 + ver + flags + digest32 + root32 + sealed_len + zlib(sealed AES blob) + crc
  Public digests only; full intent/methods in encrypted vault (passphrase).
"""

from __future__ import annotations

import struct
import zlib
from typing import Any, Optional

from stego_png import DIGEST_LEN, MAGIC as SF1_MAGIC

SF11_MAGIC = b"SF11"
SF11_VERSION = 1
# flags bit0: has_digest, bit1: has_root (both always set for v1)
SF11_FLAG_DIGEST = 1 << 0
SF11_FLAG_ROOT = 1 << 1


def _hex_to_32(h: str) -> bytes:
    clean = (h or "").strip().lower()
    if len(clean) != 64 or any(c not in "0123456789abcdef" for c in clean):
        raise ValueError(f"need 64 hex chars, got {h!r}")
    raw = bytes.fromhex(clean)
    if len(raw) != DIGEST_LEN:
        raise ValueError("digest length mismatch")
    return raw


def pack_sf1(digest: bytes, sealed: Optional[bytes] = None) -> bytes:
    from stego_png import pack_payload

    return pack_payload(digest, sealed)


def pack_sf11(*, intent_digest: str, sigil_root: str) -> bytes:
    """Pack SF11 envelope with intent_digest + sigil_root."""
    d = _hex_to_32(intent_digest)
    r = _hex_to_32(sigil_root)
    flags = SF11_FLAG_DIGEST | SF11_FLAG_ROOT
    body = SF11_MAGIC + bytes([SF11_VERSION, flags]) + d + r
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack(">I", crc)


def unpack_envelope(payload: bytes) -> dict[str, Any]:
    """Detect SF1 or SF11 and return structured fields."""
    if len(payload) < 4:
        raise ValueError("payload too short")
    magic = payload[:4]
    if magic == SF1_MAGIC:
        from stego_png import unpack_payload

        digest, sealed = unpack_payload(payload)
        return {
            "format": "SF1",
            "format_version": 1,
            "intent_digest": digest.hex(),
            "sigil_root": None,
            "sealed": sealed,
        }
    if magic == SF11_MAGIC:
        # SF11 | ver | flags | digest32 | root32 | crc4
        need = 4 + 1 + 1 + 32 + 32 + 4
        if len(payload) < need:
            raise ValueError(f"SF11 payload too short: {len(payload)} < {need}")
        ver = payload[4]
        flags = payload[5]
        body = payload[: need - 4]
        (crc_got,) = struct.unpack(">I", payload[need - 4 : need])
        crc_exp = zlib.crc32(body) & 0xFFFFFFFF
        if crc_got != crc_exp:
            raise ValueError("SF11 CRC mismatch")
        if ver != SF11_VERSION:
            raise ValueError(f"unsupported SF11 version {ver}")
        digest = payload[6 : 6 + 32]
        root = payload[6 + 32 : 6 + 64]
        return {
            "format": "SF11",
            "format_version": ver,
            "flags": flags,
            "intent_digest": digest.hex() if flags & SF11_FLAG_DIGEST else None,
            "sigil_root": root.hex() if flags & SF11_FLAG_ROOT else None,
            "sealed": None,
        }
    if magic == b"SF12":
        from wallpaper.vault import unpack_sf12

        return unpack_sf12(payload)
    raise ValueError(f"unknown stego magic {magic!r}")


def pack_auto(
    *,
    intent_digest: str,
    sigil_root: str | None = None,
    sealed: Optional[bytes] = None,
) -> bytes:
    """Prefer SF11 when root present; else SF1."""
    if sigil_root:
        return pack_sf11(intent_digest=intent_digest, sigil_root=sigil_root)
    return pack_sf1(bytes.fromhex(intent_digest.strip().lower()), sealed)


def svg_metadata_payload(
    *,
    intent_digest: str,
    method_bitmap: int = 0,
    sigil_root: str | None = None,
) -> dict[str, Any]:
    """JSON object for sf:payload (v1 digest-only, v2 + root)."""
    d = (intent_digest or "").strip().lower()
    if sigil_root:
        return {
            "v": 2,
            "d": d,
            "r": sigil_root.strip().lower(),
            "m": method_bitmap,
        }
    return {"v": 1, "d": d, "m": method_bitmap}
