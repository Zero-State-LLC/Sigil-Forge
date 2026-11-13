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
import os
import re
import stat
from pathlib import Path
from typing import Any

from sigil_forge.artifact_root import merkle_root

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
_PUBLIC_VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:+\-/ ]{0,79}")
_HEX64 = re.compile(r"[0-9a-f]{64}")


def public_methods(methods: dict[str, Any] | None) -> dict[str, Any]:
    """Identifier-only view of a methods block (see PUBLIC_METHOD_KEYS)."""

    def reduce(node: Any) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in sorted(node):
            value = node[key]
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
    for name in sorted(methods or {}):
        if name == "sigil_root" or not isinstance(methods[name], dict):
            continue
        result[name] = reduce(methods[name])
    return result


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
        "channels": [{"id": c.get("id"), "status": c.get("status")} for c in (channels or [])],
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
    if path.is_symlink():
        raise OSError("symlink")
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_MANIFEST_BYTES:
            raise OSError("not a regular file within the size limit")
        data = b""
        while len(data) <= MAX_MANIFEST_BYTES:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                break
            data += chunk
    finally:
        os.close(fd)
    if len(data) > MAX_MANIFEST_BYTES:
        raise OSError("larger than the limit")
    return json.loads(data.decode("utf-8"))


def check_run_root(path: Path | str) -> dict[str, Any]:
    """Check a run's public root, and the manifests beside it, without secrets.

    ``path`` is a run folder or its ``artifact-root.json``. With only the
    public files (root and schema 2 forge manifest) this recomputes the Merkle
    root from the listed leaves and the forge manifest's digest, and confirms
    the manifest names the same digest and commitment as the leaves. The
    private method manifest is checked too when it is present.
    """
    p = Path(path)
    run = p if p.is_dir() else p.parent
    out: dict[str, Any] = {
        "ok": False,
        "run_dir": str(run),
        "sigil_root": None,
        "manifest_schema": None,
        "manifest_is_public": None,
        "checked": [],
        "not_checked": [],
        "detail": "",
    }
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
    listed = root["leaves"]
    if not isinstance(listed, list) or not listed:
        raise ValueError("no leaves")
    leaves: dict[str, str] = {}
    for leaf in listed:
        kind, value = leaf["type"], leaf["value"]
        if not isinstance(kind, str) or not isinstance(value, str) or kind in leaves:
            raise ValueError("bad leaf")
        leaves[kind] = value
    claimed = root["sigil_root"]
    out["sigil_root"] = claimed if isinstance(claimed, str) else None
    if merkle_root(sorted(leaves.items())) != claimed:
        problems.append("sigil_root does not match its leaves")
    else:
        out["checked"].append("sigil_root recomputed from leaves")

    manifest_path = run / PUBLIC_NAME
    if manifest_path.exists() or manifest_path.is_symlink():
        manifest = _read_json(manifest_path)
        if not isinstance(manifest, dict):
            raise ValueError("manifest is not an object")
        schema = str(manifest.get("schema_version") or "")
        out["manifest_schema"] = schema
        public = schema.split(".", 1)[0] == PUBLIC_SCHEMA_VERSION.split(".", 1)[0]
        if manifest_digest(manifest) != leaves.get("forge_manifest_digest"):
            problems.append("forge-manifest.json does not match its leaf")
        else:
            out["checked"].append("forge_manifest_digest")
        for key in ("intent_digest", "intent_commitment"):
            if key in leaves and manifest.get(key) != leaves[key]:
                problems.append(f"forge-manifest.json {key} differs from the leaf")
        if public:
            if manifest.get("method_manifest_digest") != leaves.get("method_manifest_digest"):
                problems.append("forge-manifest.json names a different method manifest")
            if manifest.get("methods") != public_methods(manifest.get("methods")) or any(
                set(c) - {"id", "status"} for c in manifest.get("channels") or [] if isinstance(c, dict)
            ):
                problems.append("forge-manifest.json holds more than identifiers")
                public = False
        out["manifest_is_public"] = public
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
    elif out["manifest_schema"] and not out["manifest_is_public"]:
        out["not_checked"].append("method_manifest_digest (same file as the schema 1 manifest)")
    else:
        out["not_checked"].append("method_manifest_digest (private file not present)")

    for kind in sorted(set(leaves) - {"forge_manifest_digest", "method_manifest_digest"}):
        if not _HEX64.fullmatch(leaves[kind]):
            problems.append(f"leaf {kind} is not a digest")
    # The glyph leaf is the digest of glyph.svg before the root was written
    # into its metadata, so it cannot be recomputed from the finished file.
    out["not_checked"].append("canonical_glyph_digest (taken before the root was written into the glyph)")
    return problems
