"""Run receipts and proposal-only learning ledger.

Receipts: append-only JSONL of construct outcomes (integrity hash optional).
Receipts are PRIVATE operator records, not public media: ``methods`` carries
intent-derived data (reduced letters, the Hebrew transliteration, kamea and
rose-cross paths) from which the intent can largely be read back, and
``intent_digest`` is an unsalted hash a short intent can be guessed against.
New receipt files are therefore created owner-only (0600).
Learning ledger: operator-submitted observations with canon_status PROPOSED only —
never auto-promoted to skill corpus.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sigil_forge.paths import (
    default_state_root,
    ensure_private_dir,
    skill_root,
    write_private_text,
)

RECEIPT_SCHEMA_VERSION = "1.0"
LEDGER_SCHEMA_VERSION = "1.0"
CANON_PROPOSAL_SCHEMA_VERSION = "1.0.0"
DEFAULT_LEDGER_NAME = "learning-ledger.jsonl"
DEFAULT_RECEIPTS_NAME = "run-receipts.jsonl"
DEFAULT_CANON_PROPOSALS_NAME = "canon-proposals.jsonl"
PROMOTE_CONFIRM = "PROMOTE"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_state_file(name: str) -> Path:
    """Default location of a ledger/receipt file.

    New default: ``<state root>/ledger/<name>``. Backward compatibility, with no
    data migration: if that file does not exist but the legacy file
    ``<install root>/out/sigil-forge/<name>`` does, the legacy path is returned
    so existing ledgers keep being read and appended to.
    """
    new = default_state_root() / "ledger" / name
    if not new.exists():
        legacy = skill_root() / "out" / "sigil-forge" / name
        if legacy.exists():
            return legacy
    return new


def _make_parent(path: Path) -> None:
    """Create ``path``'s parent: 0700 for new dirs under the state root, else plain."""
    parent = path.parent
    try:
        under_state = parent.resolve().is_relative_to(default_state_root())
    except (OSError, ValueError):
        under_state = False
    if under_state:
        ensure_private_dir(parent)
    else:
        parent.mkdir(parents=True, exist_ok=True)


def default_ledger_path() -> Path:
    env = os.environ.get("SIGIL_FORGE_LEDGER")
    if env:
        return Path(env).expanduser()
    return _default_state_file(DEFAULT_LEDGER_NAME)


def default_receipts_path() -> Path:
    env = os.environ.get("SIGIL_FORGE_RECEIPTS")
    if env:
        return Path(env).expanduser()
    return _default_state_file(DEFAULT_RECEIPTS_NAME)


def default_canon_proposals_path() -> Path:
    env = os.environ.get("SIGIL_FORGE_CANON_PROPOSALS")
    if env:
        return Path(env).expanduser()
    return _default_state_file(DEFAULT_CANON_PROPOSALS_NAME)


def build_run_receipt(
    packet: dict[str, Any],
    *,
    skill_version: str,
    verify_ok: bool | None = None,
) -> dict[str, Any]:
    """Build a receipt dict from a forge packet.

    The receipt holds no plaintext intent and no commitment nonce, but it is
    not digests-only: ``methods`` is copied from the packet and is derived from
    the intent. Treat the result as private (see the module docstring).
    """
    channels = packet.get("channels") or []
    applied = [c.get("id") for c in channels if c.get("status") == "applied"]
    skipped = [
        {"id": c.get("id"), "detail": c.get("detail")}
        for c in channels
        if c.get("status") == "skipped"
    ]
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "kind": "sigil_forge_run_receipt",
        "ts": _utc_now(),
        "skill_version": skill_version,
        "run_id": (packet.get("artifacts") or {}).get("run_id"),
        "mode": packet.get("mode"),
        "intent_digest": packet.get("intent_digest"),
        "channels_applied": applied,
        "channels_skipped": skipped,
        "methods": packet.get("methods") or {},
        "crypto_key_policy": (packet.get("crypto") or {}).get("key_policy"),
        "artifacts": {
            k: (packet.get("artifacts") or {}).get(k)
            for k in ("svg", "png", "packet_json", "polish_prompt_path")
        },
        "verify_ok": verify_ok,
        "canon_status": "OBSERVATION",
    }
    # Integrity over stable serialization without local path noise
    core = {
        "intent_digest": receipt["intent_digest"],
        "channels_applied": receipt["channels_applied"],
        "mode": receipt["mode"],
        "run_id": receipt["run_id"],
        "skill_version": skill_version,
    }
    blob = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt["receipt_hash"] = hashlib.sha256(blob).hexdigest()
    return receipt


def write_receipt_file(receipt: dict[str, Any], path: Path) -> Path:
    """Write one receipt, owner-only (0600): receipts are private records."""
    _make_parent(path)
    write_private_text(path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return path


def append_receipt_log(receipt: dict[str, Any], log_path: Path | None = None) -> Path:
    path = log_path or default_receipts_path()
    _make_parent(path)
    # A log this call creates is owner-only; an existing log keeps its mode.
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, sort_keys=True) + "\n")
    return path


