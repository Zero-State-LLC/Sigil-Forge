"""ZK-friendly companion commitment (fixed-width preimage for circuits).

C_zk = SHA-256(nonce || intent_bytes_padded_to_256)

Padding bytes after intent_len must be zero. This is separate from the
domain-separated public intent_commitment; both are bound in the capsule.
"""

from __future__ import annotations

import hashlib

from commitment import NONCE_LEN

MAX_INTENT_BYTES = 256


def pad_intent(normalized: str) -> tuple[bytes, int]:
    raw = normalized.encode("utf-8")
    if len(raw) > MAX_INTENT_BYTES:
        raise ValueError(
            f"intent exceeds MAX_INTENT_BYTES={MAX_INTENT_BYTES} (got {len(raw)})"
        )
    n = len(raw)
    padded = raw + b"\x00" * (MAX_INTENT_BYTES - n)
    return padded, n


def zk_commit(normalized: str, nonce: bytes) -> dict[str, str | int]:
    if len(nonce) != NONCE_LEN:
        raise ValueError(f"nonce must be {NONCE_LEN} bytes")
    padded, n = pad_intent(normalized)
    c = hashlib.sha256(nonce + padded).hexdigest()
    return {
        "scheme": "sha256-nonce-pad256-v1",
        "value": c,
        "intent_len": n,
        "max_intent_bytes": MAX_INTENT_BYTES,
    }


def verify_zk_commit(normalized: str, nonce: bytes, commitment_hex: str) -> bool:
    try:
        got = zk_commit(normalized, nonce)["value"]
    except ValueError:
        return False
    return str(got).lower() == (commitment_hex or "").strip().lower()
