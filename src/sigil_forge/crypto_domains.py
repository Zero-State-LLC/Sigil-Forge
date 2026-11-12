"""Cryptographic domain separators for Sigil-Forge Proof of Intent.

Never hash variable-length material without an explicit domain and length
encoding. Payloads use: domain || u32(len(p0)) || p0 || ...
"""

from __future__ import annotations

import hashlib
import struct

INTENT_COMMITMENT_V1 = b"SIGIL-FORGE/INTENT-COMMITMENT/V1"
ARTIFACT_ROOT_V1 = b"SIGIL-FORGE/ARTIFACT-ROOT/V1"
MERKLE_LEAF_V1 = b"SIGIL-FORGE/MERKLE-LEAF/V1"
MERKLE_NODE_V1 = b"SIGIL-FORGE/MERKLE-NODE/V1"
WALLPAPER_SEED_V1 = b"SIGIL-FORGE/WALLPAPER-SEED/V1"
STEGO_PAYLOAD_V1 = b"SIGIL-FORGE/STEGO/V1"
FORGE_SEED_V1 = b"SIGIL-FORGE/FORGE-SEED/V1"
PROOF_BINDING_V1 = b"SIGIL-FORGE/ZK-PROOF/V1"

# Human-readable domain strings (for JSON public fields)
DOMAIN_STR = {
    "intent_commitment": "SIGIL-FORGE/INTENT-COMMITMENT/V1",
    "artifact_root": "SIGIL-FORGE/ARTIFACT-ROOT/V1",
    "merkle_leaf": "SIGIL-FORGE/MERKLE-LEAF/V1",
    "merkle_node": "SIGIL-FORGE/MERKLE-NODE/V1",
}


def encode_u32(n: int) -> bytes:
    if not (0 <= n <= 0xFFFFFFFF):
        raise ValueError(f"u32 out of range: {n}")
    return struct.pack(">I", n)


def domain_join(domain: bytes, *parts: bytes) -> bytes:
    """domain || u32(len(p0)) || p0 || u32(len(p1)) || p1 || ..."""
    if not isinstance(domain, (bytes, bytearray)):
        raise TypeError("domain must be bytes")
    out = bytearray(domain)
    for p in parts:
        if not isinstance(p, (bytes, bytearray)):
            raise TypeError("parts must be bytes")
        out.extend(encode_u32(len(p)))
        out.extend(p)
    return bytes(out)


def domain_sha256(domain: bytes, *parts: bytes) -> bytes:
    """SHA-256 over domain_join(domain, *parts). Returns raw 32 bytes."""
    return hashlib.sha256(domain_join(domain, *parts)).digest()


def domain_sha256_hex(domain: bytes, *parts: bytes) -> str:
    return domain_sha256(domain, *parts).hex()
