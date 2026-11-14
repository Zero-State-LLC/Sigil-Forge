"""Forge manifests hashed into sigil_root (neither ever contains sigil_root).

A run writes two, and each has its own leaf in ``artifact-root.json``:

- ``forge-manifest.json`` (schema 2.x, leaf ``forge_manifest_digest``) is
  **public**. It names what was done and with which methods, by identifier
  and digest only, so anyone can recompute its digest and check it against
  the root. It holds nothing derived from the intent text beyond the public
  digest and commitment.
- ``method-manifest.json`` (leaf ``method_manifest_digest``) is **private**.
  It holds the method detail: reduced letters, the transliteration, kamea
  and rose-cross sequences, per-channel counts. The intent can largely be
  read back from it. Neither file holds plaintext intent or a nonce.

Runs made before the split have a schema 1.x ``forge-manifest.json`` that
contains the method detail and one digest used for both leaves. Treat those
files as private. ``check_run_root`` tells the two apart.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from sigil_forge.artifact_root import merkle_root
from sigil_forge.safe_io import read_regular

PUBLIC_SCHEMA_VERSION = "2.0.0"
METHOD_SCHEMA_VERSION = "1.0.0"
PUBLIC_NAME = "forge-manifest.json"
METHOD_NAME = "method-manifest.json"
ROOT_NAME = "artifact-root.json"
MAX_MANIFEST_BYTES = 1024 * 1024

# Method fields that identify HOW something was made and say nothing about the
# intent's content. Anything else (letters, sequences, coordinates, counts,
# notes) stays in the private method manifest. Values must be short scalars.
PUBLIC_METHOD_KEYS = frozenset(
    {
        "family",
        "method_id",
        "system",
        "mode",
        "determinism",
        "status",
        "cipher",
        "encoding_system",
        "transliteration_system",
        "claimed_historical_status",
        "historical_basis",
        "semantic_verification",
        "reduction",
        "planet",  # chosen from the public digest, or named by the operator
    }
)
# An identifier: no spaces, so it cannot hold a sentence.
_PUBLIC_VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:+\-/]{0,63}")
_PUBLIC_KEY = re.compile(r"[a-z][a-z0-9_]{0,39}")
_VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+\-]{0,31}")
_SCHEMA_PUBLIC = re.compile(r"2\.\d{1,4}\.\d{1,4}")
_SCHEMA_LEGACY = re.compile(r"1\.\d{1,4}\.\d{1,4}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
PUBLIC_KEYS = frozenset(
    {
        "schema_version", "forge_engine_version", "forge_version", "intent_digest",
        "intent_commitment", "mode", "methods", "method_manifest_digest", "channels",
        "output", "construction",
    }
)
FORGE_MODES = ("creative", "practice")
CHANNEL_STATUSES = ("applied", "skipped", "private")
# Channels drawn from the intent's letters. Whether one applied can depend on
# the letters themselves (an intent with no consonants has no monogram), so
# the public manifest does not say; the private manifest does.
LETTER_CHANNELS = frozenset(
    {"spare_monogram", "kamea_path", "bind_runes", "rose_cross_path", "phonetic_sigil"}
)
ROOT_KEYS = frozenset({"schema_version", "domain", "sigil_root", "leaves"})
LEAF_TYPES = frozenset(
    {
        "canonical_glyph_digest", "ciphertext_digest", "forge_manifest_digest",
        "intent_commitment", "intent_digest", "method_manifest_digest",
    }
)


def public_methods(methods: dict[str, Any] | None) -> dict[str, Any]:
    """Identifier-only view of a methods block (see PUBLIC_METHOD_KEYS)."""

    def reduce(node: Any) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in sorted(node):
            value = node[key]
            if not isinstance(key, str) or not _PUBLIC_KEY.fullmatch(key):
                continue
            if isinstance(value, dict):
                inner = reduce(value)
                if inner:
                    out[key] = inner
            elif (
                key in PUBLIC_METHOD_KEYS
                and isinstance(value, str)
                and _PUBLIC_VALUE.fullmatch(value)
            ):
                out[key] = value
        return out

    result: dict[str, Any] = {}
    for name in sorted(methods or {}, key=str):
        if name == "sigil_root" or not isinstance(methods[name], dict):
            continue
        if not isinstance(name, str) or not _PUBLIC_KEY.fullmatch(name):
            continue
        result[name] = reduce(methods[name])
    return result


def public_channels(channels: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Channel ids with a status that says nothing about the intent's letters."""
    out = []
    for c in channels or []:
        cid = c.get("id")
        status = "private" if cid in LETTER_CHANNELS else c.get("status")
        out.append({"id": cid, "status": status})
    return out


