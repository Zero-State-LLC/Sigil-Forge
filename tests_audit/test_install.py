"""Installer runs only in temporary homes, never a real Hermes profile."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = "sigil-forge"


class InstallAudit(unittest.TestCase):
    def test_profile_dry_run_has_no_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            profile = home / "named profile"
            env = dict(os.environ, HOME=str(home), HERMES_HOME=str(profile))
            r = subprocess.run(
                check=False,
                args=["bash", str(ROOT / "install.sh"), "--dry-run"],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn(str(profile / "skills" / SKILL), r.stdout)
            self.assertEqual(list(home.iterdir()), [])

    def test_failed_check_preserves_previous_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            profile = home / "profile"
            dest = profile / "skills" / SKILL
            dest.mkdir(parents=True)
            (dest / "SKILL.md").write_text("previous package")
            (dest / "out/wizard-sessions").mkdir(parents=True)
            sentinel = dest / "out/wizard-sessions/keep.json"
            sentinel.write_text("previous session")
            import shutil

            source = Path(tmp) / "source"
            shutil.copytree(
                ROOT,
                source,
                ignore=shutil.ignore_patterns(
                    ".git", "skills", "out", "__pycache__", ".venv"
                ),
            )
            script = {
                "neon-genie": "validate_hermes_skill.py",
                "sigil-forge": "sigil_forge.py",
                "hyperlex": "hyperlex.py",
            }[SKILL]
            (source / "scripts" / script).write_text("import sys\nsys.exit(42)\n")
            env = dict(os.environ, HOME=str(home), HERMES_HOME=str(profile))
            r = subprocess.run(
                check=False,
                args=["bash", str(source / "install.sh")],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual((dest / "SKILL.md").read_text(), "previous package")
            self.assertEqual(sentinel.read_text(), "previous session")
            self.assertFalse((home / ".hermes").exists())

    def test_reinstall_preserves_outputs_and_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            profile = home / "profile"
            dest = profile / "skills" / SKILL
            (dest / "out/wizard-sessions").mkdir(parents=True)
            sentinel = dest / "out/wizard-sessions/keep.json"
            sentinel.write_text("previous session")
            wallpaper = dest / "out/wallpaper.png"
            wallpaper.write_bytes(b"previous wallpaper")
            env = dict(os.environ, HOME=str(home), HERMES_HOME=str(profile))
            r = subprocess.run(
                check=False,
                args=["bash", str(ROOT / "install.sh")],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(sentinel.is_file(), "saved session disappeared")
            self.assertEqual(sentinel.read_text(), "previous session")
            self.assertEqual(wallpaper.read_bytes(), b"previous wallpaper")
            self.assertFalse((home / ".hermes").exists())
            self.assertFalse((dest.parent / (SKILL + ".bak")).exists())

    def test_profile_skills_symlink_cannot_redirect_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            profile = home / "profile-a"
            foreign = home / "profile-b/skills"
            profile.mkdir(parents=True)
            foreign.mkdir(parents=True)
            (profile / "skills").symlink_to(foreign, target_is_directory=True)
            env = dict(os.environ, HOME=str(home), HERMES_HOME=str(profile))
            r = subprocess.run(
                ["bash", str(ROOT / "install.sh")],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(list(foreign.iterdir()), [])
            self.assertTrue((profile / "skills").is_symlink())


if __name__ == "__main__":
    unittest.main()
