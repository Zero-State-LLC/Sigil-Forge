"""Intent digest and optional AES-GCM sealing (PBKDF2 default; Argon2id optional)."""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Any

from sigil_forge.aes_gcm import aes_gcm_decrypt, aes_gcm_encrypt

# OWASP Password Storage Cheat Sheet floor for PBKDF2-HMAC-SHA256. Blobs record
# their own count, so images sealed at the earlier 200,000 still open.
DEFAULT_PBKDF2_ITERATIONS = 600_000
MAX_PBKDF2_ITERATIONS = 1_000_000
_SALT_LEN = 16
_NONCE_LEN = 12  # standard 96-bit GCM IV
_TAG_LEN = 16
_REQUIRED_BLOB_KEYS = ("salt_b64", "nonce_b64", "ciphertext_b64")
_ARGON2_TIME = 2
_ARGON2_MEMORY_KIB = 64 * 1024
_ARGON2_PARALLELISM = 2
# Bounds for parameters read back from an untrusted blob.
_ARGON2_MAX_TIME = 16
_ARGON2_MAX_MEMORY_KIB = 256 * 1024
_ARGON2_MAX_PARALLELISM = 16


def intent_digest(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def argon2_available() -> bool:
    try:
        import argon2  # noqa: F401

        return True
    except ImportError:
        return False


def _argon2_params(params: dict[str, Any] | None) -> tuple[int, int, int]:
    """Argon2id cost parameters: the blob's own if recorded, else the defaults."""
    if params is None:
        return _ARGON2_TIME, _ARGON2_MEMORY_KIB, _ARGON2_PARALLELISM
    if not isinstance(params, dict):
        raise ValueError("argon2 parameters must be an object")
    try:
        time_cost = params.get("time_cost", _ARGON2_TIME)
        memory_kib = params.get("memory_kib", _ARGON2_MEMORY_KIB)
        parallelism = params.get("parallelism", _ARGON2_PARALLELISM)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"invalid argon2 parameters: {params!r}") from exc
    for value in (time_cost, memory_kib, parallelism):
        if type(value) is not int:
            raise ValueError(f"invalid argon2 parameters: {params!r}")
    if not (
        1 <= time_cost <= _ARGON2_MAX_TIME
        and 8 <= memory_kib <= _ARGON2_MAX_MEMORY_KIB
        and 1 <= parallelism <= _ARGON2_MAX_PARALLELISM
        and memory_kib >= 8 * parallelism
    ):
        raise ValueError(f"argon2 parameters out of range: {params!r}")
    return time_cost, memory_kib, parallelism


def derive_key(
    passphrase: str,
    salt: bytes,
    iterations: int = DEFAULT_PBKDF2_ITERATIONS,
    *,
    kdf: str = "pbkdf2-sha256",
    argon2_params: dict[str, Any] | None = None,
) -> bytes:
    """Derive 32-byte AES key. kdf: pbkdf2-sha256 (default) or argon2id if installed."""
    kdf = (kdf or "pbkdf2-sha256").lower()
    if kdf == "argon2id":
        try:
            from argon2.low_level import Type, hash_secret_raw
        except ImportError as exc:
            raise ValueError(
                "argon2id requested but argon2 package not installed; use pbkdf2-sha256"
            ) from exc
        time_cost, memory_kib, parallelism = _argon2_params(argon2_params)
        return hash_secret_raw(
            secret=passphrase.encode("utf-8"),
            salt=salt,
            time_cost=time_cost,
            memory_cost=memory_kib,
            parallelism=parallelism,
            hash_len=32,
            type=Type.ID,
        )
    if kdf != "pbkdf2-sha256":
        raise ValueError(f"unsupported kdf: {kdf!r}")
    if not (1 <= iterations <= MAX_PBKDF2_ITERATIONS):
        raise ValueError(
            f"iterations must be in [1, {MAX_PBKDF2_ITERATIONS}], got {iterations}"
        )
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations,
        dklen=32,
    )


