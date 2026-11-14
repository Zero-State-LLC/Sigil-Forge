"""Regressions for three defects found by the November 2026 audit of v0.18.0."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sigil_forge import wizard
from sigil_forge.construct import run as construct_run
from sigil_forge.inspect_artifact import inspect_path
from sigil_forge.proofs.verify_run import verify_proof_run
from sigil_forge.verify import run as verify_run
from sigil_forge.wallpaper.pipeline import build_wallpaper
from sigil_forge.wallpaper.vault import probe_png_public

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / "scripts" / "sigil_forge.py")]
# A made-up marker standing in for a passphrase. It is not a credential; the
# tests only check that this exact string never reaches disk or stdout.
MARKER = "hunter2-do-not-store"
INTENT = "I maintain calm focus"


# ---------------------------------------------------- 1. wizard and secrets


def _session_text(session_id: str) -> str:
    return wizard.session_path(session_id).read_text(encoding="utf-8")


@pytest.mark.parametrize("key", ["passphrase", "password", "secret", "token", "nonce"])
def test_wizard_never_stores_or_echoes_a_secret_answer(key):
    sid = wizard.create_session("full")["session_id"]
    out = wizard.session_next(sid, merge_answers={"intent": INTENT, key: MARKER})
    assert MARKER not in json.dumps(out)
    assert MARKER not in _session_text(sid)
    assert out["ignored_answers"] == [key]
    assert "SIGIL_FORGE_PASSPHRASE" in out["warning"]
    # The real answer is kept and the interview moves on.
    assert out["answers_so_far"]["intent"] == INTENT
    assert json.loads(_session_text(sid))["answers"] == {"intent": INTENT}


def test_wizard_drops_unknown_answers_without_a_secret_warning():
    sid = wizard.create_session("quick")["session_id"]
    out = wizard.session_next(sid, merge_answers={"intent": INTENT, "favourite_colour": "green"})
    assert out["ignored_answers"] == ["favourite_colour"]
    assert "warning" not in out
    assert "green" not in _session_text(sid)


def test_wizard_scrubs_a_secret_left_in_an_older_session_file():
    sid = wizard.create_session("quick")["session_id"]
    path = wizard.session_path(sid)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["answers"] = {"intent": INTENT, "passphrase": MARKER}
    path.write_text(json.dumps(doc), encoding="utf-8")
    out = wizard.session_next(sid)
    assert MARKER not in json.dumps(out)
    assert MARKER not in path.read_text(encoding="utf-8")


def test_wizard_cli_does_not_print_or_save_a_passphrase():
    new = subprocess.run([*CLI, "wizard", "--session-new", "--path", "quick"], capture_output=True, text=True)
    sid = json.loads(new.stdout)["session"]["session_id"]
    r = subprocess.run(
        [*CLI, "wizard", "--session", sid, "--next", "--answers-json",
         json.dumps({"intent": INTENT, "passphrase": MARKER})],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert MARKER not in r.stdout and MARKER not in r.stderr
    state = Path(os.environ["SIGIL_FORGE_STATE_DIR"])
    for f in (state / "wizard-sessions").glob("*.json"):
        assert MARKER not in f.read_text(encoding="utf-8")


def test_clean_answers_keeps_every_real_step():
    everything = {step["id"]: "x" for step in wizard.STEPS}
    clean, ignored = wizard.clean_answers({**everything, "path": "full", "session_id": "s"})
    assert clean == everything and ignored == []


# ------------------------------------------- 2. verify-proof and other runs


@pytest.fixture()
def two_runs(tmp_path):
    runs = []
    for name, intent in (("a", INTENT), ("b", "I finish what I start")):
        packet = construct_run(intent, out_root=tmp_path / name, passphrase="same-pass", proof="commitment")
        runs.append(Path(packet["artifacts"]["run_dir"]))
    return runs


def test_verify_proof_accepts_a_runs_own_proof(two_runs):
    got = verify_proof_run(two_runs[0], passphrase="same-pass")
    assert got["verified"] is True and got["provider"] == "local_capsule"


def test_verify_proof_refuses_a_capsule_and_proofs_from_another_run(two_runs):
    """Same passphrase on both runs, so only the binding can catch the swap."""
    mine, other = two_runs
    shutil.copy(other / "intent-capsule.json", mine / "intent-capsule.json")
    shutil.rmtree(mine / "proofs")
    shutil.copytree(other / "proofs", mine / "proofs")
    got = verify_proof_run(mine, passphrase="same-pass")
    assert got["verified"] is False
    assert "different commitment" in got["detail"]
    # It reports this run's commitment, not the one in the foreign proof files.
    packet = json.loads((mine / "forge-packet.json").read_text(encoding="utf-8"))
    assert got["intent_commitment"] == packet["intent_commitment"]["value"]


def test_verify_proof_refuses_proofs_naming_another_root(two_runs):
    mine, _ = two_runs
    path = mine / "proofs" / "proof-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["public_inputs"]["sigil_root"] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    got = verify_proof_run(mine, passphrase="same-pass")
    assert got["verified"] is False and "sigil_root" in got["detail"]


def test_verify_proof_needs_the_runs_packet_to_bind_against(two_runs):
    mine, _ = two_runs
    (mine / "forge-packet.json").unlink()
    got = verify_proof_run(mine, passphrase="same-pass")
    assert got["verified"] is False and "forge-packet.json" in got["detail"]


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("forge-packet.json", "{not json"),
        ("forge-packet.json", "[]"),
        ("forge-packet.json", b"\xff\xfe"),
        ("proofs/proof-manifest.json", "{not json"),
        ("proofs/proof-manifest.json", b"\xff\xfe"),
        ("proofs/proof-manifest.json", json.dumps({"public_inputs": 5, "status": "generated"})),
    ],
)
def test_verify_proof_reports_broken_files_instead_of_raising(two_runs, name, content):
    mine, _ = two_runs
    target = mine / name
    target.write_bytes(content if isinstance(content, bytes) else content.encode())
    got = verify_proof_run(mine, passphrase="same-pass")
    assert got["verified"] is False and got["detail"]


# ------------------------------- 3. verify and inspect on the vault wallpaper


@pytest.fixture(scope="module")
def wallpapers(tmp_path_factory):
    """One run with a sealed (SF12) wallpaper and one with a public (SF11) one."""
    out = {}
    for name, passphrase in (("vault", "wall-pass"), ("public", None)):
        root = tmp_path_factory.mktemp(name)
        packet = construct_run(INTENT, out_root=root, passphrase=passphrase)
        run = Path(packet["artifacts"]["run_dir"])
        result = build_wallpaper(run, surface="phone_lock", passphrase=passphrase)
        out[name] = (packet, Path(result["wallpaper"]), result)
    return out


def test_verify_reads_the_products_own_vault_wallpaper(wallpapers):
    packet, png, result = wallpapers["vault"]
    assert result["vault_status"] == "embedded"
    got = verify_run(png)
    assert got["ok"] is True, got.get("detail")
    assert got["stego_format"] == "SF12" and got["has_vault"] is True
    assert got["intent_digest"] == packet["intent_digest"]
    assert got["sigil_root"] == packet["sigil_root"]
    assert "sf12_vault" in got["channels_checked"]
    assert verify_run(png, expected_digest="0" * 64)["ok"] is False


def test_inspect_reads_the_vault_wallpaper_without_a_passphrase(wallpapers):
    packet, png, _ = wallpapers["vault"]
    got = inspect_path(png)
    assert got["ok"] is True and got["format_version"] == "SF12" and got["has_vault"] is True
    assert got["intent_digest"] == packet["intent_digest"]
    assert INTENT.lower() not in json.dumps(got).lower()


def test_verify_and_inspect_still_read_the_older_formats(wallpapers):
    packet, png, _ = wallpapers["public"]
    for got in (verify_run(png), inspect_path(png)):
        assert got["ok"] is True
        assert got["intent_digest"] == packet["intent_digest"]
    assert verify_run(png)["stego_format"] == "SF11"
    glyph = Path(packet["artifacts"]["run_dir"]) / "glyph.png"
    assert verify_run(glyph)["ok"] is True and inspect_path(glyph)["ok"] is True


def test_verify_inspect_and_the_probe_agree_on_every_format(wallpapers):
    """One probe, so the commands cannot drift apart again."""
    for _packet, png, _ in wallpapers.values():
        probe = probe_png_public(png.read_bytes())
        assert verify_run(png)["stego_format"] == probe["format"] == inspect_path(png)["format_version"]


def test_a_damaged_vault_is_reported_not_half_read(wallpapers, tmp_path):
    from sigil_forge.stego_png import embed_lsb, extract_lsb

    _packet, png, _ = wallpapers["vault"]
    data = png.read_bytes()
    payload = bytearray(extract_lsb(data, 200))
    payload[100] ^= 0xFF  # inside the sealed part, covered by the CRC
    broken = tmp_path / "broken.png"
    broken.write_bytes(embed_lsb(data, bytes(payload)))
    assert verify_run(broken)["ok"] is False
    assert inspect_path(broken)["ok"] is False


def test_a_png_with_no_payload_gives_the_plain_message(tmp_path):
    from sigil_forge.stego_png import write_rgb_png

    plain = tmp_path / "plain.png"
    plain.write_bytes(write_rgb_png(64, 64, bytes(64 * 64 * 3)))
    got = verify_run(plain)
    assert got["ok"] is False and got["detail"] == "bad PNG LSB magic"


def test_inspect_accepts_a_run_folder(wallpapers):
    """This branch was unreachable: a folder was reported as file not found."""
    packet, _png, _ = wallpapers["vault"]
    got = inspect_path(packet["artifacts"]["run_dir"])
    assert got["ok"] is True and got["carrier"] == "run"
    assert got["sigil_root"] == packet["sigil_root"]
    assert inspect_path("/nonexistent/path")["detail"] == "file not found"


def test_suite_is_not_affected_by_a_passphrase_in_the_shell():
    """conftest clears it; an ambient passphrase used to fail four unrelated tests."""
    assert "SIGIL_FORGE_PASSPHRASE" not in os.environ
