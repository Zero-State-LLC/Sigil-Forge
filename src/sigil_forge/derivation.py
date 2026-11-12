"""HKDF-SHA256 derivation from public commitment material (RFC 5869).

Derives public deterministic channel parameters only. Does not claim the
commitment is a private master secret. Geometry continues to use intent_digest.
"""

from __future__ import annotations

import hashlib
import hmac

from crypto_domains import FORGE_SEED_V1, WALLPAPER_SEED_V1


def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    if not salt:
        salt = bytes(32)  # HashLen zeros for SHA-256
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    if length < 1 or length > 255 * 32:
        raise ValueError(f"invalid HKDF length: {length}")
    t = b""
    okm = bytearray()
    counter = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        okm.extend(t)
        counter += 1
    return bytes(okm[:length])


def hkdf_sha256(
    ikm: bytes,
    *,
    info: bytes = b"",
    length: int = 32,
    salt: bytes = b"",
) -> bytes:
    prk = hkdf_extract(salt, ikm)
    return hkdf_expand(prk, info, length)


def derive_from_commitment(
    commitment_hex: str,
    domain: bytes,
    *,
    length: int = 32,
) -> bytes:
    """HKDF(ikm=commitment_bytes, info=domain)."""
    clean = (commitment_hex or "").strip().lower()
    if len(clean) != 64 or any(c not in "0123456789abcdef" for c in clean):
        raise ValueError("commitment must be 64 hex chars")
    ikm = bytes.fromhex(clean)
    return hkdf_sha256(ikm, info=domain, length=length)


def forge_seed_bytes(commitment_hex: str) -> bytes:
    return derive_from_commitment(commitment_hex, FORGE_SEED_V1)


def wallpaper_seed_from_commitment(commitment_hex: str) -> int:
    """Optional unlinkable wallpaper seed (64-bit) from commitment."""
    raw = derive_from_commitment(commitment_hex, WALLPAPER_SEED_V1, length=8)
    return int.from_bytes(raw, "big")
