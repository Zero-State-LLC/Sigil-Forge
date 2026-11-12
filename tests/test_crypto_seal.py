"""Round-trip seal/open and AES-GCM known-vector checks."""
from __future__ import annotations

import binascii

import pytest
from sigil_forge.crypto_payload import open_intent, seal_intent

from sigil_forge.aes_gcm_pure import aes_gcm_decrypt, aes_gcm_encrypt


def test_seal_roundtrip():
    blob = seal_intent("secret intent", "correct horse")
    assert "ciphertext_b64" in blob
    assert "nonce_b64" in blob
    assert "salt_b64" in blob
    assert blob["kdf"] == "pbkdf2-sha256"
    assert blob["alg"] == "aes-256-gcm"
    assert open_intent(blob, "correct horse") == "secret intent"


def test_wrong_passphrase_fails():
    blob = seal_intent("secret intent", "correct horse")
    with pytest.raises(ValueError):
        open_intent(blob, "wrong")


def test_seal_produces_distinct_blobs():
    """Random salt/nonce → different ciphertext each seal."""
    a = seal_intent("same plaintext", "passphrase")
    b = seal_intent("same plaintext", "passphrase")
    assert a["salt_b64"] != b["salt_b64"] or a["nonce_b64"] != b["nonce_b64"]
    assert a["ciphertext_b64"] != b["ciphertext_b64"]


# --- NIST SP 800-38D style AES-256-GCM vectors (12-byte IV) ---


def _h(hexstr: str) -> bytes:
    return binascii.unhexlify(hexstr.replace(" ", ""))


def test_aes_gcm_nist_empty_pt_empty_aad():
    # Key all-zero 256-bit, IV 12 zero bytes, empty PT/AAD
    key = _h("00" * 32)
    iv = _h("00" * 12)
    ct, tag = aes_gcm_encrypt(key, iv, b"", b"")
    assert ct == b""
    assert tag == _h("530f8afbc74536b9a963b4f1c4cb738b")
    assert aes_gcm_decrypt(key, iv, ct, tag, b"") == b""


def test_aes_gcm_nist_with_pt_and_aad():
    # NIST CAVP-style AES-256-GCM (from SP 800-38D examples / known vectors)
    key = _h(
        "feffe9928665731c6d6a8f9467308308"
        "feffe9928665731c6d6a8f9467308308"
    )
    iv = _h("cafebabefacedbaddecaf888")
    pt = _h(
        "d9313225f88406e5a55909c5aff5269a"
        "86a7a9531534f7da2e4c303d8a318a72"
        "1c3c0c95956809532fcf0e2449a6b525"
        "b16aedf5aa0de657ba637b39"
    )
    aad = _h("feedfacedeadbeeffeedfacedeadbeefabaddad2")
    expected_ct = _h(
        "522dc1f099567d07f47f37a32a84427d"
        "643a8cdcbfe5c0c97598a2bd2555d1aa"
        "8cb08e48590dbb3da7b08b1056828838"
        "c5f61e6393ba7a0abcc9f662"
    )
    expected_tag = _h("76fc6ece0f4e1768cddf8853bb2d551b")

    ct, tag = aes_gcm_encrypt(key, iv, pt, aad)
    assert ct == expected_ct
    assert tag == expected_tag
    assert aes_gcm_decrypt(key, iv, ct, tag, aad) == pt


def test_aes_gcm_tampered_tag_fails():
    key = _h("00" * 32)
    iv = _h("00" * 12)
    ct, tag = aes_gcm_encrypt(key, iv, b"hello", b"")
    bad_tag = bytes(b ^ 0x01 for b in tag)
    with pytest.raises(ValueError):
        aes_gcm_decrypt(key, iv, ct, bad_tag, b"")


def test_pbkdf2_default_meets_owasp_floor():
    from sigil_forge import crypto_payload

    assert crypto_payload.DEFAULT_PBKDF2_ITERATIONS >= 600_000
    assert seal_intent("x", "pw")["iterations"] == crypto_payload.DEFAULT_PBKDF2_ITERATIONS


def test_blob_sealed_at_previous_default_still_opens():
    """Images sealed before the default rose record iterations=200000."""
    import base64
    import hashlib
    import os

    salt, nonce = os.urandom(16), os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", b"old-pass", salt, 200_000, dklen=32)
    ct, tag = aes_gcm_encrypt(key, nonce, b"sealed last month")
    blob = {
        "alg": "aes-256-gcm",
        "kdf": "pbkdf2-sha256",
        "iterations": 200_000,
        "salt_b64": base64.b64encode(salt).decode(),
        "nonce_b64": base64.b64encode(nonce).decode(),
        "ciphertext_b64": base64.b64encode(ct + tag).decode(),
    }
    assert open_intent(blob, "old-pass") == "sealed last month"


def test_argon2_blob_opens_with_its_recorded_parameters():
    """Decrypt must use the cost parameters in the blob, not today's defaults."""
    pytest.importorskip("argon2")
    import base64
    import os

    from argon2.low_level import Type, hash_secret_raw

    salt, nonce = os.urandom(16), os.urandom(12)
    params = {"time_cost": 1, "memory_kib": 8 * 1024, "parallelism": 1}
    key = hash_secret_raw(
        secret=b"pw", salt=salt, time_cost=1, memory_cost=8 * 1024,
        parallelism=1, hash_len=32, type=Type.ID,
    )
    ct, tag = aes_gcm_encrypt(key, nonce, b"other parameters")
    blob = {
        "alg": "aes-256-gcm",
        "kdf": "argon2id",
        "argon2": params,
        "salt_b64": base64.b64encode(salt).decode(),
        "nonce_b64": base64.b64encode(nonce).decode(),
        "ciphertext_b64": base64.b64encode(ct + tag).decode(),
    }
    assert open_intent(blob, "pw") == "other parameters"


@pytest.mark.parametrize(
    "params",
    [
        {"time_cost": 10_000},
        {"memory_kib": 64 * 1024 * 1024},
        {"parallelism": 0},
        {"time_cost": "many"},
        {"time_cost": float("inf")},
        {"time_cost": 2.9},
        {"parallelism": True},
        {"memory_kib": 8, "parallelism": 16},
        {"memory_kib": 512 * 1024},
        "not-an-object",
    ],
)
def test_argon2_parameters_from_blob_are_bounded(params):
    from sigil_forge import crypto_payload

    with pytest.raises(ValueError):
        crypto_payload._argon2_params(params)
