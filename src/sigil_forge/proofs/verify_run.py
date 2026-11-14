"""Verify proof artifacts for a forge run directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sigil_forge.safe_io import MAX_JSON_BYTES, read_text
from sigil_forge.proofs.manifest import load_proof_manifest
from sigil_forge.proofs.registry import get_provider


def _run_binding_error(
    public_inputs: dict[str, Any], packet_commitment: Any, packet_root: Any
) -> str:
    """Why these proof inputs do not belong to this run; empty when they do."""
    if not packet_commitment or not packet_root:
        return "run has no forge-packet.json commitment to check the proof against"
    if public_inputs.get("intent_commitment") != packet_commitment:
        return "proof files name a different commitment than this run's packet"
    if public_inputs.get("sigil_root") not in (None, "", packet_root):
        return "proof files name a different sigil_root than this run's packet"
    return ""


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
        "attestation_present": False,
        "detail": "",
    }
    if not run.is_dir():
        out["detail"] = "run_dir not found"
        return out

    packet_path = run / "forge-packet.json"
    packet: dict[str, Any] = {}
    if packet_path.is_file():
        try:
            packet = json.loads(read_text(packet_path, MAX_JSON_BYTES))
        except (OSError, ValueError) as exc:
            out["detail"] = f"cannot read forge-packet.json: {type(exc).__name__}"
            return out
        if not isinstance(packet, dict):
            out["detail"] = "forge-packet.json is not an object"
            return out
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

    try:
        manifest = load_proof_manifest(run)
    except (OSError, ValueError) as exc:
        out["detail"] = f"cannot read proofs/proof-manifest.json: {type(exc).__name__}"
        return out
    if not manifest:
        out["detail"] = "no proofs/proof-manifest.json"
        return out
    if not isinstance(manifest, dict) or not isinstance(manifest.get("public_inputs") or {}, dict):
        out["detail"] = "proofs/proof-manifest.json is malformed"
        return out

    out["provider"] = manifest.get("provider")
    out["proof_kind"] = manifest.get("proof_kind")
    pub = dict(manifest.get("public_inputs") or {})
    # What this run's own packet records. The proof files are only evidence
    # for this run if they name the same commitment and root; otherwise they
    # are someone else's proof sitting in this folder.
    packet_commitment = out["intent_commitment"]
    packet_root = out["sigil_root"]
    out["intent_commitment_zk"] = pub.get("intent_commitment_zk")
    out["forge_version"] = pub.get("forge_version") or out["forge_version"]

    if manifest.get("status") == "failed" and not manifest.get("local_attestation"):
        out["detail"] = manifest.get("detail") or "proof generation failed"
        return out

    extra: dict[str, Any] = {}
    if passphrase:
        extra["passphrase"] = passphrase
        cap_path = run / "intent-capsule.json"
        if cap_path.is_file():
            try:
                capsule_doc = json.loads(read_text(cap_path, MAX_JSON_BYTES))
            except (OSError, ValueError):
                capsule_doc = None
            if isinstance(capsule_doc, dict):
                extra["capsule"] = capsule_doc

    # Prefer Noir when generated; fall back to local capsule attestation
    attempts: list[tuple[str, Any, Any]] = []
    provider_name = manifest.get("provider") or "none"
    # Only ever the file of that name inside this run's proofs folder: a
    # manifest must not be able to point the verifier at a path elsewhere.
    proof_file = manifest.get("proof_file")
    proof_path = (
        run / "proofs" / Path(str(proof_file)).name
        if isinstance(proof_file, str) and proof_file
        else None
    )

    bind_error = ""
    if provider_name == "noir":
        # A Noir proof only says "someone knows a preimage of this commitment".
        # It speaks for this run only if that commitment and length are the
        # ones the run's packet records; a manifest edited to carry another
        # run's proof and commitment must not verify.
        recorded = packet.get("intent_commitment_zk")
        recorded = recorded if isinstance(recorded, dict) else {}
        if (
            not recorded.get("value")
            or pub.get("intent_commitment_zk") != recorded.get("value")
            or pub.get("intent_len") != recorded.get("intent_len")
        ):
            bind_error = "noir proof is not bound to this run's packet commitment"
    # Every provider's proof must name this run's commitment and root. Without
    # this, a capsule and proofs copied in from another run would verify here.
    if not bind_error:
        bind_error = _run_binding_error(pub, packet_commitment, packet_root)
    if manifest.get("status") == "generated" and provider_name not in ("none",) and not bind_error:
        attempts.append((str(provider_name), proof_path, pub))

    # local attestation always preferred for offline operator verify with passphrase
    local_att = run / "proofs" / "knowledge-attestation.json"
    local_extra_pub = pub
    if manifest.get("local_attestation"):
        la = manifest["local_attestation"]
        if isinstance(la, dict) and la.get("public_inputs"):
            local_extra_pub = dict(la["public_inputs"])
    # The local attestation is verified by opening the capsule, which needs the
    # passphrase. Without one its presence is reported but proves nothing.
    out["attestation_present"] = local_att.is_file()
    needs_passphrase = local_att.is_file() and not passphrase
    local_bind_error = ""
    if local_att.is_file() and passphrase:
        # Opening the capsule shows it matches the commitment in the proof
        # files. That commitment must also be this run's.
        local_bind_error = _run_binding_error(
            local_extra_pub, packet_commitment, packet_root
        ) or _run_binding_error(pub, packet_commitment, packet_root)
        if not local_bind_error and ("local_capsule", local_att, local_extra_pub) not in attempts:
            attempts.append(("local_capsule", local_att, local_extra_pub))

    if not attempts and manifest.get("status") == "skipped":
        out["detail"] = manifest.get("detail") or "proof skipped"
        if needs_passphrase:
            out["detail"] += "; passphrase required to verify the local attestation"
        return out

    last_err = "; ".join(dict.fromkeys(e for e in (bind_error, local_bind_error) if e))
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

    if needs_passphrase:
        hint = "passphrase required to verify the local attestation"
        last_err = f"{last_err}; {hint}" if last_err else hint
    out["detail"] = last_err or "verification failed"
    return out