def public_shape_problems(manifest: Any) -> list[str]:
    """Why a manifest does not have the public shape; empty when it does.

    This is a check of shape: exact keys, exact types, identifiers without
    spaces, known modes and statuses. It cannot know what a well-formed
    identifier means, so it shows a file was not altered into something
    carrying free text, not that its author put nothing private into it.
    """
    if not isinstance(manifest, dict):
        return ["not an object"]
    problems: list[str] = []
    if set(manifest) != PUBLIC_KEYS:
        problems.append("unexpected or missing top-level fields")
    for key in ("forge_engine_version", "forge_version"):
        if not isinstance(manifest.get(key), str) or not _VERSION.fullmatch(manifest[key]):
            problems.append(f"{key} is not a version string")
    for key in ("intent_digest", "intent_commitment", "method_manifest_digest"):
        if not isinstance(manifest.get(key), str) or not _HEX64.fullmatch(manifest[key]):
            problems.append(f"{key} is not a digest")
    if manifest.get("mode") not in FORGE_MODES:
        problems.append("mode is not a known forge mode")
    methods = manifest.get("methods")
    if not isinstance(methods, dict) or methods != public_methods(methods):
        problems.append("methods holds more than identifiers")
    channels = manifest.get("channels")
    if not isinstance(channels, list) or len(channels) > 64:
        problems.append("channels is not a list")
    else:
        for c in channels:
            if (
                not isinstance(c, dict)
                or set(c) != {"id", "status"}
                or not isinstance(c["id"], str)
                or not _PUBLIC_KEY.fullmatch(c["id"])
                or c["status"] not in CHANNEL_STATUSES
                or (c["id"] in LETTER_CHANNELS and c["status"] != "private")
            ):
                problems.append("a channel entry is not an id and a known status")
                break
    output = manifest.get("output")
    if not isinstance(output, dict) or set(output) != {"geometry_digest"} or not (
        output["geometry_digest"] is None
        or (isinstance(output["geometry_digest"], str) and _HEX64.fullmatch(output["geometry_digest"]))
    ):
        problems.append("output is not a single geometry digest")
    construction = manifest.get("construction")
    if (
        not isinstance(construction, dict)
        or set(construction) != {"algorithm_version"}
        or not isinstance(construction["algorithm_version"], str)
        or not _PUBLIC_VALUE.fullmatch(construction["algorithm_version"])
    ):
        problems.append("construction is not a single algorithm version")
    return problems


def build_method_manifest(
    *,
    forge_version: str,
    intent_digest: str,
    methods: dict[str, Any],
    channels: list[dict[str, Any]],
) -> dict[str, Any]:
    """Private manifest: full method detail and per-channel detail."""
    return {
        "schema_version": METHOD_SCHEMA_VERSION,
        "kind": "sigil_forge_method_manifest",
        "forge_version": forge_version,
        "intent_digest": (intent_digest or "").lower(),
        "methods": {k: v for k, v in (methods or {}).items() if k != "sigil_root"},
        "channels": [
            {"id": c.get("id"), "status": c.get("status"), "detail": c.get("detail")}
            for c in (channels or [])
        ],
    }


def build_forge_manifest(
    *,
    forge_version: str,
    intent_digest: str,
    intent_commitment: str,
    mode: str,
    methods: dict[str, Any],
    channels: list[dict[str, Any]],
    glyph_digest: str | None,
    construction: dict[str, Any] | None = None,
    method_manifest_digest: str | None = None,
) -> dict[str, Any]:
    """Deterministic public manifest: identifiers and digests only."""
    manifest: dict[str, Any] = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "forge_engine_version": "1",
        "forge_version": forge_version,
        "intent_digest": (intent_digest or "").lower(),
        "intent_commitment": (intent_commitment or "").lower(),
        "mode": mode,
        "methods": public_methods(methods),
        "method_manifest_digest": (method_manifest_digest or "").lower() or None,
        # Channel detail carries counts that follow the intent's length, so
        # only the id and status are public.
        "channels": public_channels(channels),
        "output": {
            "geometry_digest": (glyph_digest or "").lower() or None,
        },
        "construction": construction or {"algorithm_version": "construct-v1"},
    }
    if "sigil_root" in manifest:
        raise ValueError("forge_manifest must not contain sigil_root")
    return manifest


def manifest_digest(manifest: dict[str, Any]) -> str:
    if "sigil_root" in manifest:
        raise ValueError("forge_manifest must not contain sigil_root")
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def write_manifest(path: Any, manifest: dict[str, Any]) -> str:
    p = Path(path)
    p.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_digest(manifest)


