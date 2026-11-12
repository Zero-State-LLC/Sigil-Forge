"""AES-256-GCM dispatcher: vetted `cryptography` backend when present, else pure Python.

Same signatures and observable behaviour as `aes_gcm_pure` (a failed
authentication or a bad key/tag/nonce size raises ValueError with the same
messages). The `cryptography` package is optional and never required.

Selection happens at call time via SIGIL_FORGE_AES_BACKEND:
  unset / "auto"   prefer the library, fall back to pure Python
  "pure"           force the built-in pure-Python implementation
  "cryptography"   require the library; RuntimeError if it is missing

Nonces the library rejects (it accepts 8..128 bytes; the pure code accepts any
non-empty nonce) are handled by the pure implementation, so behaviour for those
inputs does not change. Both backends produce identical bytes.
"""
from __future__ import annotations

import os
from typing import Tuple

from sigil_forge import aes_gcm_pure as _pure

try:  # resolved once at import
    from cryptography.exceptions import InvalidTag as _InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
except Exception:  # noqa: BLE001 - ImportError or any broken-install failure
    _AESGCM = None
    _InvalidTag = None

ENV_VAR = "SIGIL_FORGE_AES_BACKEND"
_TAG_LEN = 16
_LIB_NONCE_RANGE = (8, 128)


def _requested() -> str:
    value = os.environ.get(ENV_VAR, "auto").strip().lower() or "auto"
    if value not in ("auto", "pure", "cryptography"):
        raise ValueError(
            f"{ENV_VAR} must be auto, pure or cryptography (got {value!r})"
        )
    return value


def _use_library() -> bool:
    mode = _requested()
    if mode == "pure":
        return False
    if _AESGCM is None:
        if mode == "cryptography":
            raise RuntimeError(
                f"{ENV_VAR}=cryptography but the 'cryptography' package is not "
                "installed (pip install cryptography)"
            )
        return False
    return True


def backend() -> str:
    """Name of the backend the next call will use: 'cryptography' or 'pure-python'."""
    return "cryptography" if _use_library() else "pure-python"


def _nonce_ok_for_library(nonce: bytes) -> bool:
    return _LIB_NONCE_RANGE[0] <= len(nonce) <= _LIB_NONCE_RANGE[1]


def aes_gcm_encrypt(
    key: bytes,
    nonce: bytes,
    plaintext: bytes,
    aad: bytes = b"",
) -> Tuple[bytes, bytes]:
    """AES-GCM encrypt. Returns (ciphertext, tag) with 16-byte tag."""
    if not _use_library() or not _nonce_ok_for_library(nonce):
        return _pure.aes_gcm_encrypt(key, nonce, plaintext, aad)
    if len(key) not in (16, 24, 32):
        raise ValueError("key must be 16, 24, or 32 bytes")
    out = _AESGCM(key).encrypt(nonce, plaintext, aad or None)
    return out[:-_TAG_LEN], out[-_TAG_LEN:]


def aes_gcm_decrypt(
    key: bytes,
    nonce: bytes,
    ciphertext: bytes,
    tag: bytes,
    aad: bytes = b"",
) -> bytes:
    """AES-GCM decrypt. Raises ValueError if authentication fails."""
    if not _use_library() or not _nonce_ok_for_library(nonce):
        return _pure.aes_gcm_decrypt(key, nonce, ciphertext, tag, aad)
    if len(key) not in (16, 24, 32):
        raise ValueError("key must be 16, 24, or 32 bytes")
    if len(tag) != _TAG_LEN:
        raise ValueError("tag must be 16 bytes")
    try:
        return _AESGCM(key).decrypt(nonce, bytes(ciphertext) + bytes(tag), aad or None)
    except _InvalidTag:
        raise ValueError("AES-GCM authentication failed") from None

