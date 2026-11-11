#!/usr/bin/env python3
"""Validate Sigil-Forge SKILL.md against Hermes Agent v0.21 hardline rules.

Sources: hermes-agent v2026.8.31 skill authoring standards + skill_utils.py.

  - frontmatter at byte 0 with --- close
  - required: name, description, version, author, license, platforms,
    metadata.hermes.tags, metadata.hermes.related_skills
  - description ≤ 60 chars, one sentence, ends with a period, no marketing words
  - Hermes index truncates at 57 chars + "..." (SKILL_PROMPT_DESC_LIMIT - 3)
  - name lowercase hyphens ≤ 64
  - body non-empty; total content ≤ 100_000 chars
  - quote description if it contains ":"
"""

from __future__ import annotations

import json
import re
from pathlib import Path

try:
    import yaml
except ImportError:  # stdlib-only fallback: _parse_minimal_yaml
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
MAX_DESCRIPTION = 60
MAX_NAME = 64
MAX_CONTENT = 100_000
# extract_skill_description() keeps SKILL_PROMPT_DESC_LIMIT (60) then
# replaces the tail with "...": desc[:57] + "..."
INDEX_TRUNCATE = 57
MARKETING_WORDS = (
    "powerful",
    "comprehensive",
    "seamless",
    "advanced",
    "cutting-edge",
    "state-of-the-art",
    "revolutionary",
    "robust",
)
REQUIRED_SECTIONS = (
    "## When to Use",
    "## Prerequisites",
    "## How to Run",
    "## Quick Reference",
    "## Procedure",
    "## Pitfalls",
    "## Verification",
)


_NON_STRING_PLAIN = re.compile(
    r"(?i)(?:true|false|yes|no|on|off|null|~)"
    r"|[-+]?(?:0x[0-9a-f_]+|0b[01_]+"
    r"|\d[\d_]*(?::[0-5]?\d)*(?:\.[\d_]*)?(?:e[-+]?\d+)?"
    r"|\.[\d_]+(?:e[-+]?\d+)?|\.(?:inf|nan))"
    r"|\d{4}-\d{1,2}-\d{1,2}.*"
)


def _needs_yaml(v: str):
    raise ValueError(f"frontmatter value {v!r} needs a full YAML parser; install PyYAML")


def _scalar(raw: str):
    """Fallback scalar: simple quoted string, inline list of plain words, or plain text.

    Anything PyYAML might read differently raises instead of being guessed at.
    """
    v = raw.strip()
    if v[:1] in ("\"", "'"):
        q = v[0]
        if len(v) < 2 or v[-1] != q:
            _needs_yaml(v)  # unterminated, trailing text or comment
        inner = v[1:-1]
        if q in inner or (q == '"' and "\\" in inner):
            _needs_yaml(v)  # escapes, doubled quotes, text after a closing quote
        return inner
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if any(c in inner for c in "\"'[]{}#"):
            _needs_yaml(v)
        if not inner:
            return []
        items = [item.strip() for item in inner.split(",")]
        if not all(items):
            _needs_yaml(v)
        return [_scalar(item) for item in items]
    if v[:1] in ("{", "&", "*", "!", "|", ">", "[", "#", "%", "@", "`") or v.startswith("- "):
        _needs_yaml(v)
    if re.search(r"\s#", v) or ": " in v or v.endswith(":"):
        _needs_yaml(v)
    if _NON_STRING_PLAIN.fullmatch(v):
        _needs_yaml(v)
    return v


def _parse_minimal_yaml(fm_raw: str) -> dict:
    """Stdlib-only parse of the YAML subset SKILL.md frontmatter uses.

    Nested block mappings, block lists of scalars, inline lists and plain or
    quoted scalars. Anything else fails closed rather than being misread.
    """
    lines = []
    for raw in fm_raw.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ValueError("frontmatter must be indented with spaces")
        lines.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))

    def block(i: int, indent: int):
        if lines[i][1].startswith("- "):
            items = []
            while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
                items.append(_scalar(lines[i][1][2:]))
                i += 1
            return items, i
        out: dict = {}
        while i < len(lines) and lines[i][0] == indent:
            key, sep, rest = lines[i][1].partition(":")
            if not sep or not key.strip() or (rest and not rest.startswith(" ")):
                raise ValueError(f"unsupported frontmatter line: {lines[i][1]!r}")
            if key[:1] in "\"'" or re.search(r"\s", key.strip()) or (
                _NON_STRING_PLAIN.fullmatch(key.strip())
            ):
                raise ValueError(
                    f"frontmatter key {key!r} needs a full YAML parser; install PyYAML"
                )
            i += 1
            if rest.strip():
                out[key.strip()] = _scalar(rest)
            elif i < len(lines) and lines[i][0] > indent:
                out[key.strip()], i = block(i, lines[i][0])
            else:
                out[key.strip()] = None
        return out, i

    if not lines:
        return {}
    fm, end = block(0, lines[0][0])
    if end != len(lines) or not isinstance(fm, dict):
        raise ValueError("unsupported frontmatter indentation")
    return fm


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with --- (no leading whitespace/BOM)")
    m = re.search(r"\n---\s*\n", text[3:])
    if not m:
        raise ValueError("SKILL.md frontmatter not closed with \\n---\\n")
    fm_raw = text[3 : 3 + m.start()]
    body = text[3 + m.end() :]
    if yaml is not None:
        fm = yaml.safe_load(fm_raw)
    else:
        fm = _parse_minimal_yaml(fm_raw)
    if not isinstance(fm, dict):
        raise ValueError("frontmatter is not a YAML mapping")
    return fm, body


