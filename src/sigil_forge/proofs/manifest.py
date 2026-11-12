"""Proof manifest read/write."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from proofs.base import ProofResult


def write_proof_manifest(
    out_dir: Path | str,
    result: ProofResult,
    *,
    extra: dict[str, Any] | None = None,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "proof-manifest.json"
    body: dict[str, Any] = {
        "schema_version": "1.0.0",
        "provider": result.provider,
        "proof_kind": result.proof_kind,
        "circuit_version": result.circuit_version,
        "public_inputs": result.public_inputs,
        "proof_file": result.proof_path,
        "verification_key_digest": result.verification_key_digest,
        "status": result.status,
        "detail": result.detail,
        "intent_disclosed": result.intent_disclosed,
    }
    if extra:
        body.update(extra)
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_proof_manifest(run_dir: Path | str) -> dict[str, Any] | None:
    p = Path(run_dir) / "proofs" / "proof-manifest.json"
    if not p.is_file():
        # also allow run_dir itself if already proofs/
        p2 = Path(run_dir) / "proof-manifest.json"
        p = p2 if p2.is_file() else p
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def file_digest(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
