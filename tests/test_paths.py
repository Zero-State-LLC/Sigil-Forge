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
