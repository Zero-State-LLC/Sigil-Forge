"""The advertised defaults must match external runtime state paths."""

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OutputHelpTests(unittest.TestCase):
    def test_cli_help_names_external_output_and_override(self):
        for command in ("construct", "wizard"):
            with self.subTest(command=command):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts/sigil_forge.py"),
                        command,
                        "--help",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                    env=dict(os.environ, HERMES_SKILL_DIR=str(ROOT), COLUMNS="180"),
                )
                text = " ".join(result.stdout.split())
                self.assertIn("$HERMES_HOME/state/sigil-forge/products", text)
                self.assertIn("$SIGIL_FORGE_STATE_DIR/products", text)
                self.assertNotIn("default: out/sigil-forge", text)
                self.assertNotIn("under out/wizard-sessions", text)

    def test_runtime_contract_names_external_outputs_and_sessions(self):
        text = (ROOT / "references/hermes-runtime-contract.md").read_text()
        for path in (
            "$HERMES_HOME/state/sigil-forge/products",
            "$SIGIL_FORGE_STATE_DIR/products",
            "$HERMES_HOME/state/sigil-forge/wizard-sessions",
        ):
            self.assertIn(path, text)
        self.assertNotIn("or skill `out/`", text)
