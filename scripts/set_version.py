#!/usr/bin/env python3
"""Set the release version everywhere it is written.

    python3 scripts/set_version.py 0.16.0     # write
    python3 scripts/set_version.py --check    # exit 1 if any place disagrees with VERSION

VERSION is the source of truth (pyproject.toml reads it). The other places
below repeat it for people and for hosts that read a file directly. Each is
one exact pattern, so a release cannot miss one and nothing else is touched.
Release notes (CHANGELOG.md, the roadmap table) are written by hand.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"\d+\.\d+\.\d+")
V = r"\d+\.\d+\.\d+"

# (file, pattern with the version as group 2, how many times it must match)
PLACES: list[tuple[str, str, int]] = [
    ("SKILL.md", rf"(?m)^(version: )({V})$", 1),
    ("README.md", rf"(<strong>v)({V})(?=</strong>)", 1),
    ("QUICKSTART.md", rf"(\*\*Current version: )({V})(?=\.\*\*)", 1),
    ("docs/index.html", rf'(<p class="eyebrow">v)({V})(?= )', 1),
    ("docs/index.html", rf"(Release · )({V})(?=<)", 1),
    ("docs/index.html", rf"(© \d{{4}} · v)({V})(?=<)", 1),
    ("references/expansion-spine.md", rf"(\*\*Current release: v)({V})(?=\*\*)", 1),
    (
        "integrations/grok-bot/SKILL.md",
        rf"(git clone --depth 1 --branch v)({V})(?= https://github\.com/Zero-State-LLC/Sigil-Forge )",
        1,
    ),
]


def current() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def found() -> list[tuple[str, str, list[str]]]:
    """(file, pattern, versions found) for every place; raises if a place is missing."""
    out = []
    for rel, pattern, count in PLACES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        versions = [m.group(2) for m in re.finditer(pattern, text)]
        if len(versions) != count:
            raise SystemExit(f"{rel}: expected {count} match(es) of {pattern!r}, found {len(versions)}")
        out.append((rel, pattern, versions))
    return out


def check() -> list[str]:
    version = current()
    problems = [] if SEMVER.fullmatch(version) else [f"VERSION is not MAJOR.MINOR.PATCH: {version!r}"]
    for rel, _pattern, versions in found():
        problems += [f"{rel}: says {v}, VERSION is {version}" for v in versions if v != version]
    return problems


def write(version: str) -> None:
    if not SEMVER.fullmatch(version):
        raise SystemExit(f"not MAJOR.MINOR.PATCH: {version!r}")
    found()  # every place must exist before anything is changed
    (ROOT / "VERSION").write_text(version + "\n", encoding="utf-8")
    for rel, pattern, _count in PLACES:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        path.write_text(re.sub(pattern, lambda m: m.group(1) + version, text), encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    if argv[0] == "--check":
        problems = check()
        for line in problems:
            print(line, file=sys.stderr)
        print(f"version {current()}: " + ("consistent" if not problems else "INCONSISTENT"))
        return 1 if problems else 0
    write(argv[0])
    print(f"version set to {argv[0]}; now add the CHANGELOG.md section and the roadmap row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
