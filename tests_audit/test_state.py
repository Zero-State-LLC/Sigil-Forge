"""Default mutable state belongs to the active profile, not the package."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/sigil_forge.py"


class StateAudit(unittest.TestCase):
    def test_state_is_external(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(
                os.environ,
                HOME=tmp,
                HERMES_HOME=str(Path(tmp) / "profile"),
                HERMES_SKILL_DIR=str(ROOT),
            )
            env.pop("SIGIL_FORGE_STATE_DIR", None)
            code = "import sys; sys.path.insert(0, sys.argv[1]); from paths import default_out_dir; print(default_out_dir())"
            r = subprocess.run(
                [sys.executable, "-c", code, str(ROOT / "scripts")],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertTrue(
                Path(r.stdout.strip()).is_relative_to(
                    Path(tmp) / "profile/state/sigil-forge"
                )
            )

    def test_documented_session_handoff_from_unrelated_cwd(self):
        for doc in ["SKILL.md", "README.md"]:
            self.assertIn(
                "wizard --session <id> --path quick --out", (ROOT / doc).read_text()
            )
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(
                os.environ,
                HOME=tmp,
                HERMES_HOME=str(Path(tmp) / "profile"),
                SIGIL_FORGE_STATE_DIR=str(Path(tmp) / "state"),
            )

            def run(*args):
                r = subprocess.run(
                    check=False,
                    args=[sys.executable, str(CLI), "wizard", *args],
                    cwd=tmp,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                return json.loads(r.stdout)

            session = run("--session-new", "--path", "quick")["session"]["session_id"]
            run(
                "--next",
                "--session",
                session,
                "--path",
                "quick",
                "--answers-json",
                json.dumps({"intent": "I maintain calm focus"}),
            )
            done = run(
                "--next",
                "--session",
                session,
                "--path",
                "quick",
                "--answers-json",
                json.dumps({"mode": "creative", "wallpaper": False}),
            )
            self.assertTrue(done["done"])
            result = run(
                "--session",
                session,
                "--path",
                "quick",
                "--out",
                str(Path(tmp) / "product"),
            )
            self.assertTrue(result["ok"], result)
            self.assertTrue(list((Path(tmp) / "product").rglob("glyph.svg")))
            self.assertFalse((Path(tmp) / "answers.json").exists())

    def test_legacy_session_can_resume_without_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / "old/out/wizard-sessions/legacy-id.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                json.dumps(
                    {
                        "session_id": "legacy-id",
                        "path": "quick",
                        "answers": {"intent": "I maintain calm focus"},
                    }
                )
            )
            env = dict(
                os.environ,
                HOME=tmp,
                HERMES_HOME=str(Path(tmp) / "profile"),
                HERMES_SKILL_DIR=str(Path(tmp) / "old"),
            )
            env.pop("SIGIL_FORGE_STATE_DIR", None)
            r = subprocess.run(
                check=False,
                args=[
                    sys.executable,
                    str(CLI),
                    "wizard",
                    "--next",
                    "--session",
                    "legacy-id",
                    "--path",
                    "quick",
                    "--answers-json",
                    '{"mode":"creative","wallpaper":false}',
                ],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(json.loads(r.stdout)["done"])
            self.assertTrue(legacy.exists())
            self.assertTrue(
                (
                    Path(tmp)
                    / "profile/state/sigil-forge/wizard-sessions/legacy-id.json"
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
