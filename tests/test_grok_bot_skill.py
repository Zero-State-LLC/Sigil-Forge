"""The Grok Bot skill must describe the engine as it is.

Nobody can run Grok Bot in CI, so these tests pin what can be pinned: the file
is importable as a skill, every command in it exists with the flags shown, it
agrees with the Hermes contract on refusals and private files, and its install
and forge steps work in a clean home directory with no Hermes present.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "integrations" / "grok-bot" / "SKILL.md"
CLI = ROOT / "scripts" / "sigil_forge.py"
ENGINE = 'python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py"'


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _frontmatter() -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", _text(), re.S)
    assert m, "SKILL.md must start with YAML frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def _bash_lines() -> list[str]:
    lines: list[str] = []
    for block in re.findall(r"```bash\n(.*?)```", _text(), re.S):
        lines += [ln.strip() for ln in block.splitlines() if ln.strip()]
    return lines


def _engine_commands() -> list[list[str]]:
    """Argument lists of every engine invocation in the skill's bash blocks."""
    cmds = [shlex.split(ln[len(ENGINE):]) for ln in _bash_lines() if ln.startswith(ENGINE)]
    assert len(cmds) >= 10
    return cmds


def test_frontmatter_names_and_describes_the_skill():
    fm = _frontmatter()
    assert fm["name"] == "sigil-forge"
    # Grok Bot uses the description to decide when the skill applies, and
    # refuses to publish a skill without one.
    assert 40 <= len(fm["description"]) <= 300
    assert set(fm) == {"name", "description"}


def test_skill_is_self_contained_for_a_bot_without_hermes():
    text = _text()
    for hermes_only in ("HERMES_SKILL_DIR", "HERMES_HOME", "~/.hermes", "terminal(", "[[as_document]]"):
        assert hermes_only not in text
    # Every engine call goes through the standalone root the skill sets up.
    for line in _bash_lines():
        if "sigil_forge.py" in line:
            assert line.startswith(ENGINE), line
    assert 'export SIGIL_FORGE_HOME="$HOME/.sigil-forge"' in text
    assert "install.sh\" --standalone" in text


def test_every_documented_command_and_flag_exists():
    def help_for(path: tuple[str, ...]) -> str:
        r = subprocess.run(
            [sys.executable, str(CLI), *path, "--help"], capture_output=True, text=True
        )
        assert r.returncode == 0, f"{path}: {r.stderr}"
        return r.stdout

    top = help_for(())
    for argv in _engine_commands():
        sub = argv[0]
        assert re.search(rf"\b{re.escape(sub)}\b", top), f"unknown command {sub}"
        path = (sub, argv[1]) if sub == "policy" else (sub,)
        text = help_for(path)
        for flag in (a for a in argv if a.startswith("--")):
            assert re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", text), (
                f"{' '.join(path)} has no {flag}"
            )


def test_documented_surfaces_are_real():
    line = next(ln for ln in _text().splitlines() if "phone_lock" in ln and "default" in ln)
    block = _text()[_text().index(line) :][:300]
    surfaces = set(re.findall(r"`([a-z_]+)`", block))
    r = subprocess.run(
        [sys.executable, str(CLI), "construct", "--help"], capture_output=True, text=True
    )
    for surface in ("phone_lock", "phone_home", "tablet", "desktop", "desktop_ultrawide"):
        assert surface in surfaces
        assert surface in r.stdout


def test_skill_keeps_the_hermes_contract_boundaries():
    """Same refusals, same private files, same human-only steps."""
    text = _text().lower()
    for required in (
        "enochian",
        "goetic",
        "self-harm",
        "never say or imply that a sigil works",
        "forge-packet.json",
        "run-receipt.json",
        "intent-capsule.json",
        "never run `ledger promote`",
        "sigil_forge_passphrase",
        "do not put this skill in a routine",
    ):
        assert required in text, required
    # The passphrase is never shown on a command line.
    for line in _bash_lines():
        assert "--passphrase" not in line
        assert "SIGIL_FORGE_PASSPHRASE=" not in line


