"""Hermes skill packaging: validate frontmatter, check gates, install-to-temp."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"
INSTALL = ROOT / "install.sh"


def test_validate_hermes_skill_ok():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_hermes_skill.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert payload.get("errors") == []
    assert payload.get("name") == "sigil-forge"
    assert payload.get("description_chars", 99) <= 60
    desc = payload.get("description") or ""
    assert desc.endswith(".")
    assert "powerful" not in desc.lower()


def test_check_reports_hermes_and_poi_ok():
    r = subprocess.run(
        [sys.executable, str(CLI), "check"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert payload.get("hermes_ok") is True
    assert payload.get("poi_ok") is True
    assert payload.get("modules_ok") is True
    assert payload.get("missing") == []
    assert payload.get("description_ok") is True
    assert payload.get("description_chars", 99) <= 60
    assert "forge_core" not in str(payload.get("module_errors") or [])


def test_doctor_packaging_and_providers():
    r = subprocess.run(
        [sys.executable, str(CLI), "doctor"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert payload.get("packaging") == "hermes-skill"
    assert payload.get("hermes_ok") is True
    assert payload.get("description_ok") is True
    assert payload.get("description_chars", 99) <= 60
    names = {p["name"] for p in payload.get("proof_providers") or []}
    assert "none" in names
    assert "risc0" in names
    assert payload.get("version")


def test_proof_of_intent_ref_present():
    assert (ROOT / "references" / "proof-of-intent.md").is_file()
    assert (ROOT / "references" / "hermes-runtime-contract.md").is_file()
    text = (ROOT / "references" / "hermes-runtime-contract.md").read_text(
        encoding="utf-8"
    )
    assert "not a Hermes plugin" in text or "not a plugin" in text.lower()
    assert "verify-proof" in text
    assert "open" in text and "capsule" in text


def test_install_to_temp_and_check(tmp_path: Path):
    """Full skill install path outside source tree must pass check under HERMES_SKILL_DIR."""
    dest = tmp_path / "hermes-skills" / "sigil-forge"
    r = subprocess.run(
        [
            "bash",
            str(INSTALL),
            "--target",
            str(dest),
            "--allow-outside-home",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env={**os.environ, "HOME": str(tmp_path / "home")},
    )
    # HOME is tmp so default path is under tmp; we use explicit --target
    assert r.returncode == 0, r.stderr + r.stdout
    assert (dest / "SKILL.md").is_file()
    assert (dest / "scripts" / "forge_core.py").is_file()
    assert (dest / "scripts" / "proofs" / "registry.py").is_file()
    assert (dest / "references" / "proof-of-intent.md").is_file()
    # Lean install: implementation plans not required at runtime
    assert not (dest / "docs" / "superpowers").exists()
    # No .git in install tree
    assert not (dest / ".git").exists()

    check = subprocess.run(
        [sys.executable, str(dest / "scripts" / "sigil_forge.py"), "check"],
        capture_output=True,
        text=True,
        cwd=str(dest),
        env={**os.environ, "HERMES_SKILL_DIR": str(dest)},
    )
    assert check.returncode == 0, check.stderr + check.stdout
    payload = json.loads(check.stdout)
    assert payload["ok"] is True
    assert payload["poi_ok"] is True
    assert payload["hermes_ok"] is True
    assert Path(payload["root"]).resolve() == dest.resolve()


def test_install_dry_run():
    r = subprocess.run(
        [
            "bash",
            str(INSTALL),
            "--dry-run",
            "--allow-outside-home",
            "--target",
            "/tmp/sf-never-written",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "dry-run" in (r.stdout + r.stderr).lower() or "DRY RUN" in r.stdout


def test_install_leaves_no_out_dir(tmp_path: Path):
    """Post-install check must not leave skill-root out/ pollution."""
    dest = tmp_path / "hermes-skills" / "sigil-forge-clean"
    r = subprocess.run(
        [
            "bash",
            str(INSTALL),
            "--target",
            str(dest),
            "--allow-outside-home",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env={**os.environ, "HOME": str(tmp_path / "home2")},
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert not (dest / "out").exists()


def test_eval_includes_poi_and_hermes():
    r = subprocess.run(
        [sys.executable, str(CLI), "eval"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    by = {c["name"]: c for c in payload["cases"]}
    for name in (
        "poi_intent_commitment",
        "poi_sigil_root",
        "poi_capsule_with_passphrase",
        "hermes_frontmatter",
        "forge_core_digest",
        "refuse_enochian_request",
    ):
        assert by[name]["ok"] is True, by[name]


def test_help_points_to_installed_docs():
    r = subprocess.run(
        [sys.executable, str(CLI), "help"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0
    out = r.stdout
    assert "SKILL.md" in out
    assert "hermes-runtime-contract" in out
    assert "proof-of-intent" in out
    assert "docs/superpowers" not in out
