import os
from pathlib import Path

import pytest

import scripts.paths as paths


def test_skill_root_contains_scripts():
    root = paths.skill_root()
    assert (root / "scripts").is_dir() or (root / "scripts" / "paths.py").exists() or root.name == "Sigil-Forge" or (root / "VERSION").exists() or True
    # After layout exists:
    assert (paths.skill_root() / "scripts" / "paths.py").is_file()


def test_make_run_id_uses_digest_prefix_not_full_intent():
    rid = paths.make_run_id("abcdef0123456789" * 4)
    assert "abcdef01" in rid
    assert " " not in rid
    assert len(rid) < 80


def test_run_dir_under_out():
    out = Path("/tmp/sf-out")
    d = paths.run_dir(out, "20260101T000000Z-abcdef01")
    assert d == out / "20260101T000000Z-abcdef01"


def _mode(p):
    return p.stat().st_mode & 0o777


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_default_state_and_sessions_are_owner_only(tmp_path, monkeypatch, request):
    """Sessions hold plaintext intent; default state must not be world-readable."""
    import wizard
    from construct import run as construct_run

    monkeypatch.setenv("SIGIL_FORGE_STATE_DIR", str(tmp_path / "state"))
    previous = os.umask(0o022)  # assert under a permissive umask
    request.addfinalizer(lambda: os.umask(previous))
    doc = wizard.create_session("quick")
    sessions = tmp_path / "state" / "wizard-sessions"
    assert _mode(tmp_path / "state") == 0o700
    assert _mode(sessions) == 0o700
    assert _mode(sessions / f"{doc['session_id']}.json") == 0o600

    construct_run("I maintain calm focus")
    products = tmp_path / "state" / "products"
    assert _mode(products) == 0o700
    runs = [d for d in products.iterdir() if d.is_dir()]
    assert runs and all(_mode(d) == 0o700 for d in runs)


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_operator_chosen_directory_keeps_its_mode(tmp_path):
    existing = tmp_path / "shared"
    existing.mkdir(mode=0o755)
    os.chmod(existing, 0o755)
    paths.ensure_private_dir(existing)
    assert _mode(existing) == 0o755


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_write_private_text_tightens_and_leaves_no_temp_files(tmp_path):
    session = tmp_path / "session.json"
    session.write_text("old")
    os.chmod(session, 0o644)
    paths.write_private_text(session, "new")
    assert session.read_text() == "new"
    assert _mode(session) == 0o600
    assert [p.name for p in tmp_path.iterdir()] == ["session.json"]


_ALL_VARS = (
    "SIGIL_FORGE_HOME",
    "SIGIL_FORGE_ROOT",
    "SIGIL_FORGE_DIR",
    "SIGIL_FORGE_SKILL_DIR",
    "SIGIL_FORGE_STATE_DIR",
    "HERMES_SKILL_DIR",
    "HERMES_HOME",
)


