"""Regression coverage for installer PR follow-up; shared across distributions."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "transaction_followup", ROOT / "scripts/install_transaction.py"
)
assert spec is not None and spec.loader is not None
transaction = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transaction)


class FollowupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("new")
        (self.source / "VERSION").write_text("1")
        self.target = self.base / "target"
        self.home = self.base / "profile"
        env = patch.dict(os.environ, HERMES_HOME=str(self.home))
        env.start()
        self.addCleanup(env.stop)
        key = hashlib.sha256(str(self.target).encode()).hexdigest()[:20]
        self.backups = self.home / "backups/hyperlex" / key

    def install(self):
        transaction.install(self.source, self.target, "hyperlex", True)

    def receipt(self):
        return json.loads((self.target / ".install-provenance.json").read_text())

    def test_archive_dirty_state_is_unknown(self):
        self.install()
        self.assertIsNone(self.receipt()["source_dirty"])

    def test_enclosing_repository_is_not_source_provenance(self):
        subprocess.run(["git", "init", str(self.base)], check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.base),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--allow-empty",
                "-m",
                "unrelated",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.base),
                "remote",
                "add",
                "origin",
                "https://example.invalid/unrelated",
            ],
            check=True,
        )
        self.install()
        for field in ("repository", "source_commit", "source_dirty"):
            self.assertIsNone(self.receipt()[field], field)

    def test_missing_git_does_not_block_install(self):
        with patch.dict(os.environ, PATH=str(self.base / "no-executables")):
            self.install()
        for field in ("repository", "source_commit", "source_dirty"):
            self.assertIsNone(self.receipt()[field], field)

    def test_stale_lock_error_and_docs_are_actionable(self):
        lock = self.target.parent / ("." + self.target.name + ".install-lock")
        lock.mkdir()
        with self.assertRaisesRegex(
            FileExistsError, "Do not reclaim automatically"
        ) as error:
            self.install()
        self.assertIn(str(lock), str(error.exception))
        self.assertIn("rmdir", str(error.exception))
        self.assertTrue(lock.is_dir())
        self.assertFalse(self.target.exists())
        docs = (ROOT / "references/source-and-upgrades.md").read_text()
        for phrase in (
            "rmdir",
            "SIGKILL",
            "no installer",
            ".install-lock",
            ".backup-incomplete-",
        ):
            self.assertIn(phrase, docs)

    def test_tracked_neon_hub_retains_repository_and_subtree(self):
        repo = self.base / "neon"
        hub = repo / "skills/neon-genie"
        hub.mkdir(parents=True)
        for directory in (repo, hub):
            license_id = "MIT" if directory == repo else "Apache-2.0"
            (directory / "SKILL.md").write_text(
                f"---\nname: neon-genie\nlicense: {license_id}\n---\n"
            )
            (directory / "VERSION").write_text("1")
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-m",
                "hub",
            ],
            check=True,
            capture_output=True,
        )
        transaction.install(hub, self.target, "neon-genie", True)
        receipt = self.receipt()
        self.assertIsNotNone(receipt["source_commit"])
        self.assertIs(receipt["source_dirty"], False)
        self.assertEqual(receipt["source_subdirectory"], "skills/neon-genie")
        self.assertEqual(receipt["source_repository_root"], str(repo))

    def test_partial_backup_never_published(self):
        self.install()
        self.install()
        previous = set(self.backups.iterdir())
        copytree = shutil.copytree

        def interrupt(src, dst, *args, **kwargs):
            if Path(src) == self.target:
                Path(dst).mkdir()
                (Path(dst) / "truncated").write_text("partial")
                raise KeyboardInterrupt("backup copy interrupted")
            return copytree(src, dst, *args, **kwargs)

        with (
            patch.object(transaction.shutil, "copytree", side_effect=interrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.install()
        self.assertEqual(set(self.backups.iterdir()), previous)
        self.assertEqual((self.target / "SKILL.md").read_text(), "new")
        transaction.rollback(self.target, "hyperlex", True)

    def test_rollback_skips_legacy_partial_backup(self):
        self.install()
        self.install()
        partial = self.backups / "partial"
        partial.mkdir()
        os.utime(partial, (2000000000, 2000000000))
        transaction.rollback(self.target, "hyperlex", True)
        self.assertEqual((self.target / "SKILL.md").read_text(), "new")
