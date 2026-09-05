"""Adversarial transactions: sandbox only, no mocked runtime successes."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "install_transaction", ROOT / "scripts/install_transaction.py"
)
assert spec is not None and spec.loader is not None
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class TransactionAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "VERSION").write_text("1")
        (self.source / "SKILL.md").write_text("new")
        self.target = self.root / "profile/skills/test"
        self.env = patch.dict(
            os.environ,
            HOME=str(self.root / "home"),
            HERMES_HOME=str(self.root / "profile"),
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def install(self):
        m.install(self.source, self.target, "hyperlex", skip_checks=True)

    def previous(self):
        self.target.mkdir(parents=True)
        (self.target / "SKILL.md").write_text("old")

    def test_final_and_dangling_target_symlinks_rejected(self):
        self.target.parent.mkdir(parents=True)
        for exists in (True, False):
            referent = self.root / str(exists)
            if exists:
                referent.mkdir()
            self.target.symlink_to(referent, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.install()
            self.assertTrue(self.target.is_symlink())
            self.assertFalse((referent / "SKILL.md").exists())
            self.target.unlink()

    def test_source_ancestor_rejected(self):
        self.target = self.root
        with self.assertRaises(ValueError):
            self.install()

    def test_secrets_not_packaged(self):
        (self.source / ".env").write_text("FAKE_SECRET=do-not-copy")
        (self.source / ".env.local").write_text("do-not-copy")
        self.install()
        self.assertFalse((self.target / ".env").exists())
        self.assertFalse((self.target / ".env.local").exists())

    def test_source_symlink_rejected(self):
        (self.source / "linked-secret").symlink_to(self.root / "private")
        with self.assertRaises(ValueError):
            self.install()

    def test_output_symlink_preserved_without_crawling(self):
        self.previous()
        private = self.root / "private"
        private.mkdir()
        (private / "keep").write_text("keep")
        (self.target / "out").symlink_to(private, target_is_directory=True)
        self.install()
        self.assertTrue((self.target / "out").is_symlink())
        self.assertEqual((private / "keep").read_text(), "keep")

    def test_activation_failure_restores_previous(self):
        self.previous()
        replace = os.replace

        def fail(src, dst):
            if Path(src).name == "package":
                raise OSError("injected activation failure")
            return replace(src, dst)

        with (
            patch.object(m.os, "replace", side_effect=fail),
            self.assertRaises(OSError),
        ):
            self.install()
        self.assertEqual((self.target / "SKILL.md").read_text(), "old")

    def test_restoration_failure_retains_recovery_tree(self):
        self.previous()
        replace = os.replace

        def fail(src, dst):
            if Path(src).name in ("package", "previous"):
                raise OSError("injected rename failure")
            return replace(src, dst)

        with (
            patch.object(m.os, "replace", side_effect=fail),
            self.assertRaises(RuntimeError),
        ):
            self.install()
        recovered = list(self.target.parent.glob(".hyperlex-stage-*/previous/SKILL.md"))
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].read_text(), "old")

    def test_existing_lock_fails_closed(self):
        self.target.parent.mkdir(parents=True)
        lock = self.target.parent / ("." + self.target.name + ".install-lock")
        lock.mkdir()
        with self.assertRaises(FileExistsError):
            self.install()
        self.assertTrue(lock.is_dir())


if __name__ == "__main__":
    unittest.main()