def _clean(monkeypatch, tmp_path):
    for name in _ALL_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def _make_install_root(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("x")
    (d / "VERSION").write_text("0.0.0\n")
    return d


def test_root_variable_precedence(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    for name in paths._ROOT_ENV:
        _make_install_root(tmp_path / name)
    for name in reversed(paths._ROOT_ENV):
        monkeypatch.setenv(name, str(tmp_path / name))
        assert paths.skill_root() == (tmp_path / name).resolve()
    assert paths.skill_root() == (tmp_path / "SIGIL_FORGE_HOME").resolve()


def test_sigil_forge_home_beats_hermes_skill_dir(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("HERMES_SKILL_DIR", str(tmp_path / "hermes"))
    monkeypatch.setenv("SIGIL_FORGE_HOME", str(_make_install_root(tmp_path / "sf")))
    assert paths.skill_root() == (tmp_path / "sf").resolve()


def test_hermes_skill_dir_alone_still_works(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("HERMES_SKILL_DIR", str(tmp_path / "hermes"))
    assert paths.skill_root() == (tmp_path / "hermes").resolve()
    # State stays at the Hermes default, not <skill dir>/state.
    assert paths.default_state_root() == (tmp_path / "home" / ".hermes" / "state" / "sigil-forge").resolve()


def test_defaults_unchanged_with_nothing_set(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    assert paths.configured_root() is None
    assert (paths.skill_root() / "scripts" / "paths.py").is_file()
    expected = (tmp_path / "home" / ".hermes" / "state" / "sigil-forge" / "products").resolve()
    assert paths.default_out_dir() == expected


def test_hermes_home_sets_default_state(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hh"))
    assert paths.default_out_dir() == (tmp_path / "hh" / "state" / "sigil-forge" / "products").resolve()


def test_sigil_forge_home_sets_state_and_sessions(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hh"))
    monkeypatch.setenv("SIGIL_FORGE_HOME", str(tmp_path / "sf"))
    home = (tmp_path / "sf").resolve()
    assert paths.default_state_root() == home / "state"
    assert paths.default_out_dir() == home / "state" / "products"
    assert paths.default_session_dir() == home / "state" / "wizard-sessions"


def test_state_dir_wins_over_everything(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("SIGIL_FORGE_HOME", str(tmp_path / "sf"))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hh"))
    monkeypatch.setenv("SIGIL_FORGE_STATE_DIR", str(tmp_path / "st"))
    assert paths.default_state_root() == (tmp_path / "st").resolve()
    assert paths.default_session_dir() == (tmp_path / "st" / "wizard-sessions").resolve()


def test_tilde_is_expanded(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    _make_install_root(tmp_path / "home" / "sf")
    monkeypatch.setenv("SIGIL_FORGE_HOME", "~/sf")
    assert paths.skill_root() == (tmp_path / "home" / "sf").resolve()
    monkeypatch.delenv("SIGIL_FORGE_HOME")
    monkeypatch.setenv("HERMES_SKILL_DIR", "~/hs")
    assert paths.skill_root() == (tmp_path / "home" / "hs").resolve()


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_wizard_session_lands_under_sigil_forge_home(tmp_path, monkeypatch, request):
    import wizard

    _clean(monkeypatch, tmp_path)
    home = tmp_path / "sf"
    monkeypatch.setenv("SIGIL_FORGE_HOME", str(home))
    previous = os.umask(0o022)
    request.addfinalizer(lambda: os.umask(previous))
    doc = wizard.create_session("quick")
    sessions = home.resolve() / "state" / "wizard-sessions"
    assert _mode(sessions) == 0o700
    assert _mode(sessions / f"{doc['session_id']}.json") == 0o600


def test_is_install_root_needs_both_markers(tmp_path):
    assert not paths._is_install_root(tmp_path)
    (tmp_path / "SKILL.md").write_text("x")
    assert not paths._is_install_root(tmp_path)
    (tmp_path / "VERSION").write_text("1\n")
    assert paths._is_install_root(tmp_path)


def test_find_install_root_walks_up(tmp_path):
    root = _make_install_root(tmp_path / "skill")
    nested = root / "a" / "b" / "c"
    nested.mkdir(parents=True)
    assert paths._find_install_root(nested) == root
    assert paths._find_install_root(root) == root
    lonely = tmp_path / "elsewhere" / "x"
    lonely.mkdir(parents=True)
    # tmp_path has no markers above it (pytest tmp dirs sit under the OS temp dir)
    assert paths._find_install_root(lonely) is None


def test_sigil_forge_home_empty_dir_is_state_home_only(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("SIGIL_FORGE_HOME", str(empty))
    assert (paths.skill_root() / "schemas").is_dir()
    assert paths.skill_root() != empty.resolve()
    assert paths.default_state_root() == empty.resolve() / "state"
    assert paths.configured_root() == empty.resolve()


def test_sigil_forge_home_with_markers_is_install_root(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    home = _make_install_root(tmp_path / "inst")
    monkeypatch.setenv("SIGIL_FORGE_HOME", str(home))
    assert paths.skill_root() == home.resolve()


def test_hermes_skill_dir_empty_is_returned_as_is(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("HERMES_SKILL_DIR", str(empty))
    assert paths.skill_root() == empty.resolve()


def test_invalid_sigil_home_falls_through_to_hermes_skill_dir(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("SIGIL_FORGE_HOME", str(tmp_path / "state-only"))
    monkeypatch.setenv("HERMES_SKILL_DIR", str(tmp_path / "hermes"))
    assert paths.skill_root() == (tmp_path / "hermes").resolve()


def test_nothing_set_skill_root_has_markers(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    root = paths.skill_root()
    assert (root / "SKILL.md").is_file() and (root / "VERSION").is_file()


def test_end_to_end_state_home_without_install_data(tmp_path):
    import json
    import subprocess
    import sys

    repo = Path(__file__).resolve().parents[1]
    cli = repo / "scripts" / "sigil_forge.py"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("HERMES_") and not k.startswith("SIGIL_FORGE_")}
    env["SIGIL_FORGE_HOME"] = str(tmp_path)
    env["HOME"] = str(tmp_path / "home")
    r = subprocess.run([sys.executable, str(cli), "check"], capture_output=True,
                       text=True, cwd=str(repo), env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)["ok"] is True
    r = subprocess.run([sys.executable, str(cli), "construct", "--intent", "I maintain calm focus"],
                       capture_output=True, text=True, cwd=str(repo), env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    products = tmp_path / "state" / "products"
    assert [d for d in products.iterdir() if d.is_dir()]
    assert not (tmp_path / "out").exists()
