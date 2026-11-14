"""Regressions for the low-priority findings of the November 2026 audit of v0.18.0."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sigil_forge import aes_gcm, construct, receipt
from sigil_forge.construct import run as construct_run
from sigil_forge.proofs.verify_run import verify_proof_run

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / "scripts" / "sigil_forge.py")]
INTENT = "I maintain calm focus"
PW = "pw-test"


def cli(*args: str, passphrase: str | None = None):
    env = dict(os.environ)
    if passphrase:
        env["SIGIL_FORGE_PASSPHRASE"] = passphrase
    return subprocess.run([*CLI, *args], capture_output=True, text=True, env=env)


@pytest.fixture()
def proof_run(tmp_path):
    packet = construct_run(INTENT, out_root=tmp_path / "out", passphrase=PW, proof="commitment")
    return packet, Path(packet["artifacts"]["run_dir"])


def test_proof_paths_name_the_finished_run_not_the_staging_folder(proof_run):
    packet, run = proof_run
    manifest = json.loads((run / "proofs" / "proof-manifest.json").read_text(encoding="utf-8"))
    assert manifest["proof_file"] == "knowledge-attestation.json"  # a name, not a path
    recorded = Path(packet["proof"]["proof_path"])
    assert recorded == run / "proofs" / "knowledge-attestation.json" and recorded.is_file()
    everything = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in run.rglob("*.json"))
    assert ".sf-staging-" not in everything


def test_a_run_still_verifies_after_it_is_moved(proof_run, tmp_path):
    _packet, run = proof_run
    moved = tmp_path / "elsewhere" / "renamed-run"
    moved.parent.mkdir()
    run.rename(moved)
    got = verify_proof_run(moved, passphrase=PW)
    assert got["verified"] is True, got["detail"]


def test_a_manifest_cannot_point_the_verifier_outside_the_run(proof_run, tmp_path, monkeypatch):
    """Whatever proof_file says, a provider is only ever handed a path inside the run."""
    from sigil_forge.proofs import verify_run as vr

    _packet, run = proof_run
    path = run / "proofs" / "proof-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    handed: list[Path] = []
    real = vr.get_provider

    def spy(name):
        provider = real(name)
        inner = provider.verify

        def verify(proof_path, public_inputs, **kw):
            handed.append(Path(proof_path))
            return inner(proof_path, public_inputs, **kw)

        provider.verify = verify
        return provider

    monkeypatch.setattr(vr, "get_provider", spy)
    for claimed in (str(tmp_path / "outside.json"), "../../../etc/passwd", "/etc/passwd", "sub/dir/x.json"):
        manifest["proof_file"] = claimed
        path.write_text(json.dumps(manifest), encoding="utf-8")
        verify_proof_run(run, passphrase=PW)
    assert handed
    for given in handed:
        assert given.parent == run / "proofs", given


@pytest.mark.parametrize("mode", ["commitment", "zk-knowledge"])
def test_proof_modes_that_seal_a_capsule_need_a_passphrase(tmp_path, mode):
    with pytest.raises(ValueError, match="requires passphrase"):
        construct_run(INTENT, out_root=tmp_path, proof=mode)
    assert list(tmp_path.iterdir()) == []
    r = cli("construct", "--intent", INTENT, "--proof", mode, "--out", str(tmp_path / "cli"))
    assert r.returncode == 1 and "requires passphrase" in r.stderr
    assert not (tmp_path / "cli").exists() or not any((tmp_path / "cli").iterdir())


def test_check_reports_poi_ok_only_when_the_root_recomputes(monkeypatch, capsys):
    from sigil_forge import cli as cli_mod
    from sigil_forge import forge_manifest

    good = cli("check")
    assert json.loads(good.stdout)["poi_ok"] is True

    monkeypatch.setattr(
        forge_manifest, "check_run_root", lambda path: {"ok": False, "detail": "simulated"}
    )
    rc = cli_mod.main(["check"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["poi_ok"] is False and payload["ok"] is False and rc != 0


def test_a_failed_forge_leaves_no_line_in_the_receipt_log(tmp_path, monkeypatch):
    log = tmp_path / "receipts.jsonl"
    monkeypatch.setenv("SIGIL_FORGE_RECEIPTS", str(log))
    real_rename = os.rename

    def fail_promote(src, dst):
        # Both the rename and the Windows fallback move things out of staging.
        if ".sf-staging-" in str(src):
            raise PermissionError("simulated failure at promotion")
        return real_rename(src, dst)

    monkeypatch.setattr(construct.os, "rename", fail_promote)
    with pytest.raises(OSError):
        construct_run(INTENT, out_root=tmp_path / "out")
    monkeypatch.setattr(construct.os, "rename", real_rename)
    assert not log.exists() or log.read_text(encoding="utf-8") == ""
    assert list((tmp_path / "out").iterdir()) == []  # and no run folder either

    packet = construct_run(INTENT, out_root=tmp_path / "out2")
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["run_id"] == packet["artifacts"]["run_id"]


@pytest.mark.parametrize("bad", ["xyz", "abc123", "g" * 64, "a" * 63, "a" * 65, ""])
def test_learn_rejects_a_digest_that_is_not_one(tmp_path, bad):
    ledger = tmp_path / "ledger.jsonl"
    r = cli("learn", "--class", "channel_preference", "--summary", "note", "--digest", bad,
            "--ledger", str(ledger))
    assert r.returncode == 2 and "64 hex" in r.stderr
    assert not ledger.exists()


def test_learn_accepts_a_real_digest_in_any_case(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    r = cli("learn", "--class", "channel_preference", "--summary", "note", "--digest", "AB" * 32,
            "--ledger", str(ledger))
    assert r.returncode == 0, r.stderr
    assert json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])["intent_digest"] == "ab" * 32


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_every_log_and_packet_file_is_created_owner_only(tmp_path, monkeypatch, request):
    previous = os.umask(0o022)
    request.addfinalizer(lambda: os.umask(previous))
    ledger, proposals, receipts = (tmp_path / n for n in ("ledger.jsonl", "canon.jsonl", "r.jsonl"))
    entry = receipt.build_ledger_entry(class_name="channel_preference", summary="note")
    receipt.append_ledger(entry, ledger)
    receipt.promote_entry(0, confirm=receipt.PROMOTE_CONFIRM, ledger_path=ledger, out_path=proposals)
    receipt.append_receipt_log({"a": 1}, receipts)
    for path in (ledger, proposals, receipts):
        assert path.stat().st_mode & 0o777 == 0o600, path.name
    # An existing file keeps the mode its owner gave it.
    os.chmod(ledger, 0o644)
    receipt.append_ledger(entry, ledger)
    assert ledger.stat().st_mode & 0o777 == 0o644

    packet = construct_run(INTENT, out_root=tmp_path / "out")
    run = Path(packet["artifacts"]["run_dir"])
    for name in ("forge-packet.json", "forge-packet.md", "method-manifest.json", "run-receipt.json"):
        assert (run / name).stat().st_mode & 0o777 == 0o600, name


def test_doctor_says_why_the_built_in_aes_is_in_use(monkeypatch):
    payload = json.loads(cli("doctor").stdout)
    assert "aes_backend_note" in payload
    assert (payload["aes_backend"] == "cryptography") == (payload["aes_backend_note"] == "")

    monkeypatch.setattr(aes_gcm, "_AESGCM", None)
    monkeypatch.setattr(aes_gcm, "_LOAD_PROBLEM", None)
    assert "not constant-time" in aes_gcm.backend_note() and "crypto" in aes_gcm.backend_note()
    monkeypatch.setattr(aes_gcm, "_LOAD_PROBLEM", "OSError")
    note = aes_gcm.backend_note()
    assert "failed to load (OSError)" in note and aes_gcm.backend() == "pure-python"


def test_the_spare_label_is_the_same_for_every_intent():
    """It is public. Varying it for vowel-only intents would reveal that about the intent."""
    from sigil_forge.spare import run_spare

    labels = {
        run_spare(text, mode="letter_monogram").semantic_verification
        for text in ("i maintain calm focus", "aeiou aeiou", "a", "zzz")
    }
    assert labels == {"VERIFIED_geometry_from_letters"}
