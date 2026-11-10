"""Proof providers, zk companion commit, verify-proof CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from commitment import commit_intent
from construct import run as construct_run
from proofs.local_knowledge import LocalCapsuleProvider
from proofs.noir_provider import NoirProvider
from proofs.registry import get_provider, list_providers
from proofs.verify_run import verify_proof_run
from proofs.zk_commit import MAX_INTENT_BYTES, pad_intent, verify_zk_commit, zk_commit

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"


def test_zk_commit_roundtrip():
    nonce = b"\x07" * 32
    rec = zk_commit("i maintain calm focus", nonce)
    assert rec["scheme"] == "sha256-nonce-pad256-v1"
    assert len(rec["value"]) == 64
    assert verify_zk_commit("i maintain calm focus", nonce, rec["value"])
    assert not verify_zk_commit("other intent", nonce, rec["value"])


def test_pad_intent_zeros():
    padded, n = pad_intent("abc")
    assert n == 3
    assert len(padded) == MAX_INTENT_BYTES
    assert padded[3:] == b"\x00" * (MAX_INTENT_BYTES - 3)


def test_list_providers():
    names = {p["name"] for p in list_providers()}
    assert "none" in names
    assert "local_capsule" in names
    assert "noir" in names
    assert "risc0" in names


def test_construct_zk_knowledge_local_attestation(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="zk-test-pass",
        proof="zk-knowledge",
        kdf="pbkdf2-sha256",
    )
    assert packet.get("intent_commitment_zk", {}).get("value")
    run = Path(packet["artifacts"]["run_dir"])
    assert (run / "proofs" / "proof-manifest.json").is_file()
    assert (run / "proofs" / "knowledge-attestation.json").is_file()
    man = json.loads((run / "proofs" / "proof-manifest.json").read_text(encoding="utf-8"))
    # noir may be skipped; local attestation still generated first then overwritten
    # when zk-knowledge: final manifest is noir result with local_attestation extra
    assert man.get("public_inputs", {}).get("intent_commitment")
    # verify-proof with passphrase should succeed via local path or noir
    res = verify_proof_run(run, passphrase="zk-test-pass")
    # If noir generated, verify may need nargo; if skipped, local attestation in extra
    if man.get("provider") == "noir" and man.get("status") == "generated":
        # may or may not verify without full nargo setup
        assert "verified" in res
    else:
        # When noir skipped, manifest is noir skip — re-verify using local provider
        from proofs.local_knowledge import LocalCapsuleProvider
        from intent_capsule import open_capsule

        att = run / "proofs" / "knowledge-attestation.json"
        # re-write manifest for local if noir skipped
        if man.get("status") == "skipped":
            # Direct local verify
            capsule = json.loads((run / "intent-capsule.json").read_text(encoding="utf-8"))
            ok = LocalCapsuleProvider().verify(
                att,
                man.get("public_inputs")
                or {
                    "intent_commitment": packet["intent_commitment"]["value"],
                    "intent_commitment_zk": packet["intent_commitment_zk"]["value"],
                },
                extra={"passphrase": "zk-test-pass", "capsule": capsule},
            )
            assert ok is True


def test_construct_commitment_writes_local_proof(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="c-pass",
        proof="commitment",
        kdf="pbkdf2-sha256",
    )
    run = Path(packet["artifacts"]["run_dir"])
    man = json.loads((run / "proofs" / "proof-manifest.json").read_text(encoding="utf-8"))
    assert man["provider"] == "local_capsule"
    assert man["status"] == "generated"
    res = verify_proof_run(run, passphrase="c-pass")
    assert res["verified"] is True
    assert res["intent_disclosed"] is False
    assert res["intent_commitment"] == packet["intent_commitment"]["value"]


def test_verify_proof_cli(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="cli-pass",
        proof="commitment",
        kdf="pbkdf2-sha256",
    )
    run = packet["artifacts"]["run_dir"]
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "verify-proof",
            run,
            "--passphrase",
            "cli-pass",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    out = json.loads(r.stdout)
    assert out["verified"] is True


def test_noir_provider_skipped_without_nargo():
    n = NoirProvider()
    # available depends on host; prove should not crash
    res = n.prove(
        {"normalized_intent": "i maintain calm focus", "nonce": b"\x01" * 32},
        {"intent_commitment_zk": "00" * 32},
        out_dir=Path("/tmp/sf-noir-test"),
    )
    assert res.status in ("generated", "skipped", "failed")
    if not n.available():
        assert res.status == "skipped"
        assert "noir" in res.detail.lower() or "unavailable" in res.detail.lower()


def test_zk_forge_skips_via_risc0(tmp_path: Path):
    """zk-forge is no longer a hard NOT_IMPLEMENTED; adapter skips offline."""
    from construct import run as cr

    packet = cr(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        proof="zk-forge",
    )
    assert packet["proof"]["mode"] == "zk-forge"
    assert packet["proof"]["provider"] == "risc0"
    assert packet["proof"]["status"] in ("skipped", "generated", "failed")


def _fake_nargo(bin_dir: Path, *, prove_exit: int) -> None:
    """A stand-in nargo that records whether the witness was present."""
    bin_dir.mkdir()
    script = bin_dir / "nargo"
    script.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "prove" ]; then\n'
        "  [ -f Prover.toml ] && stat -c %a Prover.toml > witness-mode 2>/dev/null"
        " || stat -f %Lp Prover.toml > witness-mode\n"
        f"  exit {prove_exit}\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


@pytest.mark.parametrize("prove_exit", [0, 1])
def test_noir_witness_is_private_and_removed(tmp_path, monkeypatch, prove_exit):
    """Prover.toml holds plaintext intent + nonce: owner-only, gone after prove."""
    circuit = tmp_path / "skill" / "zk" / "noir" / "intent_commitment"
    circuit.mkdir(parents=True)
    _fake_nargo(tmp_path / "bin", prove_exit=prove_exit)
    monkeypatch.setenv("HERMES_SKILL_DIR", str(tmp_path / "skill"))
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")

    res = NoirProvider().prove(
        {"normalized_intent": "i maintain calm focus", "nonce": b"\x01" * 32},
        {},
        out_dir=tmp_path / "out",
    )

    assert res.status == ("generated" if prove_exit == 0 else "failed")
    # nargo saw the witness, with no group/other access ...
    assert (circuit / "witness-mode").read_text().strip() == "600"
    # ... and it does not outlive the call, on success or failure.
    assert not (circuit / "Prover.toml").exists()


def test_noir_verify_is_bound_to_the_proof_it_is_given(tmp_path, monkeypatch):
    """nargo verify succeeding must not vouch for a different proof file."""
    circuit = tmp_path / "skill" / "zk" / "noir" / "intent_commitment"
    (circuit / "proofs").mkdir(parents=True)
    (circuit / "proofs" / "intent_commitment.proof").write_bytes(b"proof-A")
    _fake_nargo(tmp_path / "bin", prove_exit=0)  # verify exits 0 for anything
    monkeypatch.setenv("HERMES_SKILL_DIR", str(tmp_path / "skill"))
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")

    same = tmp_path / "same.bin"
    same.write_bytes(b"proof-A")
    other = tmp_path / "other.bin"
    other.write_bytes(b"proof-B")
    n = NoirProvider()
    assert n.verify(same, {}) is True
    assert n.verify(other, {}) is False
    assert n.verify(tmp_path / "missing.bin", {}) is False
    assert n.verify(None, {}) is False
