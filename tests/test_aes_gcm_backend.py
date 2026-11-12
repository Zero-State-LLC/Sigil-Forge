"""AES-GCM backend dispatcher: pure-Python and optional `cryptography` agree."""
from __future__ import annotations

import binascii
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sigil_forge import aes_gcm
from sigil_forge import aes_gcm_pure as pure
from sigil_forge.crypto_payload import open_intent, seal_intent

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"
HAVE_LIB = aes_gcm._AESGCM is not None


def _h(s: str) -> bytes:
    return binascii.unhexlify(s.replace(" ", ""))


BACKENDS = [
    "pure",
    pytest.param(
        "cryptography",
        marks=pytest.mark.skipif(not HAVE_LIB, reason="cryptography not installed"),
    ),
]


@pytest.fixture(params=BACKENDS)
def be(request, monkeypatch):
    monkeypatch.setenv(aes_gcm.ENV_VAR, request.param)
    return request.param


# (key, iv, plaintext, aad, ciphertext, tag): McGrew/Viega GCM spec test cases
_K256 = "feffe9928665731c6d6a8f9467308308" * 2
_PT60 = (
    "d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
    "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b39"
)
_AAD = "feedfacedeadbeeffeedfacedeadbeefabaddad2"
VECTORS = {
    # Test Case 13: 256-bit zero key, empty PT/AAD
    "tc13": ("00" * 32, "00" * 12, "", "", "", "530f8afbc74536b9a963b4f1c4cb738b"),
    # Test Case 14: 256-bit zero key, one zero block, no AAD
    "tc14": (
        "00" * 32, "00" * 12, "00" * 16, "",
        "cea7403d4d606b6e074ec5d3baf39d18", "d0d1c8a799996bf0265b98b5d48ab919",
    ),
    # Test Case 16: 256-bit key, 60-byte PT with AAD, 96-bit IV
    "tc16": (
        _K256, "cafebabefacedbaddecaf888", _PT60, _AAD,
        "522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa"
        "8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662",
        "76fc6ece0f4e1768cddf8853bb2d551b",
    ),
    # Test Case 17: as 16 but 64-bit IV (library minimum nonce length)
    "tc17": (
        _K256, "cafebabefacedbad", _PT60, _AAD,
        "c3762df1ca787d32ae47c13bf19844cbaf1ae14d0b976afac52ff7d79bba9de0"
        "feb582d33934a4f0954cc2363bc73f7862ac430e64abe499f47c9b1f",
        "3a337dbf46a792c45e454913fe2ea8f2",
    ),
}


@pytest.mark.parametrize("name", sorted(VECTORS))
def test_known_vectors(be, name):
    key, iv, pt, aad, ect, etag = (_h(x) for x in VECTORS[name])
    ct, tag = aes_gcm.aes_gcm_encrypt(key, iv, pt, aad)
    assert (ct, tag) == (ect, etag)
    assert aes_gcm.aes_gcm_decrypt(key, iv, ct, tag, aad) == pt


def _flip(b: bytes) -> bytes:
    return bytes([b[0] ^ 1]) + b[1:]


def test_auth_failures_raise_valueerror(be):
    key, iv = os.urandom(32), os.urandom(12)
    ct, tag = aes_gcm.aes_gcm_encrypt(key, iv, b"hello world", b"aad")
    with pytest.raises(ValueError, match="authentication failed"):
        aes_gcm.aes_gcm_decrypt(key, iv, ct, _flip(tag), b"aad")
    with pytest.raises(ValueError, match="authentication failed"):
        aes_gcm.aes_gcm_decrypt(key, iv, _flip(ct), tag, b"aad")
    with pytest.raises(ValueError, match="authentication failed"):
        aes_gcm.aes_gcm_decrypt(key, iv, ct, tag, b"other")


def test_bad_sizes_raise_same_valueerror(be):
    iv = os.urandom(12)
    for bad in (b"", b"x" * 15, b"x" * 33):
        with pytest.raises(ValueError, match="key must be"):
            aes_gcm.aes_gcm_encrypt(bad, iv, b"x")
        with pytest.raises(ValueError, match="key must be"):
            aes_gcm.aes_gcm_decrypt(bad, iv, b"x", b"t" * 16)
    with pytest.raises(ValueError, match="tag must be 16"):
        aes_gcm.aes_gcm_decrypt(os.urandom(32), iv, b"x", b"short")
    with pytest.raises(ValueError, match="nonce must be non-empty"):
        aes_gcm.aes_gcm_encrypt(os.urandom(32), b"", b"x")


