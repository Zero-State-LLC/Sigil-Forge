"""Hermes skill packaging: validate frontmatter, check gates, install-to-temp."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

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
    assert (dest / "src" / "sigil_forge" / "forge_core.py").is_file()
    assert (dest / "src" / "sigil_forge" / "proofs" / "registry.py").is_file()
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


def _frontmatter_raw() -> str:
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    return text.split("---", 2)[1]


def test_validator_passes_without_pyyaml(monkeypatch):
    """README promises a stdlib-only core path; install.sh runs this validator."""
    from sigil_forge import validate_hermes_skill as v

    monkeypatch.setattr(v, "yaml", None)
    report = v.validate()
    assert report["ok"] is True, report["errors"]
    fm, _ = v._parse_frontmatter((ROOT / "SKILL.md").read_text(encoding="utf-8"))
    assert fm["platforms"] == ["linux", "macos", "windows"]
    assert fm["metadata"]["hermes"]["related_skills"] == []
    assert "Sigil" in fm["metadata"]["hermes"]["tags"]


def test_stdlib_frontmatter_parse_matches_pyyaml():
    yaml = pytest.importorskip("yaml")
    from sigil_forge import validate_hermes_skill as v

    assert v._parse_minimal_yaml(_frontmatter_raw()) == yaml.safe_load(
        _frontmatter_raw()
    )


@pytest.mark.parametrize(
    "frontmatter",
    [
        "name: x\nmetadata: {hermes: {}}\n",  # flow mapping
        "name: x\ndescription: >\n  folded\n",  # block scalar
        "name: x\nplatforms: [linux, macos\n",  # unbalanced inline list
        "name: x\n\tversion: 1\n",  # tab indentation
        "name: x\n   stray\n",  # indentation with no parent key
        "name: x # c\n",  # plain value + comment
        'name: "x" # c\n',  # quoted value + comment
        'name: "x" y\n',  # text after closing quote
        'name: "x\n',  # unterminated quote
        "name: 'it''s'\n",  # doubled single quote
        'name: "a\\nb"\n',  # backslash escape
        "name: a: b\n",  # plain scalar with ': '
        "name: a:\n",  # plain scalar ending in ':'
        "enabled: yes\n",  # YAML 1.1 bool
        "enabled: Null\n",
        "version: 1\n",  # int
        "version: 1.0\n",  # float
        "version: -3\n",
        "version: 1e5\n",
        "version: 0x1F\n",
        "tags:\n  - key: value\n",  # list item that is a mapping
        "tags: [a, 'b']\n",  # quote in inline list
        "tags: [a, [b]]\n",  # nested flow list
        "tags: [a, {b}]\n",
        "tags: [a, b # c]\n",
        '"quoted key": x\n',  # quoted key
        "two words: x\n",  # key with a space
    ],
)
def test_stdlib_frontmatter_parse_fails_closed(frontmatter):
    from sigil_forge import validate_hermes_skill as v

    with pytest.raises(ValueError):
        v._parse_minimal_yaml(frontmatter)


@pytest.mark.parametrize(
    "frontmatter",
    [
        "name: sigil-forge\nversion: 0.13.1\n",
        'name: "quoted: value"\ndescription: \'single # quoted\'\n',
        "platforms: [linux, macos, windows]\n",
        "platforms: []\n",
        "tags:\n  - Creative\n  - Sigil\n",
        "metadata:\n  hermes:\n    category: creative\n    related_skills: []\n",
        "author: Daniel Meyer (x), Hermes Agent\nlicense: LicenseRef-Zero-1.0\n",
        "a: 1x\nb: v1.2.3\n",
        "empty:\nother: value\n",
        "outer:\n  inner:\n    - one\n    - two\n  sibling: [a, b]\n",
    ],
)
def test_stdlib_frontmatter_parse_accepted_snippets_match_pyyaml(frontmatter):
    yaml = pytest.importorskip("yaml")
    from sigil_forge import validate_hermes_skill as v

    assert v._parse_minimal_yaml(frontmatter) == yaml.safe_load(frontmatter)


def test_install_source_path_is_not_evaluated_as_code(tmp_path: Path):
    """A checkout path with quotes must not break out of the syntax-check snippet."""
    import shutil

    marker = tmp_path / "injected"
    src = tmp_path / f"sf'''+open({str(marker)!r},'w').close()+r'''"
    shutil.copytree(
        ROOT,
        src,
        ignore=shutil.ignore_patterns(".git", "out", "__pycache__", ".pytest_cache"),
    )
    r = subprocess.run(
        [
            "bash",
            str(src / "install.sh"),
            "--dry-run",
            "--allow-outside-home",
            "--target",
            str(tmp_path / "dest"),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert not marker.exists(), "checkout path was executed as Python"
    assert r.returncode == 0, r.stderr + r.stdout
    assert "Source validation OK" in r.stdout


def _skill_field(key: str) -> str:
    import re

    m = re.search(rf"^{key}:[ \t]*(.*?)[ \t]*$", _frontmatter_raw(), re.MULTILINE)
    assert m, f"SKILL.md frontmatter has no {key}:"
    return m.group(1).strip().strip("\"'")


def _pyproject_text() -> str:
    return (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def _pyproject_value(key: str) -> str:
    """Return the string value of a top-level `key = "..."` line (stdlib only).

    tomllib is 3.11+, and the suite must also pass on Python 3.10.
    """
    import re

    m = re.search(rf'^{key}\s*=\s*"([^"]*)"\s*$', _pyproject_text(), re.MULTILINE)
    assert m, f"pyproject.toml has no string {key} = ..."
    return m.group(1)


def test_skill_version_matches_version_file():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert version
    assert _skill_field("version") == version


def test_pyproject_declares_metadata_policy():
    text = _pyproject_text()
    assert _pyproject_value("license") == "MIT"
    assert _pyproject_value("requires-python") == ">=3.10"
    assert "dependencies = []" in text
    assert 'version = { file = "VERSION" }' in text
    # Version must come from VERSION, never a literal under [project].
    project = text.split("[project]", 1)[1].split("\n[", 1)[0]
    assert "version =" not in project.replace("dynamic", "")
    assert '"version"' in project  # listed in dynamic = ["version"]


def test_pyproject_description_matches_skill():
    assert _pyproject_value("description") == _skill_field("description")
