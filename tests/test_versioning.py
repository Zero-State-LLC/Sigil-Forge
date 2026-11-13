"""One version, written the same everywhere, with release notes to match."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "set_version.py"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _module():
    spec = importlib.util.spec_from_file_location("set_version", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION)


def test_every_place_agrees_with_version_file():
    r = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_no_other_doc_states_a_current_version():
    """A current-version claim outside the script's list would drift unnoticed."""
    listed = {rel for rel, _p, _c in _module().PLACES}
    pattern = re.compile(r"(?i)(current (version|release)|this distribution is)[^\n]{0,60}\d+\.\d+\.\d+")
    offenders = []
    for path in [*ROOT.glob("*.md"), *ROOT.glob("references/*.md"), *ROOT.glob("integrations/**/*.md")]:
        rel = path.relative_to(ROOT).as_posix()
        if rel in listed or rel == "CHANGELOG.md":
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert offenders == []


def test_changelog_has_a_dated_section_for_this_version_first():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"(?m)^## (.+)$", text)
    assert headings[0] == "Unreleased"
    assert re.fullmatch(rf"{re.escape(VERSION)} - \d{{4}}-\d{{2}}-\d{{2}}", headings[1]), headings[1]
    # Unreleased may collect notes between releases; the newest released
    # section must still be the current version.


def test_roadmap_has_a_row_for_this_version():
    spine = (ROOT / "references" / "expansion-spine.md").read_text(encoding="utf-8")
    assert re.search(rf"(?m)^\| v{re.escape(VERSION)} \|", spine)


def test_set_version_writes_every_place_and_check_catches_drift(tmp_path, monkeypatch):
    mod = _module()
    for rel in ["VERSION", *{rel for rel, _p, _c in mod.PLACES}]:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / rel).read_bytes())
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    mod.write("9.8.7")
    assert mod.current() == "9.8.7" and mod.check() == []
    for _rel, _pattern, versions in mod.found():
        assert versions and set(versions) == {"9.8.7"}
    # Only the version changed: putting it back restores every file exactly.
    mod.write(VERSION)
    for rel in ["VERSION", *{rel for rel, _p, _c in mod.PLACES}]:
        assert (tmp_path / rel).read_bytes() == (ROOT / rel).read_bytes(), rel

    (tmp_path / "VERSION").write_text("9.9.9\n")
    assert len(mod.check()) == len(mod.PLACES)
    with pytest.raises(SystemExit):
        mod.write("not-a-version")


def test_grok_bot_skill_installs_this_release_tag():
    skill = (ROOT / "integrations" / "grok-bot" / "SKILL.md").read_text(encoding="utf-8")
    assert f"--branch v{VERSION} https://github.com/Zero-State-LLC/Sigil-Forge" in skill


def test_wizard_offers_only_spare_modes_the_engine_accepts():
    """The wizard once offered two names construct rejects; keep the lists in step."""
    sys.path.insert(0, str(ROOT / "src"))
    from sigil_forge import ontology, wizard

    steps = [s for s in wizard.STEPS if s.get("id") == "spare_mode"]
    assert len(steps) == 1
    assert set(steps[0]["choices"]) <= set(ontology.SPARE_MODES)
    assert steps[0]["default"] in steps[0]["choices"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    line = next(ln for ln in readme.splitlines() if ln.startswith("--spare-mode "))
    assert set(line.split()[1].split("|")) == set(ontology.SPARE_MODES)
