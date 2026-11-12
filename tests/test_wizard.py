"""Hermes forge wizard: script, next runner, paths, sessions, apply."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sigil_forge.wizard import (
    answers_to_construct_kwargs,
    apply_answers,
    create_session,
    default_answers,
    next_step,
    session_next,
    steps_for_path,
    validate_answers,
    wizard_script,
)

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"


def test_wizard_script_has_steps_and_loop():
    script = wizard_script("quick")
    assert script["wizard_version"] >= "2"
    assert "loop" in script
    assert script["path"] == "quick"
    ids = [s["id"] for s in script["steps"]]
    assert ids[0] == "intent"
    assert "kamea_encoding" not in ids  # quick path
    assert "help" in script["steps"][0]


def test_full_path_includes_craft_steps():
    ids = [s["id"] for s in steps_for_path("full")]
    assert "kamea_encoding" in ids
    assert "planetary_seal" in ids
    assert "planetary_geometry" in ids
    assert "proof" in ids
    assert "kdf" in ids


def test_next_starts_with_intent():
    nxt = next_step({}, path="quick")
    assert nxt["ok"] is True
    assert nxt["done"] is False
    assert nxt["step"]["id"] == "intent"
    assert nxt["step"]["help"]


def test_next_after_intent_mode_quick():
    nxt = next_step({"intent": "I maintain calm focus"}, path="quick")
    assert nxt["done"] is False
    assert nxt["step"]["id"] == "mode"


def test_next_early_safety_refusal():
    nxt = next_step({"intent": "I will murder my neighbor tomorrow"}, path="quick")
    assert nxt["refused"] is True
    assert nxt["done"] is True
    assert "safety" in nxt["error"]


def test_next_skips_planetary_geometry_when_none():
    answers = {
        "intent": "I maintain calm focus",
        "mode": "creative",
        "kamea_encoding": "hebrew_gematria",
        "square": "auto",
        "planetary_seal": "none",
    }
    nxt = next_step(answers, path="full")
    assert nxt["done"] is False
    # should not ask planetary_geometry
    assert nxt["step"]["id"] != "planetary_geometry"
    assert nxt["step"]["id"] == "spare_mode"


def test_next_asks_geometry_when_seal_set():
    answers = {
        "intent": "I maintain calm focus",
        "mode": "creative",
        "kamea_encoding": "hebrew_gematria",
        "square": "auto",
        "planetary_seal": "intelligence_character",
    }
    nxt = next_step(answers, path="full")
    assert nxt["step"]["id"] == "planetary_geometry"


def test_next_done_fills_defaults_quick():
    answers = {
        "intent": "I maintain calm focus",
        "mode": "creative",
        "wallpaper": False,
    }
    nxt = next_step(answers, path="quick")
    assert nxt["done"] is True
    assert nxt["ok"] is True
    assert nxt["answers"]["kamea_encoding"] == "hebrew_gematria"


def test_validate_requires_intent():
    r = validate_answers({})
    assert r["ok"] is False
    assert any("intent" in e for e in r["errors"])


def test_validate_safety_refusal():
    r = validate_answers({"intent": "I will murder my neighbor tomorrow"})
    assert r["ok"] is False
    assert any("safety" in e for e in r["errors"])


def test_validate_happy_path_defaults():
    r = validate_answers({"intent": "I maintain calm focus"}, path="quick")
    assert r["ok"] is True
    assert r["answers"]["mode"] == "creative"
    assert r["answers"]["kamea_encoding"] == "hebrew_gematria"


def test_answers_to_kwargs_planetary():
    mapped = answers_to_construct_kwargs(
        {
            "intent": "I maintain calm focus",
            "mode": "creative",
            "kamea_encoding": "latin_mod9_v1",
            "square": "jupiter",
            "planetary_seal": "intelligence_character",
            "planetary_geometry": "plate",
            "spare_mode": "letter_monogram",
            "phonetic": False,
            "polish": False,
            "wallpaper": True,
            "wp_surface": "desktop",
            "wp_mode": "ambient",
            "wp_theme": "lunar",
            "seal_packet": False,
        }
    )
    assert mapped["construct"]["planetary_seal"] is True
    assert mapped["construct"]["planetary_seal_kind"] == "intelligence_character"
    assert mapped["construct"]["planetary_geometry"] == "plate"
    assert mapped["construct"]["square"] == "jupiter"
    assert mapped["wallpaper"]["enabled"] is True


def test_apply_answers_constructs(tmp_path: Path):
    result = apply_answers(
        {
            "intent": "I maintain calm focus",
            "mode": "creative",
            "kamea_encoding": "latin_mod9_v1",
            "square": "auto",
            "planetary_seal": "none",
            "wallpaper": False,
        },
        out_root=tmp_path,
        path="quick",
    )
    assert result["ok"] is True, result
    assert result["svg"]
    assert Path(result["svg"]).is_file()


def test_apply_with_wallpaper(tmp_path: Path):
    result = apply_answers(
        {
            "intent": "I maintain calm focus",
            "kamea_encoding": "latin_mod9_v1",
            "wallpaper": True,
            "wp_surface": "phone_lock",
            "wp_mode": "focus",
            "wp_theme": "mercurial",
        },
        out_root=tmp_path,
        path="quick",
    )
    assert result["ok"] is True, result
    assert result.get("wallpaper", {}).get("ok") is True


def test_session_next_loop(tmp_path: Path, monkeypatch):
    # sessions write under default_out_dir parent — fine for real skill root
    doc = create_session(path="quick")
    sid = doc["session_id"]
    n1 = session_next(sid)
    assert n1["step"]["id"] == "intent"
    n2 = session_next(sid, merge_answers={"intent": "I maintain calm focus"})
    assert n2["step"]["id"] == "mode"
    n3 = session_next(
        sid,
        merge_answers={"mode": "creative", "wallpaper": False},
    )
    assert n3["done"] is True
    assert n3["ok"] is True


def test_wizard_cli_script():
    r = subprocess.run(
        [sys.executable, str(CLI), "wizard", "--script", "--path", "quick"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["steps"]
    assert data["loop"]


def test_wizard_cli_next():
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "wizard",
            "--next",
            "--path",
            "quick",
            "--answers-json",
            json.dumps({"intent": "I maintain calm focus"}),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    out = json.loads(r.stdout)
    assert out["step"]["id"] == "mode"


def test_wizard_cli_apply(tmp_path: Path):
    ans = tmp_path / "answers.json"
    ans.write_text(
        json.dumps(
            {
                "intent": "I maintain calm focus",
                "kamea_encoding": "latin_mod9_v1",
                "planetary_seal": "intelligence_character",
                "square": "jupiter",
                "planetary_geometry": "plate",
            }
        ),
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "wizard",
            "--apply",
            str(ans),
            "--path",
            "full",
            "--out",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert Path(out["svg"]).is_file()


def test_wizard_cli_session_new():
    r = subprocess.run(
        [sys.executable, str(CLI), "wizard", "--session-new", "--path", "quick"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["session"]["session_id"]
    assert out["next"]["step"]["id"] == "intent"


def test_default_answers_template():
    d = default_answers()
    assert d["mode"] == "creative"
    assert d["planetary_seal"] == "none"
    assert d["proof"] == "none"
    assert d["kdf"] == "auto"


def test_next_asks_proof_on_full_path():
    answers = {
        "intent": "I maintain calm focus",
        "mode": "creative",
        "kamea_encoding": "latin_mod9_v1",
        "square": "auto",
        "planetary_seal": "none",
        "spare_mode": "letter_monogram",
        "phonetic": False,
        "polish": False,
        "wallpaper": False,
        "seal_packet": False,
    }
    nxt = next_step(answers, path="full")
    assert nxt["done"] is False
    assert nxt["step"]["id"] == "proof"


def test_next_asks_kdf_when_proof_commitment():
    answers = {
        "intent": "I maintain calm focus",
        "mode": "creative",
        "kamea_encoding": "latin_mod9_v1",
        "square": "auto",
        "planetary_seal": "none",
        "spare_mode": "letter_monogram",
        "phonetic": False,
        "polish": False,
        "wallpaper": False,
        "seal_packet": False,
        "proof": "commitment",
    }
    nxt = next_step(answers, path="full")
    assert nxt["done"] is False
    assert nxt["step"]["id"] == "kdf"


def test_next_skips_kdf_when_proof_none():
    answers = {
        "intent": "I maintain calm focus",
        "mode": "creative",
        "kamea_encoding": "latin_mod9_v1",
        "square": "auto",
        "planetary_seal": "none",
        "spare_mode": "letter_monogram",
        "phonetic": False,
        "polish": False,
        "wallpaper": False,
        "seal_packet": False,
        "proof": "none",
    }
    nxt = next_step(answers, path="full")
    assert nxt["done"] is True
    assert nxt["ok"] is True


def test_answers_to_kwargs_proof():
    mapped = answers_to_construct_kwargs(
        {
            "intent": "I maintain calm focus",
            "mode": "creative",
            "kamea_encoding": "latin_mod9_v1",
            "square": "auto",
            "planetary_seal": "none",
            "spare_mode": "letter_monogram",
            "phonetic": False,
            "polish": False,
            "wallpaper": False,
            "seal_packet": False,
            "proof": "commitment",
            "kdf": "pbkdf2-sha256",
        }
    )
    assert mapped["construct"]["proof"] == "commitment"
    assert mapped["construct"]["kdf"] == "pbkdf2-sha256"


def test_apply_proof_commitment_requires_passphrase(tmp_path: Path):
    result = apply_answers(
        {
            "intent": "I maintain calm focus",
            "kamea_encoding": "latin_mod9_v1",
            "proof": "commitment",
            "wallpaper": False,
        },
        out_root=tmp_path,
        path="full",
    )
    assert result["ok"] is False
    assert any("passphrase" in e for e in (result.get("errors") or []))


def test_apply_proof_commitment_with_passphrase(tmp_path: Path):
    result = apply_answers(
        {
            "intent": "I maintain calm focus",
            "kamea_encoding": "latin_mod9_v1",
            "proof": "commitment",
            "kdf": "pbkdf2-sha256",
            "wallpaper": False,
        },
        out_root=tmp_path,
        path="full",
        passphrase="wizard-poi-pass",
    )
    assert result["ok"] is True, result
    assert result.get("intent_commitment")
    assert result.get("sigil_root")
    assert result.get("intent_capsule")
    assert Path(result["intent_capsule"]).is_file()
    assert any("open --capsule" in n for n in result.get("next") or [])
