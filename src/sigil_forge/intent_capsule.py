"""Intent capsule — sealed witness binding commitment nonce + intent.

Public shell is safe to store with the run. Sealed witness holds plaintext intent
and commitment nonce. Requires passphrase.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sigil_forge.commitment import (
    nonce_b64,
    nonce_from_b64,
    public_commitment,
    verify_commitment,
)
from sigil_forge.crypto_payload import open_intent, seal_intent


def build_capsule(
    *,
    intent: str,
    normalized: str,
    commitment_record: dict[str, Any],
    passphrase: str,
    forge_version: str,
    method_manifest_digest: str | None = None,
    artifact_root: str | None = None,
    kdf: str = "auto",
) -> dict[str, Any]:
    """Build public capsule with sealed witness."""
    nonce = commitment_record["nonce"]
    if not verify_commitment(normalized, nonce, commitment_record["commitment"]):
        raise ValueError("commitment does not match intent/nonce")

    prefer_argon2 = kdf in ("auto", "argon2id")
    if kdf == "pbkdf2-sha256":
        prefer_argon2 = False

    witness = {
        "intent": intent,
        "normalized_intent": normalized,
        "commitment_nonce_b64": nonce_b64(nonce),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    sealed = seal_intent(
        json.dumps(witness, sort_keys=True, separators=(",", ":")),
        passphrase,
        prefer_argon2=prefer_argon2,
    )
    # Force pbkdf2 path when explicitly requested
    if kdf == "pbkdf2-sha256" and sealed.get("kdf") != "pbkdf2-sha256":
        sealed = seal_intent(
            json.dumps(witness, sort_keys=True, separators=(",", ":")),
            passphrase,
            prefer_argon2=False,
        )

    capsule = {
        "schema_version": "1.0.0",
        "crypto_version": 2,
        "commitment": public_commitment(commitment_record),
        "compatibility": {
            "intent_digest": __import__(
                "sigil_forge.crypto_payload", fromlist=["intent_digest"]
            ).intent_digest(normalized),
        },
        "sealed_witness": {
            "algorithm": sealed.get("alg", "aes-256-gcm"),
            "kdf": sealed.get("kdf"),
            "ciphertext_b64": sealed["ciphertext_b64"],
            "nonce_b64": sealed["nonce_b64"],
            "salt_b64": sealed["salt_b64"],
        },
        "public_bindings": {
            "forge_version": forge_version,
            "method_manifest_digest": method_manifest_digest,
            "artifact_root": artifact_root,
        },
    }
    if sealed.get("iterations") is not None:
        capsule["sealed_witness"]["iterations"] = sealed["iterations"]
    if sealed.get("argon2"):
        capsule["sealed_witness"]["argon2"] = sealed["argon2"]
    return capsule


def open_capsule(capsule: dict[str, Any], passphrase: str) -> dict[str, Any]:
    """Decrypt witness; verify commitment; return witness dict + checks."""
    sealed = capsule.get("sealed_witness") or {}
    blob = {
        "alg": sealed.get("algorithm") or sealed.get("alg") or "aes-256-gcm",
        "kdf": sealed.get("kdf") or "pbkdf2-sha256",
        "ciphertext_b64": sealed["ciphertext_b64"],
        "nonce_b64": sealed["nonce_b64"],
        "salt_b64": sealed["salt_b64"],
    }
    if sealed.get("iterations") is not None:
        blob["iterations"] = sealed["iterations"]
    if sealed.get("argon2"):
        blob["argon2"] = sealed["argon2"]
    pt = open_intent(blob, passphrase)
    witness = json.loads(pt)
    nonce = nonce_from_b64(witness["commitment_nonce_b64"])
    pub = capsule.get("commitment") or {}
    c_hex = pub.get("value") or pub.get("commitment") or ""
    if not verify_commitment(witness["normalized_intent"], nonce, c_hex):
        raise ValueError("capsule commitment verification failed")
    return witness


def ciphertext_digest(capsule: dict[str, Any]) -> str:
    import hashlib

    ct = (capsule.get("sealed_witness") or {}).get("ciphertext_b64") or ""
    return hashlib.sha256(ct.encode("ascii")).hexdigest()