def resolve_kdf(kdf: str | None = None, *, prefer_argon2: bool = False) -> str:
    """Return concrete kdf name: argon2id | pbkdf2-sha256.

    ``auto`` (and prefer_argon2=True) selects Argon2id when importable.
    """
    name = (kdf or ("auto" if prefer_argon2 else "pbkdf2-sha256")).strip().lower()
    if name in ("auto",):
        return "argon2id" if argon2_available() else "pbkdf2-sha256"
    if name == "argon2id":
        if not argon2_available():
            raise ValueError(
                "argon2id requested but argon2 package not installed; use auto or pbkdf2-sha256"
            )
        return "argon2id"
    if name in ("pbkdf2-sha256", "pbkdf2"):
        return "pbkdf2-sha256"
    raise ValueError(f"unsupported kdf: {kdf!r}")


def seal_intent(
    plaintext: str,
    passphrase: str,
    *,
    prefer_argon2: bool = False,
    kdf: str | None = None,
) -> dict[str, Any]:
    """Encrypt intent with AES-256-GCM.

    KDF selection:
      - kdf='auto' or prefer_argon2=True → Argon2id if available else PBKDF2
      - kdf='argon2id' / 'pbkdf2-sha256' → explicit
      - default (no args) remains PBKDF2 for backward-compatible call sites
        unless prefer_argon2=True
    """
    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    # Prefer explicit kdf; else prefer_argon2 maps to auto
    if kdf is not None:
        kdf_name = resolve_kdf(kdf)
    elif prefer_argon2:
        kdf_name = resolve_kdf("auto")
    else:
        kdf_name = "pbkdf2-sha256"
    iterations: int | None = DEFAULT_PBKDF2_ITERATIONS if kdf_name == "pbkdf2-sha256" else None
    key = derive_key(
        passphrase,
        salt,
        iterations if iterations is not None else DEFAULT_PBKDF2_ITERATIONS,
        kdf=kdf_name,
    )
    ct, tag = aes_gcm_encrypt(key, nonce, plaintext.encode("utf-8"))
    combined = ct + tag
    out: dict[str, Any] = {
        "ciphertext_b64": base64.b64encode(combined).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "kdf": kdf_name,
        "alg": "aes-256-gcm",
        "crypto_version": 2,
    }
    if kdf_name == "pbkdf2-sha256":
        out["iterations"] = DEFAULT_PBKDF2_ITERATIONS
    else:
        out["argon2"] = {
            "time_cost": _ARGON2_TIME,
            "memory_kib": _ARGON2_MEMORY_KIB,
            "parallelism": _ARGON2_PARALLELISM,
        }
    return out


def open_intent(blob: dict[str, Any], passphrase: str) -> str:
    """Decrypt a seal_intent blob; raises on auth failure / wrong passphrase."""
    if blob.get("alg") != "aes-256-gcm":
        raise ValueError(f"unsupported alg: {blob.get('alg')!r}")
    kdf = (blob.get("kdf") or "pbkdf2-sha256").lower()
    if kdf not in ("pbkdf2-sha256", "argon2id"):
        raise ValueError(f"unsupported kdf: {blob.get('kdf')!r}")
    missing = [k for k in _REQUIRED_BLOB_KEYS if k not in blob]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")
    salt = base64.b64decode(blob["salt_b64"])
    nonce = base64.b64decode(blob["nonce_b64"])
    combined = base64.b64decode(blob["ciphertext_b64"])
    if len(salt) != _SALT_LEN:
        raise ValueError(f"salt must be {_SALT_LEN} bytes, got {len(salt)}")
    if len(nonce) != _NONCE_LEN:
        raise ValueError(f"nonce must be {_NONCE_LEN} bytes, got {len(nonce)}")
    if len(combined) < _TAG_LEN:
        raise ValueError("ciphertext too short")
    ct, tag = combined[:-_TAG_LEN], combined[-_TAG_LEN:]
    if kdf == "pbkdf2-sha256":
        try:
            iterations = int(blob.get("iterations", DEFAULT_PBKDF2_ITERATIONS))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid iterations: {blob.get('iterations')!r}") from exc
        if not (1 <= iterations <= MAX_PBKDF2_ITERATIONS):
            raise ValueError(
                f"iterations must be in [1, {MAX_PBKDF2_ITERATIONS}], got {iterations}"
            )
        key = derive_key(passphrase, salt, iterations, kdf=kdf)
    else:
        key = derive_key(passphrase, salt, kdf=kdf, argon2_params=blob.get("argon2"))
    pt = aes_gcm_decrypt(key, nonce, ct, tag)
    return pt.decode("utf-8")
