"""Verify proof artifacts for a forge run directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from proofs.manifest import load_proof_manifest
from proofs.registry import get_provider


def verify_proof_run(
    run_dir: Path | str,
    *,
    passphrase: str | None = None,
) -> dict[str, Any]:
    """Machine-readable proof verification for a run directory."""
    run = Path(run_dir)
    out: dict[str, Any] = {
        "verified": False,
        "proof_kind": None,
        "intent_disclosed": False,
        "intent_commitment": None,
        "intent_commitment_zk": None,
        "sigil_root": None,
        "forge_version": None,
        "provider": None,
        "detail": "",
    }
    if not run.is_dir():
        out["detail"] = "run_dir not found"
        return out

    packet_path = run / "forge-packet.json"
    packet: dict[str, Any] = {}
    if packet_path.is_file():
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        ic = packet.get("intent_commitment") or {}
        out["intent_commitment"] = (
            ic.get("value") if isinstance(ic, dict) else None
        )
        out["sigil_root"] = packet.get("sigil_root")
        # version from bindings if present
        out["forge_version"] = (
            (packet.get("artifacts") or {}).get("forge_version")
            or packet.get("schema_version")
        )

    manifest = load_proof_manifest(run)
    if not manifest:
        out["detail"] = "no proofs/proof-manifest.json"
        return out

    out["provider"] = manifest.get("provider")
    out["proof_kind"] = manifest.get("proof_kind")
    pub = dict(manifest.get("public_inputs") or {})
    out["intent_commitment"] = pub.get("intent_commitment") or out["intent_commitment"]
    out["intent_commitment_zk"] = pub.get("intent_commitment_zk")
    out["sigil_root"] = pub.get("sigil_root") or out["sigil_root"]
    out["forge_version"] = pub.get("forge_version") or out["forge_version"]

    if manifest.get("status") == "failed" and not manifest.get("local_attestation"):
        out["detail"] = manifest.get("detail") or "proof generation failed"
        return out

    extra: dict[str, Any] = {}
    if passphrase:
        extra["passphrase"] = passphrase
        cap_path = run / "intent-capsule.json"
        if cap_path.is_file():
            extra["capsule"] = json.loads(cap_path.read_text(encoding="utf-8"))

    # Prefer Noir when generated; fall back to local capsule attestation
    attempts: list[tuple[str, Any, Any]] = []
    provider_name = manifest.get("provider") or "none"
    proof_file = manifest.get("proof_file")
    proof_path = Path(proof_file) if proof_file else None
    if proof_path and not proof_path.is_file():
        alt = run / "proofs" / Path(str(proof_file)).name
        proof_path = alt if alt.is_file() else proof_path

    if manifest.get("status") == "generated" and provider_name not in ("none",):
        attempts.append((str(provider_name), proof_path, pub))

    # local attestation always preferred for offline operator verify with passphrase
    local_att = run / "proofs" / "knowledge-attestation.json"
    local_extra_pub = pub
    if manifest.get("local_attestation"):
        la = manifest["local_attestation"]
        if isinstance(la, dict) and la.get("public_inputs"):
            local_extra_pub = dict(la["public_inputs"])
    if local_att.is_file():
        attempts.append(("local_capsule", local_att, local_extra_pub))

    if not attempts and manifest.get("status") == "skipped":
        out["detail"] = manifest.get("detail") or "proof skipped"
        return out

    last_err = ""
    for pname, ppath, pinputs in attempts:
        try:
            provider = get_provider(pname)
        except ValueError as exc:
            last_err = str(exc)
            continue
        try:
            ok = provider.verify(ppath, pinputs, extra=extra or None)
        except Exception as exc:  # noqa: BLE001
            last_err = f"verify error ({pname}): {exc}"
            continue
        if ok:
            out["verified"] = True
            out["provider"] = pname
            out["proof_kind"] = (
                "zk_knowledge" if pname == "noir" else "knowledge_of_intent"
            )
            out["intent_disclosed"] = False
            out["detail"] = "ok"
            return out
        last_err = f"{pname} verification failed"

    out["detail"] = last_err or "verification failed"
    return out