def _description_raw_line(text: str) -> str | None:
    """Return the authored description: line (folded blocks collapse later)."""
    m = re.search(r"(?m)^description:\s*(.*)$", text)
    if not m:
        return None
    return m.group(1)


def validate(skill_path: Path = SKILL) -> dict:
    raw = skill_path.read_bytes()
    errors: list[str] = []
    warnings: list[str] = []

    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append("must start with --- at byte 0 (BOM present)")
    text = raw.decode("utf-8")
    if len(text) > MAX_CONTENT:
        errors.append(f"SKILL.md length {len(text)} > {MAX_CONTENT}")
    if not text.startswith("---"):
        errors.append("must start with --- at byte 0")

    try:
        fm, body = _parse_frontmatter(text)
    except ValueError as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    name = fm.get("name")
    desc = fm.get("description")
    if not name:
        errors.append("missing name")
    else:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(name)):
            errors.append(f"name must be lowercase-hyphen: {name!r}")
        if len(str(name)) > MAX_NAME:
            errors.append(f"name length {len(str(name))} > {MAX_NAME}")

    desc_len = 0
    desc_norm = ""
    if not desc:
        errors.append("missing description")
    else:
        desc_norm = " ".join(str(desc).split())
        desc_len = len(desc_norm)
        if desc_len > MAX_DESCRIPTION:
            errors.append(
                f"description length {desc_len} > {MAX_DESCRIPTION} "
                f"(Hermes index truncates at {INDEX_TRUNCATE} chars + '...')"
            )
        if not desc_norm.endswith("."):
            errors.append("description must be one sentence ending with a period")
        if desc_norm.count(".") > 1:
            errors.append("description must be one sentence")
        lower = desc_norm.lower()
        hits = [w for w in MARKETING_WORDS if re.search(rf"\b{re.escape(w)}\b", lower)]
        if hits:
            errors.append(f"description contains marketing words: {hits}")
        raw_line = _description_raw_line(text)
        if raw_line is not None and ":" in desc_norm:
            stripped = raw_line.strip()
            if not (
                (stripped.startswith('"') and stripped.endswith('"'))
                or (stripped.startswith("'") and stripped.endswith("'"))
            ):
                errors.append('description contains ":" and must be quoted')
        head = desc_norm[:INDEX_TRUNCATE]
        if "sigil" not in head.lower() and "intent" not in head.lower():
            warnings.append(
                f"first {INDEX_TRUNCATE} chars of description should include "
                f"primary triggers (got {head!r})"
            )

    if not body.strip():
        errors.append("empty body after frontmatter")

    for key in ("version", "author", "license", "platforms"):
        if key not in fm:
            errors.append(f"missing required field: {key}")

    platforms = fm.get("platforms")
    if platforms is not None:
        items = platforms if isinstance(platforms, list) else [platforms]
        valid = {"linux", "macos", "windows", "darwin"}
        bad = [p for p in items if str(p).lower() not in valid]
        if bad:
            errors.append(f"platforms contains unrecognized value(s): {bad}")
        if not items:
            errors.append("platforms must be a non-empty list")

    meta = fm.get("metadata")
    hermes = meta.get("hermes") if isinstance(meta, dict) else None
    if not isinstance(hermes, dict):
        errors.append("missing metadata.hermes")
    else:
        if "tags" not in hermes:
            errors.append("missing metadata.hermes.tags")
        if "related_skills" not in hermes:
            errors.append("missing metadata.hermes.related_skills (use [] if none)")
        elif not isinstance(hermes.get("related_skills"), list):
            errors.append("metadata.hermes.related_skills must be a list")

    author = str(fm.get("author") or "")
    if author and author.strip().lower() in ("hermes", "agent", "hermes agent"):
        errors.append(
            "author must credit the human first, then Hermes Agent "
            f"(got {author!r})"
        )

    fm_block = text.split("---", 2)[1] if text.startswith("---") else ""
    if re.search(r"(?m)^\s*blueprint\s*:", fm_block):
        errors.append("do not add metadata.hermes.blueprint / cron")

    for section in REQUIRED_SECTIONS:
        if section not in text:
            warnings.append(f"missing section: {section}")

    if "[[as_document]]" not in text:
        warnings.append("body should instruct the agent to emit [[as_document]]")
    if "${HERMES_SKILL_DIR}" not in text:
        warnings.append("command examples should use ${HERMES_SKILL_DIR}")

    ok = not errors
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "name": name,
        "description": desc_norm or None,
        "description_chars": desc_len,
        "description_index_preview": desc_norm[:INDEX_TRUNCATE] if desc_norm else None,
        "content_chars": len(text),
    }


def main() -> int:
    report = validate()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