@pytest.mark.parametrize("nlen", [1, 7, 129, 200])
def test_nonce_lengths_the_library_rejects_use_pure(be, nlen):
    key, nonce = os.urandom(32), os.urandom(nlen)
    ct, tag = aes_gcm.aes_gcm_encrypt(key, nonce, b"payload", b"a")
    assert (ct, tag) == pure.aes_gcm_encrypt(key, nonce, b"payload", b"a")
    assert aes_gcm.aes_gcm_decrypt(key, nonce, ct, tag, b"a") == b"payload"


# --- override behaviour ---


def test_env_pure_forces_pure(monkeypatch):
    monkeypatch.setenv(aes_gcm.ENV_VAR, "pure")
    assert aes_gcm.backend() == "pure-python"


@pytest.mark.skipif(not HAVE_LIB, reason="cryptography not installed")
def test_env_auto_and_unset_prefer_library(monkeypatch):
    monkeypatch.delenv(aes_gcm.ENV_VAR, raising=False)
    assert aes_gcm.backend() == "cryptography"
    monkeypatch.setenv(aes_gcm.ENV_VAR, "auto")
    assert aes_gcm.backend() == "cryptography"
    monkeypatch.setenv(aes_gcm.ENV_VAR, "cryptography")
    assert aes_gcm.backend() == "cryptography"


def test_missing_library_auto_falls_back_and_explicit_errors(monkeypatch):
    monkeypatch.setattr(aes_gcm, "_AESGCM", None)
    monkeypatch.delenv(aes_gcm.ENV_VAR, raising=False)
    assert aes_gcm.backend() == "pure-python"
    key, iv = os.urandom(32), os.urandom(12)
    ct, tag = aes_gcm.aes_gcm_encrypt(key, iv, b"x")
    assert aes_gcm.aes_gcm_decrypt(key, iv, ct, tag) == b"x"
    monkeypatch.setenv(aes_gcm.ENV_VAR, "cryptography")
    with pytest.raises(RuntimeError, match="not installed"):
        aes_gcm.backend()
    with pytest.raises(RuntimeError, match="not installed"):
        aes_gcm.aes_gcm_encrypt(key, iv, b"x")


def test_garbage_env_value_raises(monkeypatch):
    monkeypatch.setenv(aes_gcm.ENV_VAR, "openssl")
    with pytest.raises(ValueError, match=aes_gcm.ENV_VAR):
        aes_gcm.backend()


def test_doctor_reports_aes_backend():
    env = dict(os.environ, **{aes_gcm.ENV_VAR: "pure"})
    out = subprocess.run(
        [sys.executable, str(CLI), "doctor"], capture_output=True, text=True, env=env
    )
    assert json.loads(out.stdout)["aes_backend"] == "pure-python"


# --- cross-backend interchange (needs the library) ---

PAIRS = [("pure", "cryptography"), ("cryptography", "pure")]


@pytest.mark.skipif(not HAVE_LIB, reason="cryptography not installed")
class TestCrossBackend:
    @pytest.mark.parametrize("size", [0, 1, 15, 16, 17, 1000])
    @pytest.mark.parametrize("aad", [b"", b"header"])
    @pytest.mark.parametrize("first,second", PAIRS)
    def test_payloads(self, monkeypatch, size, aad, first, second):
        key, iv, pt = os.urandom(32), os.urandom(12), os.urandom(size)
        monkeypatch.setenv(aes_gcm.ENV_VAR, first)
        ct, tag = aes_gcm.aes_gcm_encrypt(key, iv, pt, aad)
        monkeypatch.setenv(aes_gcm.ENV_VAR, second)
        assert aes_gcm.aes_gcm_decrypt(key, iv, ct, tag, aad) == pt

    @pytest.mark.parametrize("first,second", PAIRS)
    def test_seal_intent(self, monkeypatch, first, second):
        monkeypatch.setenv(aes_gcm.ENV_VAR, first)
        blob = seal_intent("cross backend intent", "pw")
        monkeypatch.setenv(aes_gcm.ENV_VAR, second)
        assert open_intent(blob, "pw") == "cross backend intent"

    @pytest.mark.parametrize("first,second", PAIRS)
    def test_wallpaper_vault(self, monkeypatch, first, second):
        from sigil_forge.wallpaper.vault import (
            open_vault_blob,
            pack_sf12,
            seal_vault,
            unpack_sf12,
        )

        vault = {"schema": "sigil-forge-wallpaper-vault/1", "intent": "calm focus"}
        monkeypatch.setenv(aes_gcm.ENV_VAR, first)
        sealed = seal_vault(vault, "vault-pass", kdf="pbkdf2-sha256")
        env = unpack_sf12(
            pack_sf12(intent_digest="ab" * 32, sigil_root="cd" * 32, sealed_blob=sealed)
        )
        assert env["has_vault"] is True
        monkeypatch.setenv(aes_gcm.ENV_VAR, second)
        assert open_vault_blob(sealed, "vault-pass") == vault
