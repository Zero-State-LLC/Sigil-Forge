"""Salted intent commitment (privacy binding; not forge geometry identity).

intent_digest  = SHA-256(normalized)           — compatibility / deterministic forge
intent_commitment = SHA-256(domain||nonce||intent) — per-run privacy binding

The 32-byte nonce must never appear in public media.
"""

from __future__ import annotations

import base64
import os
from typing import Any

from crypto_domains import DOMAIN_STR, INTENT_COMMITMENT_V1, domain_sha256_hex

SCHEME = "sha256-salted-v1"
NONCE_LEN = 32


def commit_intent(
    normalized: str,
    *,
    nonce: bytes | None = None,
) -> dict[str, Any]:
    """Return commitment record. Includes raw nonce for private storage only."""
    if not isinstance(normalized, str) or not normalized:
        raise ValueError("normalized intent required")
    n = nonce if nonce is not None else os.urandom(NONCE_LEN)
    if len(n) != NONCE_LEN:
        raise ValueError(f"nonce must be {NONCE_LEN} bytes, got {len(n)}")
    c_hex = domain_sha256_hex(
        INTENT_COMMITMENT_V1,
        n,
        normalized.encode("utf-8"),
    )
    return {
        "scheme": SCHEME,
        "commitment": c_hex,
        "domain": DOMAIN_STR["intent_commitment"],
        "nonce": n,  # private — strip before public serialize
        "nonce_bytes": NONCE_LEN,
    }


def public_commitment(record: dict[str, Any]) -> dict[str, Any]:
    """Strip private nonce for packets / public media."""
    return {
        "scheme": record["scheme"],
        "value": record["commitment"],
        "domain": record["domain"],
    }


def verify_commitment(
    normalized: str,
    nonce: bytes,
    commitment_hex: str,
) -> bool:
    try:
        rec = commit_intent(normalized, nonce=nonce)
    except ValueError:
        return False
    return rec["commitment"].lower() == (commitment_hex or "").strip().lower()


def nonce_b64(nonce: bytes) -> str:
    return base64.b64encode(nonce).decode("ascii")


def nonce_from_b64(s: str) -> bytes:
    raw = base64.b64decode(s)
    if len(raw) != NONCE_LEN:
        raise ValueError(f"nonce must be {NONCE_LEN} bytes, got {len(raw)}")
    return raw
