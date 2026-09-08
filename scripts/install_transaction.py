"""Staged, checked upgrades with target-keyed backups and recovery.

The two renames have an absent-target window; this is not crash-atomic. Stop
runtime writers during upgrades. A retained recovery directory requires operator
inspection. No live profile is used by validation subprocesses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

CHECKS = {
    "neon-genie": [("validate_hermes_skill.py",), ("neon_genie.py", "do", "check")],
    "sigil-forge": [("validate_hermes_skill.py",), ("sigil_forge.py", "check")],
    "hyperlex": [("hyperlex.py", "check"), ("hyperlex.py", "smoke")],
}
IGNORE = shutil.ignore_patterns(
    ".git",
    "skills",
    "out",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "*.pyc",
    ".worktrees",
    "graft",
    ".env",
    ".env.*",
    ".hermes",
    "*.pem",
    "*.key",
    ".superpowers",
    "superpowers",
)


def install(source: Path, target: Path, kind: str, skip_checks: bool = False) -> None:
    # Check the lexical final component before resolve follows a dangling link.
    if any(p.is_symlink() for p in (target.absolute(), *target.absolute().parents)):
        raise ValueError("refusing symlink target")
    source, target = source.resolve(), target.resolve()
    if source == target or source in target.parents or target in source.parents:
        raise ValueError("source and target must not overlap")
    home = Path(os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")).resolve()
    if target in (Path("/"), Path.home().resolve(), home, home / "skills"):
        raise ValueError("refusing installation root")
    if target.exists() and not target.is_dir():
        raise ValueError("target must be a directory")
    key = hashlib.sha256(str(target).encode()).hexdigest()[:20]
    backups = home / "backups" / kind / key
    if target == backups or target in backups.parents or backups in target.parents:
        raise ValueError("backup and target must not overlap")
    # Reject payload links rather than shipping aliases into private source state.
    for directory, dirs, files in os.walk(source, followlinks=False):
        ignored = IGNORE(directory, dirs + files)
        dirs[:] = [d for d in dirs if d not in ignored]
        for name in dirs + [f for f in files if f not in ignored]:
            if (Path(directory) / name).is_symlink():
                raise ValueError(f"source payload symlink is not portable: {name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.parent / ("." + target.name + ".install-lock")
    try:
        lock.mkdir()  # exclusive; never remove another installer's lock
    except FileExistsError as exc:
        raise FileExistsError(
            f"Install lock exists: {lock}. Do not reclaim automatically. "
            "Stop launchers and confirm no installer or runtime writer is active; "
            "inspect the target, sibling stage/recovery directories and backups. "
            "Only after resolving recovery, use rmdir on this exact empty lock "
            "(never recursive removal), then retry. See references/source-and-upgrades.md."
        ) from exc
    workspace = None
    retain_recovery = False
    try:
        workspace = Path(
            tempfile.mkdtemp(prefix="." + kind + "-stage-", dir=target.parent)
        )
        stage = workspace / "package"
        shutil.copytree(source, stage, ignore=IGNORE)
        check_home = workspace / "check-home"
        check_home.mkdir()
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("HYPERLEX_", "SIGIL_FORGE_"))
        }
        env.update(
            HOME=str(check_home),
            HERMES_HOME=str(check_home / ".hermes"),
            HERMES_SKILL_DIR=str(stage),
            SIGIL_FORGE_STATE_DIR=str(check_home / "state"),
            PYTHONDONTWRITEBYTECODE="1",
        )
        if not skip_checks:
            for command in CHECKS[kind]:
                subprocess.run(
                    [sys.executable, str(stage / "scripts" / command[0]), *command[1:]],
                    cwd=check_home,
                    env=env,
                    check=True,
                )
        if (stage / "out").exists():
            shutil.rmtree(stage / "out")  # NEW staging data only
        old_out = target / "out"
        if old_out.is_symlink():
            (stage / "out").symlink_to(os.readlink(old_out), target_is_directory=True)
        elif old_out.exists():
            shutil.copytree(old_out, stage / "out", symlinks=True)

        def git(*args: str) -> str | None:
            try:
                r = subprocess.run(
                    check=False,
                    args=["git", "-C", str(source), *args],
                    capture_output=True,
                    text=True,
                    env={
                        k: v for k, v in os.environ.items() if not k.startswith("GIT_")
                    },
                )
            except OSError:
                return None  # Git is optional for archive/Python-only installs.
            return r.stdout.strip() if r.returncode == 0 else None

        # Git searches parents: accept the source root or the tracked Neon hub,
        # not arbitrary archives nested in an unrelated worktree.
        top = git("rev-parse", "--show-toplevel")
        repo_root = Path(top).resolve() if top is not None else None
        own_checkout = repo_root == source
        subtree = "." if own_checkout else None
        if (
            repo_root is not None
            and kind == "neon-genie"
            and source == repo_root / "skills/neon-genie"
        ):
            tracked = git(
                "ls-files",
                "--error-unmatch",
                "--",
                "SKILL.md",
                "VERSION",
                str(repo_root / "SKILL.md"),
                str(repo_root / "VERSION"),
            )
            try:
                # Root/hub grants can legitimately differ; compare the contract
                # apart from its license metadata, without changing either grant.
                root_contract = (repo_root / "SKILL.md").read_text().splitlines()
                hub_contract = (source / "SKILL.md").read_text().splitlines()
                matching_root = [
                    line for line in root_contract if not line.startswith("license:")
                ] == [
                    line for line in hub_contract if not line.startswith("license:")
                ] and (repo_root / "VERSION").read_bytes() == (
                    source / "VERSION"
                ).read_bytes()
            except (OSError, UnicodeError):
                matching_root = False
            if tracked is not None and matching_root:
                own_checkout = True
                subtree = "skills/neon-genie"
        dirty = git("status", "--porcelain") if own_checkout else None
        receipt = {
            "source": str(source),
            "source_repository_root": str(repo_root) if own_checkout else None,
            "source_subdirectory": subtree,
            "repository": git("remote", "get-url", "origin") if own_checkout else None,
            "source_commit": git("rev-parse", "HEAD") if own_checkout else None,
            "source_dirty": bool(dirty) if dirty is not None else None,
            "version": (source / "VERSION").read_text().strip(),
            "destination": str(target),
            "status": "UNVERIFIED" if skip_checks else "VALIDATED",
            "checks_skipped": list(CHECKS[kind]) if skip_checks else [],
            "validation": "staged runtime; activated contract/version read-back",
        }
        receipt_text = json.dumps(receipt, indent=2) + "\n"
        (stage / ".install-provenance.json").write_text(receipt_text)
        expected = {
            p: (stage / p).read_bytes()
            for p in ("SKILL.md", "VERSION", ".install-provenance.json")
        }
        backup = None
        if target.exists():
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / uuid.uuid4().hex
            # Incomplete copies live outside the selectable backup namespace.
            # Publish only after the payload and destination record are complete.
            with tempfile.TemporaryDirectory(
                prefix=".backup-incomplete-", dir=backups.parent
            ) as tmp:
                pending = Path(tmp) / "backup-payload"
                shutil.copytree(target, pending, symlinks=True)
                marker = pending / ".backup-target.json"
                marker.unlink(missing_ok=True)
                marker.write_text(json.dumps({"destination": str(target)}) + "\n")
                os.replace(pending, backup)
        displaced = workspace / "previous"
        # Detect a concurrent change of target identity since staging began.
        if any(p.is_symlink() for p in (target.absolute(), *target.absolute().parents)):
            raise ValueError("target became a symlink during staging")
        try:
            if target.exists():
                os.replace(target, displaced)
            os.replace(stage, target)
            for relative, content in expected.items():
                if (target / relative).read_bytes() != content:
                    raise OSError(f"activation read-back mismatch: {relative}")
        except BaseException as original:
            try:
                # Infer completed renames from disk even if replace raised after
                # its side effect. A still-staged package means target is not new.
                if not stage.exists() and target.exists():
                    os.replace(target, workspace / "failed-package")
                if displaced.exists():
                    os.replace(displaced, target)
            except BaseException as recovery_error:
                retain_recovery = True
                raise RuntimeError(
                    f"recovery required at {workspace}; backup {backup}; "
                    f"activation: {original}; restoration: {recovery_error}"
                ) from recovery_error
            raise
        print(f"Installed {kind}: {target} ({receipt['status']})")
        if backup:
            print(f"Backup: {backup}")
    finally:
        if workspace is not None and not retain_recovery:
            shutil.rmtree(workspace)
        lock.rmdir()


def rollback(target: Path, kind: str, skip_checks: bool = False) -> None:
    if any(p.is_symlink() for p in (target.absolute(), *target.absolute().parents)):
        raise ValueError("refusing symlink target")
    target = target.resolve()
    home = Path(os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")).resolve()
    key = hashlib.sha256(str(target).encode()).hexdigest()[:20]
    backups = home / "backups" / kind / key
    candidates = sorted(
        backups.glob("*"), key=lambda p: p.lstat().st_mtime_ns, reverse=True
    )
    backup = None
    for candidate in candidates:
        marker = candidate / ".backup-target.json"
        if candidate.is_symlink() or not candidate.is_dir() or marker.is_symlink():
            continue
        try:
            record = json.loads(marker.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and record.get("destination") == str(target):
            backup = candidate
            break
    if backup is None:
        raise ValueError(
            f"no target-bound backup for {target}; legacy backups require manual review"
        )
    # Reuse staged runtime checks, backup, activated read-back and failed-rename recovery.
    install(backup, target, kind, skip_checks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target")
    parser.add_argument("kind", choices=CHECKS)
    parser.add_argument("--skip-checks", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    try:
        if not args.target.strip():
            raise ValueError("empty target")
        if args.rollback:
            rollback(Path(args.target), args.kind, args.skip_checks)
        else:
            install(args.source, Path(args.target), args.kind, args.skip_checks)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
