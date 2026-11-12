"""install.sh --standalone / --hermes targets and the agent_contract_ok alias."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"


def _env(home: Path, **extra: str) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SIGIL_FORGE_", "HERMES_"))
    }
    env["HOME"] = str(home)
    env.update(extra)
    return env


def _run(args: list[str], home: Path, **extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(INSTALL), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=_env(home, **extra),
    )


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home.resolve()  # macOS /var -> /private/var: compare like for like


def test_standalone_dry_run_names_default_and_writes_nothing(tmp_path: Path):
    home = _home(tmp_path)
    r = _run(["--standalone", "--dry-run"], home)
    assert r.returncode == 0, r.stderr + r.stdout
    assert f"{home}/.sigil-forge" in r.stdout
    assert "SIGIL_FORGE_HOME=" in r.stdout
    assert "HERMES_SKILL_DIR=" not in r.stdout
    assert list(home.iterdir()) == []


def test_standalone_honours_sigil_forge_home(tmp_path: Path):
    home = _home(tmp_path)
    target = home / "custom-sf"
    r = _run(["--standalone", "--dry-run"], home, SIGIL_FORGE_HOME=str(target))
    assert r.returncode == 0, r.stderr + r.stdout
    assert f"{target}" in r.stdout
    assert ".sigil-forge" not in r.stdout
    assert list(home.iterdir()) == []


def test_standalone_target_flag_wins(tmp_path: Path):
    home = _home(tmp_path)
    target = home / "explicit"
    r = _run(
        ["--standalone", "--dry-run", "--target", str(target)],
        home,
        SIGIL_FORGE_HOME=str(home / "ignored"),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert str(target) in r.stdout
    assert "ignored" not in r.stdout


def test_standalone_install_and_check(tmp_path: Path):
    home = _home(tmp_path)
    target = home / ".sigil-forge"
    r = _run(["--standalone"], home)
    assert r.returncode == 0, r.stderr + r.stdout
    assert (target / "SKILL.md").is_file()
    assert f'export SIGIL_FORGE_HOME="{target}"' in r.stdout
    assert "HERMES_SKILL_DIR" not in r.stdout
    assert not (home / ".hermes").exists()

    check = subprocess.run(
        [sys.executable, str(target / "scripts" / "sigil_forge.py"), "check"],
        capture_output=True,
        text=True,
        cwd=str(target),
        env=_env(home, SIGIL_FORGE_HOME=str(target)),
    )
    assert check.returncode == 0, check.stderr + check.stdout
    payload = json.loads(check.stdout)
    assert payload["ok"] is True
    assert payload["agent_contract_ok"] is True
    assert payload["hermes_ok"] is True
    assert Path(payload["root"]).resolve() == target.resolve()

    state = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from sigil_forge.paths import default_state_root; "
            "print(default_state_root())",
            str(target / "src"),
        ],
        capture_output=True,
        text=True,
        env=_env(home, SIGIL_FORGE_HOME=str(target)),
    )
    assert state.returncode == 0, state.stderr
    assert Path(state.stdout.strip()) == target.resolve() / "state"
    assert not (home / ".hermes").exists()


def test_standalone_reinstall_keeps_backups_out_of_hermes_home(tmp_path: Path):
    home = _home(tmp_path)
    assert _run(["--standalone"], home).returncode == 0
    r = _run(["--standalone"], home)
    assert r.returncode == 0, r.stderr + r.stdout
    assert "Backup:" in r.stdout
    assert (home / ".sigil-forge-backups" / "backups" / "sigil-forge").is_dir()
    assert not (home / ".hermes").exists()


def test_hermes_flag_equals_default_target(tmp_path: Path):
    home = _home(tmp_path)
    default = _run(["--dry-run"], home)
    explicit = _run(["--hermes", "--dry-run"], home)
    assert default.returncode == 0 and explicit.returncode == 0
    expected = f"{home}/.hermes/skills/sigil-forge"
    assert expected in default.stdout
    assert default.stdout == explicit.stdout
    assert "HERMES_SKILL_DIR=" in default.stdout
    assert list(home.iterdir()) == []


def test_hermes_home_still_moves_default_target(tmp_path: Path):
    home = _home(tmp_path)
    hh = home / "hh"
    r = _run(["--dry-run"], home, HERMES_HOME=str(hh))
    assert r.returncode == 0, r.stderr + r.stdout
    assert f"{hh}/skills/sigil-forge" in r.stdout


def test_standalone_and_hermes_conflict(tmp_path: Path):
    home = _home(tmp_path)
    for args in (["--standalone", "--hermes"], ["--hermes", "--standalone"]):
        r = _run([*args, "--dry-run"], home)
        assert r.returncode != 0
        assert "mutually exclusive" in r.stderr


def test_standalone_target_validation_still_applies(tmp_path: Path):
    home = _home(tmp_path)
    # $HOME itself
    r = _run(["--standalone", "--dry-run"], home, SIGIL_FORGE_HOME=str(home))
    assert r.returncode != 0 and "HOME" in r.stderr
    # source tree
    r = _run(["--standalone", "--dry-run"], home, SIGIL_FORGE_HOME=str(ROOT))
    assert r.returncode != 0 and "source tree" in r.stderr
    # outside home without the flag
    outside = tmp_path / "elsewhere" / "sf"
    r = _run(["--standalone", "--dry-run"], home, SIGIL_FORGE_HOME=str(outside))
    assert r.returncode != 0 and "outside" in r.stderr
    # system prefix
    r = _run(["--standalone", "--dry-run"], home, SIGIL_FORGE_HOME="/usr/local/sf")
    assert r.returncode != 0 and "system path" in r.stderr
    # root
    r = _run(["--standalone", "--dry-run"], home, SIGIL_FORGE_HOME="/")
    assert r.returncode != 0
    # untrusted symlink
    real = home / "real"
    real.mkdir()
    link = home / "link"
    link.symlink_to(real)
    r = _run(["--standalone", "--dry-run"], home, SIGIL_FORGE_HOME=str(link / "sf"))
    assert r.returncode != 0 and "symlink" in r.stderr


def test_usage_documents_modes(tmp_path: Path):
    r = _run(["--help"], _home(tmp_path))
    assert r.returncode == 0
    for flag in ("--standalone", "--hermes", "--target"):
        assert flag in r.stdout