@pytest.mark.skipif(os.name != "posix" or not shutil.which("bash"), reason="needs bash")
def test_install_and_forge_steps_work_in_a_clean_home(tmp_path):
    """Run the skill's own lines 3a to 4, with the clone replaced by this checkout."""
    home = tmp_path / "home"
    home.mkdir()
    src = home / "sigil-forge-src"
    shutil.copytree(
        ROOT,
        src,
        ignore=shutil.ignore_patterns(
            ".git", ".claude", "out", "graft", ".venv", "__pycache__", ".pytest_cache", "*.pyc"
        ),
    )
    env = {"HOME": str(home), "PATH": os.environ["PATH"], "LANG": "C.UTF-8"}

    lines = _bash_lines()
    install = next(ln for ln in lines if "install.sh" in ln)
    assert install == 'bash "$HOME/sigil-forge-src/install.sh" --standalone'

    def sh(line: str, **extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", line], capture_output=True, text=True, env={**env, **extra}, cwd=str(home)
        )

    r = sh(install)
    assert r.returncode == 0, r.stderr[-2000:]
    engine_home = home / ".sigil-forge"
    assert (engine_home / "SKILL.md").is_file()
    assert (engine_home / "integrations" / "grok-bot" / "SKILL.md").is_file()
    engine_env = {"SIGIL_FORGE_HOME": str(engine_home)}

    check = sh(f"{ENGINE} check", **engine_env)
    assert check.returncode == 0, check.stdout[-2000:] + check.stderr[-2000:]
    assert json.loads(check.stdout)["ok"] is True

    policy = next(ln for ln in lines if " policy check " in ln)
    assert sh(policy, **engine_env).returncode == 0

    forge = next(ln for ln in lines if " construct " in ln)
    r = sh(forge, **engine_env)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout)
    assert out["ok"] is True
    wallpaper = out["wallpapers"][0]
    assert wallpaper["geometry_preserved"] is True
    png = Path(wallpaper["wallpaper"])
    assert png.is_file() and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    # Everything lands under the standalone root; no Hermes tree is created.
    assert engine_home.resolve() in png.resolve().parents
    assert not (home / ".hermes").exists()

    verify = next(ln for ln in lines if " verify " in ln).replace("PATH_TO_GLYPH_SVG", out["svg"])
    r = sh(verify, **engine_env)
    assert r.returncode == 0 and json.loads(r.stdout)["ok"] is True


def test_readme_says_what_is_not_verified():
    readme = (SKILL.parent / "README.md").read_text(encoding="utf-8")
    assert "Not verified" in readme
    assert "Add Custom Skill" in readme


# ------------------------------------------------------------------ BOT.md

BOT = SKILL.parent / "BOT.md"


def _brief() -> str:
    blocks = re.findall(r"```text\n(.*?)```", BOT.read_text(encoding="utf-8"), re.S)
    assert len(blocks) == 1, "BOT.md must hold exactly one brief to paste"
    return blocks[0]


def test_bot_brief_and_skill_state_the_same_limits():
    """A Bot given both must not find one permitting what the other forbids."""
    brief, skill = _brief().lower(), _text().lower()
    for shared in (
        "enochian",
        "goetic",
        "self-harm",
        "violence",
        "controlling another person",
        "exploitation",
        "ledger promote",
        "secure secret card",
        "install or update the engine",
        "open a sealed image or packet",
        "delete a run folder",
        "learning entry",
        "file attachment",
    ):
        assert shared in brief, f"brief lacks: {shared}"
        assert shared in skill, f"skill lacks: {shared}"
    assert "works" in brief and "replaces professional" in brief
    for private in ("packet", "receipts", "capsule", "proofs", "manifest"):
        assert private in brief


def test_bot_brief_defers_to_the_skill_and_is_safe_to_publish():
    brief = _brief()
    assert "sigil-forge skill" in brief
    # Commands live in the skill only, so the two cannot drift apart.
    assert "sigil_forge.py" not in brief and "python3" not in brief
    # A published template is public: the brief may name the public repo only.
    assert re.findall(r"https?://\S+", brief) == ["https://github.com/Zero-State-LLC/Sigil-Forge."]
    assert "@" not in brief
    assert len(brief) < 4000


def test_bot_never_gets_a_routine():
    assert "do not create routines" in _brief().lower()
    page = BOT.read_text(encoding="utf-8")
    assert "Do not add a routine" in page
    assert "The link is public" in page
    assert "## What is not verified" in page