def write_private_manifest(path: Any, manifest: dict[str, Any]) -> str:
    """Write the private method manifest owner-only (0600); return its digest."""
    from sigil_forge.paths import write_private_text

    write_private_text(
        Path(path), json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    return manifest_digest(manifest)


# ------------------------------------------------------------------ checking


def _read_json(path: Path) -> Any:
    """Bounded read of a regular file as JSON; no symlinks, FIFOs or devices."""
    data = read_regular(path, MAX_MANIFEST_BYTES)

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        # A repeated key keeps only its last value once parsed, so the bytes
        # could carry something the digest never sees.
        obj = dict(pairs)
        if len(obj) != len(pairs):
            raise ValueError("duplicate key")
        return obj

    return json.loads(data.decode("utf-8"), object_pairs_hook=no_duplicates)


def check_run_root(path: Path | str) -> dict[str, Any]:
    """Check a run's public root, and the manifests beside it, without secrets.

    ``path`` is a run folder or its ``artifact-root.json``. With only the
    public files (root and schema 2 forge manifest) this recomputes the Merkle
    root from the listed leaves and the forge manifest's digest, and confirms
    the manifest names the same digest and commitment as the leaves. The
    private method manifest is checked too when it is present.

    ``manifest_public_shape`` says the forge manifest has exactly the public
    shape (see ``public_shape_problems``). That is a check of form. It shows a
    manifest was not altered to carry free text; it cannot show that whoever
    wrote it put nothing private into a well-formed identifier.
    """
    p = Path(path)
    run = p if p.is_dir() else p.parent
    out: dict[str, Any] = {
        "ok": False,
        "run_dir": str(run),
        "sigil_root": None,
        "manifest_schema": None,
        "manifest_public_shape": None,
        "checked": [],
        "not_checked": [],
        "detail": "",
    }
    if not p.is_dir() and p.name != ROOT_NAME:
        out["detail"] = f"give a run folder or its {ROOT_NAME}"
        return out
    try:
        problems = _check_run_root(run, out)
    except (OSError, UnicodeDecodeError) as exc:
        problems = [f"cannot read run files: {type(exc).__name__}"]
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        problems = [f"malformed run files: {type(exc).__name__}"]
    out["detail"] = "; ".join(problems) or "ok"
    out["ok"] = not problems
    return out


def _check_run_root(run: Path, out: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    root = _read_json(run / ROOT_NAME)
    if not isinstance(root, dict) or set(root) != ROOT_KEYS:
        raise ValueError("unexpected root fields")
    listed = root["leaves"]
    if not isinstance(listed, list) or not listed:
        raise ValueError("no leaves")
    leaves: dict[str, str] = {}
    for leaf in listed:
        if not isinstance(leaf, dict) or set(leaf) != {"type", "value"}:
            raise ValueError("bad leaf")
        kind, value = leaf["type"], leaf["value"]
        if kind not in LEAF_TYPES or kind in leaves:
            raise ValueError("unknown or repeated leaf type")
        if not isinstance(value, str) or not _HEX64.fullmatch(value):
            raise ValueError("leaf is not a digest")
        leaves[kind] = value
    claimed = root["sigil_root"]
    if not isinstance(claimed, str) or not _HEX64.fullmatch(claimed):
        raise ValueError("sigil_root is not a digest")
    out["sigil_root"] = claimed
    for required in ("forge_manifest_digest", "method_manifest_digest", "intent_digest", "intent_commitment"):
        if required not in leaves:
            problems.append(f"root has no {required} leaf")
    if merkle_root(sorted(leaves.items())) != claimed:
        problems.append("sigil_root does not match its leaves")
    else:
        out["checked"].append("sigil_root recomputed from leaves")

    legacy = False
    manifest_path = run / PUBLIC_NAME
    if manifest_path.exists() or manifest_path.is_symlink():
        manifest = _read_json(manifest_path)
        if not isinstance(manifest, dict):
            raise ValueError("manifest is not an object")
        schema = manifest.get("schema_version")
        out["manifest_schema"] = schema if isinstance(schema, str) else None
        if manifest_digest(manifest) != leaves.get("forge_manifest_digest"):
            problems.append("forge-manifest.json does not match its leaf")
        else:
            out["checked"].append("forge_manifest_digest")
        for key in ("intent_digest", "intent_commitment"):
            if manifest.get(key) != leaves.get(key):
                problems.append(f"forge-manifest.json {key} differs from the leaf")
        if isinstance(schema, str) and _SCHEMA_PUBLIC.fullmatch(schema):
            if manifest.get("method_manifest_digest") != leaves.get("method_manifest_digest"):
                problems.append("forge-manifest.json names a different method manifest")
            shape = public_shape_problems(manifest)
            out["manifest_public_shape"] = not shape
            problems += [f"forge-manifest.json: {why}" for why in shape]
        elif isinstance(schema, str) and _SCHEMA_LEGACY.fullmatch(schema):
            # Before the split: this file holds the method detail. Private.
            legacy = True
            out["manifest_public_shape"] = False
        else:
            out["manifest_public_shape"] = False
            problems.append("forge-manifest.json has an unknown schema_version")
    else:
        out["not_checked"].append("forge_manifest_digest (forge-manifest.json not present)")

    method_path = run / METHOD_NAME
    if method_path.exists() or method_path.is_symlink():
        method = _read_json(method_path)
        if not isinstance(method, dict):
            raise ValueError("method manifest is not an object")
        if manifest_digest(method) != leaves.get("method_manifest_digest"):
            problems.append("method-manifest.json does not match its leaf")
        else:
            out["checked"].append("method_manifest_digest")
    elif legacy:
        out["not_checked"].append("method_manifest_digest (same file as the schema 1 manifest)")
    else:
        out["not_checked"].append("method_manifest_digest (private file not present)")

    # The glyph leaf is the digest of glyph.svg before the root was written
    # into its metadata, so it cannot be recomputed from the finished file.
    out["not_checked"].append("canonical_glyph_digest (taken before the root was written into the glyph)")
    return problems
