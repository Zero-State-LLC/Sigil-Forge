"""Sigil-Forge must work on its own: no host stack is required to run it.

Integrations (Hermes, Abraxas, anything else) read Sigil-Forge's public output
files or call its CLI. The engine never imports them. These tests keep it so.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "sigil_forge"

# Third-party imports the engine may attempt. Each is optional and guarded.
OPTIONAL = {"yaml", "jsonschema", "argon2", "cryptography", "cairosvg", "svglib", "reportlab"}
HOST_STACKS = ("abraxas", "abx", "aal_core", "hermes", "hyperlex", "noema")


def _imported_top_level_names() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                found.setdefault(name.split(".")[0], set()).add(path.name)
    return found


def test_engine_imports_only_stdlib_itself_and_declared_optionals():
    imported = _imported_top_level_names()
    unexpected = {
        name: sorted(files)
        for name, files in imported.items()
        if name != "sigil_forge"
        and name not in sys.stdlib_module_names
        and name not in OPTIONAL
    }
    assert not unexpected, f"undeclared third-party imports: {unexpected}"


def test_engine_never_imports_a_host_stack():
    imported = _imported_top_level_names()
    hits = {name: sorted(imported[name]) for name in HOST_STACKS if name in imported}
    assert not hits, f"engine imports a host stack: {hits}"


def test_runs_end_to_end_with_no_host_environment(tmp_path):
    """construct + verify with every host variable removed and a bare HOME."""
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("HERMES_", "ABX_", "ABRAXAS_", "SIGIL_FORGE_"))
    }
    env["HOME"] = str(tmp_path / "home")
    (tmp_path / "home").mkdir()
    out = tmp_path / "out"
    cli = [sys.executable, str(ROOT / "scripts" / "sigil_forge.py")]
    made = subprocess.run(
        [*cli, "construct", "--intent", "I maintain calm focus", "--out", str(out)],
        env=env, cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert made.returncode == 0, made.stderr + made.stdout
    runs = [d for d in out.iterdir() if d.is_dir()]
    assert len(runs) == 1
    checked = subprocess.run(
        [*cli, "verify", str(runs[0] / "glyph.svg")],
        env=env, cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert checked.returncode == 0, checked.stderr + checked.stdout
