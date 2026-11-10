"""Proof of Intent v0.12: domains, commitment, HKDF, merkle, capsule, construct."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from artifact_root import merkle_root
from commitment import commit_intent, public_commitment, verify_commitment
from construct import run as construct_run
from crypto_domains import INTENT_COMMITMENT_V1, domain_join, domain_sha256
from crypto_payload import argon2_available, resolve_kdf
from derivation import hkdf_sha256
from forge_manifest import build_forge_manifest, manifest_digest
from intent_capsule import build_capsule, open_capsule


def test_domain_join_length_prefix_unambiguous():
    a = domain_join(b"D", b"ab", b"c")
    b = domain_join(b"D", b"a", b"bc")
    assert a != b
    assert domain_sha256(INTENT_COMMITMENT_V1, b"x") != domain_sha256(
        INTENT_COMMITMENT_V1, b"y"
    )


def test_commitment_fixed_nonce_stable():
    nonce = bytes(range(32))
    a = commit_intent("i maintain calm focus", nonce=nonce)
    b = commit_intent("i maintain calm focus", nonce=nonce)
    assert a["commitment"] == b["commitment"]
    assert a["scheme"] == "sha256-salted-v1"
    assert verify_commitment("i maintain calm focus", nonce, a["commitment"])
    assert not verify_commitment("other", nonce, a["commitment"])


def test_commitment_different_nonce_differs():
    a = commit_intent("i maintain calm focus", nonce=b"\x00" * 32)
    b = commit_intent("i maintain calm focus", nonce=b"\x01" * 32)
    assert a["commitment"] != b["commitment"]


def test_public_commitment_strips_nonce():
    rec = commit_intent("i maintain calm focus", nonce=b"\x02" * 32)
    pub = public_commitment(rec)
    assert "nonce" not in pub
    assert pub["value"] == rec["commitment"]


def test_hkdf_rfc5869_case1():
    # RFC 5869 Appendix A.1
    ikm = bytes.fromhex("0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b")
    salt = bytes.fromhex("000102030405060708090a0b0c")
    info = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
    okm = hkdf_sha256(ikm, salt=salt, info=info, length=42)
    expected = bytes.fromhex(
        "3cb25f25faacd57a90434f64d0362f2a"
        "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
        "34007208d5b887185865"
    )
    assert okm == expected


def test_merkle_root_stable_and_sensitive():
    leaves = [
        ("intent_digest", "ab" * 32),
        ("intent_commitment", "cd" * 32),
    ]
    r1 = merkle_root(leaves)
    r2 = merkle_root(list(reversed(leaves)))  # sort makes equal
    assert r1 == r2
    r3 = merkle_root(leaves + [("canonical_glyph_digest", "ef" * 32)])
    assert r3 != r1


def test_forge_manifest_forbids_sigil_root():
    m = build_forge_manifest(
        forge_version="0.12.0",
        intent_digest="ab" * 32,
        intent_commitment="cd" * 32,
        mode="creative",
        methods={"spare": {}},
        channels=[],
        glyph_digest="ef" * 32,
    )
    assert "sigil_root" not in m
    d = manifest_digest(m)
    assert len(d) == 64


def test_capsule_roundtrip():
    rec = commit_intent("i maintain calm focus", nonce=b"\x03" * 32)
    cap = build_capsule(
        intent="I maintain calm focus",
        normalized="i maintain calm focus",
        commitment_record=rec,
        passphrase="test-secret",
        forge_version="0.12.0",
        method_manifest_digest="aa" * 32,
        kdf="pbkdf2-sha256",
    )
    dumped = json.dumps(cap)
    assert "commitment_nonce" not in dumped
    assert "i maintain calm focus" not in dumped
    w = open_capsule(cap, "test-secret")
    assert w["normalized_intent"] == "i maintain calm focus"
    with pytest.raises(Exception):
        open_capsule(cap, "wrong")


def test_resolve_kdf_auto():
    name = resolve_kdf("auto")
    assert name in ("argon2id", "pbkdf2-sha256")
    if argon2_available():
        assert name == "argon2id"
    else:
        assert name == "pbkdf2-sha256"


def test_construct_emits_poi_surfaces(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="poi-test-pass",
        proof="commitment",
        kdf="pbkdf2-sha256",
    )
    assert packet.get("intent_commitment", {}).get("value")
    assert packet.get("sigil_root")
    assert "nonce" not in json.dumps(packet.get("intent_commitment"))
    run = Path(packet["artifacts"]["run_dir"])
    assert (run / "forge-manifest.json").is_file()
    assert (run / "artifact-root.json").is_file()
    assert (run / "intent-capsule.json").is_file()
    mf = json.loads((run / "forge-manifest.json").read_text(encoding="utf-8"))
    assert "sigil_root" not in mf
    # public media must not contain plaintext intent
    svg = (run / "glyph.svg").read_text(encoding="utf-8")
    assert "I maintain calm focus" not in svg
    # capsule open
    cap = json.loads((run / "intent-capsule.json").read_text(encoding="utf-8"))
    w = open_capsule(cap, "poi-test-pass")
    assert w["normalized_intent"]


def test_construct_commitment_requires_passphrase(tmp_path: Path):
    with pytest.raises(ValueError, match="passphrase"):
        construct_run(
            "I maintain calm focus",
            out_root=tmp_path,
            kamea_encoding="latin_mod9_v1",
            proof="commitment",
        )


def test_construct_without_passphrase_still_has_commitment_and_root(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        proof="none",
    )
    assert packet.get("intent_commitment")
    assert packet.get("sigil_root")
    run = Path(packet["artifacts"]["run_dir"])
    assert not (run / "intent-capsule.json").is_file()
