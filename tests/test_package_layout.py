"""The engine is the importable package ``sigil_forge`` under ``src/``.

Bare module names (``import paths``) are gone on purpose; the two
``scripts/`` shims keep the documented entry points working.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _clean_env(**extra: str) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("HERMES_", "SIGIL_FORGE_", "PYTHON"))
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


def _run(args: list[str], cwd: Path, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=_clean_env(**env),
    )


def test_package_imports_from_src_only(tmp_path):
    r = _run(["-c", "import sigil_forge.construct, sigil_forge.cli; print('ok')"], tmp_path, PYTHONPATH=str(SRC))
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "ok"


def test_bare_module_names_are_not_importable(tmp_path):
    r = _run(["-c", "import paths"], tmp_path, PYTHONPATH=str(SRC))
    assert r.returncode != 0
    assert "ModuleNotFoundError" in r.stderr
    # Importing the package must not put src/sigil_forge/ on sys.path either.
    code = (
        "import sigil_forge.cli\n"
        "try:\n    import paths\nexcept ModuleNotFoundError:\n    print('absent')\n"
    )
    r = _run(["-c", code], tmp_path, PYTHONPATH=str(SRC))
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "absent"


def test_python_m_sigil_forge_help(tmp_path):
    r = _run(["-m", "sigil_forge", "help"], tmp_path, PYTHONPATH=str(SRC))
    assert r.returncode == 0, r.stderr
    assert "sigil-forge" in r.stdout


def test_cli_shim_check_from_outside_repo(tmp_path):
    r = _run([str(ROOT / "scripts" / "sigil_forge.py"), "check"], tmp_path, HOME=str(tmp_path / "home"))
    assert r.returncode == 0, r.stderr + r.stdout
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert Path(payload["root"]).resolve() == ROOT


def test_validator_shim_matches_package_module(tmp_path):
    shim = _run([str(ROOT / "scripts" / "validate_hermes_skill.py")], tmp_path)
    pkg = _run(
        ["-c", "from sigil_forge.validate_hermes_skill import main; raise SystemExit(main())"],
        tmp_path,
        PYTHONPATH=str(SRC),
    )
    assert shim.returncode == pkg.returncode == 0, shim.stderr + pkg.stderr
    assert shim.stdout == pkg.stdout


def test_pyproject_builds_the_src_package():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.setuptools.packages.find]" in text
    assert 'where = ["src"]' in text
    assert "py-modules" not in text
    assert 'sigil-forge = "sigil_forge.cli:main"' in text