def build_ledger_entry(
    *,
    class_name: str,
    summary: str,
    run_id: str | None = None,
    intent_digest: str | None = None,
    channels: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "kind": "sigil_forge_learning_entry",
        "ts": _utc_now(),
        "unix": int(time.time()),
        "class": class_name,
        "summary": summary,
        "run_id": run_id,
        "intent_digest": intent_digest,
        "channels": channels or [],
        "canon_status": "PROPOSED",  # never auto-canon
        "extra": extra or {},
    }
    return entry


def append_ledger(
    entry: dict[str, Any],
    ledger_path: Path | None = None,
) -> Path:
    if entry.get("canon_status") != "PROPOSED":
        raise ValueError("learning ledger entries must be canon_status=PROPOSED")
    path = ledger_path or default_ledger_path()
    _make_parent(path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return path


def read_ledger(ledger_path: Path | None = None, limit: int = 50) -> list[dict[str, Any]]:
    path = ledger_path or default_ledger_path()
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    # limit <= 0 used to mean "everything" (or "all but the first"): slicing
    # with a non-positive number. It now means none.
    for line in lines[-limit:] if limit > 0 else []:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            out.append(entry)
    return out


def list_learning(
    ledger_path: Path | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List recent learning-ledger observations (always PROPOSED in the log)."""
    return read_ledger(ledger_path, limit=limit)


def export_proposed(
    limit: int = 50,
    ledger_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return PROPOSED entries from the learning ledger (observation log only)."""
    return [
        e
        for e in read_ledger(ledger_path, limit=limit)
        if e.get("canon_status") == "PROPOSED"
    ]


def append_learning_entry(
    *,
    class_: str | None = None,
    class_name: str | None = None,
    summary: str,
    run_id: str | None = None,
    intent_digest: str | None = None,
    channels: list[str] | None = None,
    extra: dict[str, Any] | None = None,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    """Build + append a PROPOSED learning entry; returns the entry dict."""
    name = class_name if class_name is not None else class_
    if not name:
        raise ValueError("class_ or class_name is required")
    entry = build_ledger_entry(
        class_name=name,
        summary=summary,
        run_id=run_id,
        intent_digest=intent_digest,
        channels=channels,
        extra=extra,
    )
    append_ledger(entry, ledger_path)
    return entry


def promote_to_canon_proposal(
    entry: dict[str, Any],
    *,
    confirm: str,
    out_path: Path | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Write an operator-local HUMAN_PROMOTED proposal; never mutates the ledger or references/.

    Requires confirm == 'PROMOTE' (exact). Learning ledger lines stay PROPOSED.
    """
    if confirm != PROMOTE_CONFIRM:
        raise ValueError("human confirm required: pass confirm='PROMOTE'")
    if entry.get("canon_status") != "PROPOSED":
        raise ValueError("only PROPOSED entries can be promoted")

    if out_path is None:
        if out_dir is not None:
            out_path = Path(out_dir) / DEFAULT_CANON_PROPOSALS_NAME
        else:
            out_path = default_canon_proposals_path()
    else:
        out_path = Path(out_path)

    proposal: dict[str, Any] = {
        "schema_version": CANON_PROPOSAL_SCHEMA_VERSION,
        "kind": "sigil_forge_canon_proposal",
        "ts": _utc_now(),
        "canon_status": "HUMAN_PROMOTED",
        "source_canon_status": "PROPOSED",
        "entry": entry,
        "note": "Operator-local proposal only; does not mutate skill references/",
    }
    _make_parent(out_path)
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(proposal, sort_keys=True) + "\n")
    return proposal


def promote_entry(
    entry_id_or_index: int | str,
    *,
    confirm: str,
    ledger_path: Path | None = None,
    out_path: Path | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Promote a PROPOSED ledger row by index (into export_proposed window) or run_id."""
    entries = export_proposed(limit=limit, ledger_path=ledger_path)
    if not entries:
        raise ValueError("no PROPOSED ledger entries to promote")

    entry: dict[str, Any] | None = None
    if isinstance(entry_id_or_index, int) or (
        isinstance(entry_id_or_index, str) and entry_id_or_index.lstrip("-").isdigit()
    ):
        idx = int(entry_id_or_index)
        if idx < 0 or idx >= len(entries):
            raise ValueError(
                f"index {idx} out of range (0..{len(entries) - 1}, limit={limit})"
            )
        entry = entries[idx]
    else:
        key = str(entry_id_or_index)
        for e in entries:
            if e.get("run_id") == key:
                entry = e
                break
        if entry is None:
            raise ValueError(f"no PROPOSED entry with run_id={key!r} in window")

    return promote_to_canon_proposal(entry, confirm=confirm, out_path=out_path)
