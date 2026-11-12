"""Offline knowledge attestation via capsule open (NOT zero-knowledge to third parties).

Prover with passphrase opens the capsule at prove-time and writes a public
attestation that commitment and zk_commitment match the sealed witness.
Third parties verify by re-opening the capsule with the passphrase OR by
checking a Noir proof when available.

Honest labeling: proof_kind = knowledge_of_intent, provider = local_capsule.
True ZK uses NoirProvider (provider = noir).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from commitment import verify_commitment, nonce_from_b64
from intent_capsule import open_capsule
from proofs.base import ProofResult
from proofs.zk_commit import verify_zk_commit


class LocalCapsuleProvider:
    name = "local_capsule"

    def available(self) -> bool:
        return True

    def prove(
        self,
        witness: dict[str, Any],
        public_inputs: dict[str, Any],
        *,
        out_dir: Path | str,
    ) -> ProofResult:
        """witness must include capsule dict + passphrase."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        capsule = witness.get("capsule")
        passphrase = witness.get("passphrase")
        if not capsule or not passphrase:
            return ProofResult(
                provider=self.name,
                proof_kind="knowledge_of_intent",
                status="failed",
                public_inputs=dict(public_inputs),
                detail="capsule and passphrase required for local knowledge prove",
            )
        try:
            opened = open_capsule(capsule, passphrase)
        except Exception as exc:  # noqa: BLE001
            return ProofResult(
                provider=self.name,
                proof_kind="knowledge_of_intent",
                status="failed",
                public_inputs=dict(public_inputs),
                detail=f"capsule_open_failed: {exc}",
            )
        nonce = nonce_from_b64(opened["commitment_nonce_b64"])
        norm = opened["normalized_intent"]
        c_pub = public_inputs.get("intent_commitment") or ""
        if not verify_commitment(norm, nonce, str(c_pub)):
            return ProofResult(
                provider=self.name,
                proof_kind="knowledge_of_intent",
                status="failed",
                public_inputs=dict(public_inputs),
                detail="commitment mismatch after capsule open",
            )
        c_zk = public_inputs.get("intent_commitment_zk") or ""
        if c_zk and not verify_zk_commit(norm, nonce, str(c_zk)):
            return ProofResult(
                provider=self.name,
                proof_kind="knowledge_of_intent",
                status="failed",
                public_inputs=dict(public_inputs),
                detail="zk_commitment mismatch after capsule open",
            )
        att = {
            "schema_version": "1.0.0",
            "provider": self.name,
            "proof_kind": "knowledge_of_intent",
            "statement": (
                "Prover opened intent-capsule and recomputed commitments. "
                "This is not zero-knowledge to parties without the passphrase."
            ),
            "public_inputs": public_inputs,
            "ok": True,
        }
        proof_path = out / "knowledge-attestation.json"
        proof_path.write_text(
            json.dumps(att, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return ProofResult(
            provider=self.name,
            proof_kind="knowledge_of_intent",
            status="generated",
            public_inputs=dict(public_inputs),
            proof_path=str(proof_path),
            circuit_version="capsule-open-v1",
            detail="local capsule knowledge attestation (not ZK)",
            intent_disclosed=False,
        )

    def verify(
        self,
        proof_path: Any,
        public_inputs: dict[str, Any],
        *,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        """Verify by re-opening capsule with passphrase from extra."""
        extra = extra or {}
        passphrase = extra.get("passphrase")
        capsule = extra.get("capsule")
        if not passphrase or not capsule:
            # Without passphrase, only check attestation file structure
            try:
                att = json.loads(Path(proof_path).read_text(encoding="utf-8"))
            except Exception:
                return False
            return bool(att.get("ok")) and att.get("provider") == self.name
        try:
            opened = open_capsule(capsule, passphrase)
            nonce = nonce_from_b64(opened["commitment_nonce_b64"])
            norm = opened["normalized_intent"]
            c_pub = public_inputs.get("intent_commitment") or ""
            if not verify_commitment(norm, nonce, str(c_pub)):
                return False
            c_zk = public_inputs.get("intent_commitment_zk") or ""
            if c_zk and not verify_zk_commit(norm, nonce, str(c_zk)):
                return False
            return True
        except Exception:
            return False
