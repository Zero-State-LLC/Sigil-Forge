"""v0.12.3 hardening: forge_core, dual-commit bind, open --capsule, risc0 stub."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sigil_forge.commitment import commit_intent, public_commitment, verify_commitment
from sigil_forge.construct import run as construct_run
from sigil_forge.forge_core import ForgeConfig, compute_forge
from sigil_forge.intent_capsule import open_capsule
from sigil_forge.normalize import normalize_intent
from sigil_forge.proofs.registry import list_providers
from sigil_forge.proofs.risc0_provider import Risc0Provider
from sigil_forge.proofs.zk_commit import verify_zk_commit, zk_commit

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"


def test_forge_core_deterministic():
    n = normalize_intent("I maintain calm focus")
    cfg = ForgeConfig(mode="creative", kamea_encoding="latin_mod9_v1")
    a = compute_forge(n, cfg)
    b = compute_forge(n, cfg)
    assert a.intent_digest == b.intent_digest
    assert a.square_name == b.square_name
    assert a.layout.monogram_points == b.layout.monogram_points
    assert a.layout.kamea_points == b.layout.kamea_points
    assert len(a.intent_digest) == 64
    pub = a.to_public_dict()
    assert "layout" not in pub
    assert pub["normalized"] == n


def test_forge_core_empty_fail_closed():
    with pytest.raises(ValueError, match=r"^NOT_COMPUTABLE:"):
        compute_forge("aeiou", ForgeConfig(kamea_encoding="latin_mod9_v1"))


def test_construct_uses_forge_core_digest(tmp_path: Path):
    intent = "I maintain calm focus"
    packet = construct_run(
        intent,
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
    )
    n = normalize_intent(intent)
    core = compute_forge(n, ForgeConfig(kamea_encoding="latin_mod9_v1"))
    assert packet["intent_digest"] == core.intent_digest


def test_dual_commit_bind_same_nonce_and_intent():
    """SHA commitment and ZK companion share nonce+intent; both verify together."""
    n = "i maintain calm focus"
    nonce = bytes(range(32))
    rec = commit_intent(n, nonce=nonce)
    zk = zk_commit(n, nonce)
    assert verify_commitment(n, nonce, rec["commitment"])
    assert verify_zk_commit(n, nonce, zk["value"])
    # Wrong intent fails both
    assert not verify_commitment("other intent", nonce, rec["commitment"])
    assert not verify_zk_commit("other intent", nonce, zk["value"])
    # Wrong nonce fails both
    bad = b"\xff" * 32
    assert not verify_commitment(n, bad, rec["commitment"])
    assert not verify_zk_commit(n, bad, zk["value"])
    # Public strip has no nonce
    pub = public_commitment(rec)
    assert "nonce" not in pub
    assert pub["value"] == rec["commitment"]


def test_construct_dual_commit_capsule_bind(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="dual-bind-pass",
        proof="commitment",
        kdf="pbkdf2-sha256",
    )
    c = packet["intent_commitment"]["value"]
    zk = packet["intent_commitment_zk"]["value"]
    assert len(c) == 64 and len(zk) == 64
    assert c != zk  # different schemes/domains
    run = Path(packet["artifacts"]["run_dir"])
    cap = json.loads((run / "intent-capsule.json").read_text(encoding="utf-8"))
    assert (cap.get("public_bindings") or {}).get("intent_commitment_zk") == zk
    # Nonce never public
    dumped = json.dumps(packet) + (run / "glyph.svg").read_text(encoding="utf-8")
    assert "commitment_nonce" not in dumped
    # Capsule open recovers intent; commitments re-verify
    w = open_capsule(cap, "dual-bind-pass")
    from sigil_forge.commitment import nonce_from_b64

    nonce = nonce_from_b64(w["commitment_nonce_b64"])
    assert verify_commitment(w["normalized_intent"], nonce, c)
    assert verify_zk_commit(w["normalized_intent"], nonce, zk)


def test_open_capsule_cli(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="open-cap-pass",
        proof="commitment",
        kdf="pbkdf2-sha256",
    )
    cap_path = Path(packet["artifacts"]["run_dir"]) / "intent-capsule.json"
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "open",
            "--capsule",
            str(cap_path),
            "--passphrase",
            "open-cap-pass",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["source"] == "intent_capsule"
    assert out["normalized_intent"] == "i maintain calm focus"
    assert out.get("commitment", {}).get("value")


def test_open_capsule_wrong_passphrase(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="right-pass",
        proof="commitment",
        kdf="pbkdf2-sha256",
    )
    cap_path = Path(packet["artifacts"]["run_dir"]) / "intent-capsule.json"
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "open",
            "--capsule",
            str(cap_path),
            "--passphrase",
            "wrong-pass",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode != 0
    err = json.loads(r.stderr)
    assert err["ok"] is False


def test_risc0_in_registry_and_skips(tmp_path):
    names = {p["name"] for p in list_providers()}
    assert "risc0" in names
    r0 = Risc0Provider()
    res = r0.prove(
        {"normalized_intent": "i maintain calm focus"},
        {"intent_digest": "00" * 32},
        out_dir=tmp_path / "risc0",
    )
    assert res.status in ("generated", "skipped", "failed")
    if not r0.available():
        assert res.status == "skipped"
        assert "risc0" in res.detail.lower() or "unavailable" in res.detail.lower()


def test_zk_forge_skips_without_guest(tmp_path: Path):
    """zk-forge no longer hard-fails; risc0 path skips when guest unavailable."""
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        proof="zk-forge",
    )
    proof = packet.get("proof") or {}
    assert proof.get("mode") == "zk-forge"
    assert proof.get("provider") == "risc0"
    assert proof.get("status") in ("skipped", "generated", "failed")
    run = Path(packet["artifacts"]["run_dir"])
    assert (run / "proofs" / "proof-manifest.json").is_file()
    # Geometry + PoI surfaces still present
    assert packet.get("intent_digest")
    assert packet.get("intent_commitment")
    assert packet.get("sigil_root")
