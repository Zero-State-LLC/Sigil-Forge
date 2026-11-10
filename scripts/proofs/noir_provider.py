"""Optional Noir proof provider (nargo). Core forge does not require Noir.

When nargo is available, proves knowledge of (intent, nonce) such that
SHA-256(nonce || padded_intent) == public intent_commitment_zk.

Circuit lives under zk/noir/intent_commitment/.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from paths import skill_root
from proofs.base import ProofResult
from proofs.zk_commit import pad_intent, zk_commit


class NoirProvider:
    name = "noir"
    circuit_version = "1"

    def available(self) -> bool:
        if shutil.which("nargo") is None:
            return False
        return self._circuit_dir().is_dir()

    def _circuit_dir(self) -> Path:
        return skill_root() / "zk" / "noir" / "intent_commitment"

    @staticmethod
    def _circuit_proof(circuit: Path) -> Path | None:
        """The proof file nargo last wrote for this circuit, if any."""
        named = circuit / "proofs" / "intent_commitment.proof"
        if named.is_file():
            return named
        candidates = sorted((circuit / "proofs").glob("*.proof"))
        return candidates[0] if candidates else None

    def prove(
        self,
        witness: dict[str, Any],
        public_inputs: dict[str, Any],
        *,
        out_dir: Path | str,
    ) -> ProofResult:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        if not self.available():
            return ProofResult(
                provider=self.name,
                proof_kind="zk_knowledge",
                status="skipped",
                public_inputs=dict(public_inputs),
                detail="noir_unavailable",
                circuit_version=self.circuit_version,
            )
        normalized = witness.get("normalized_intent") or ""
        nonce = witness.get("nonce")
        if not isinstance(nonce, (bytes, bytearray)) or not normalized:
            return ProofResult(
                provider=self.name,
                proof_kind="zk_knowledge",
                status="failed",
                public_inputs=dict(public_inputs),
                detail="witness missing normalized_intent or nonce bytes",
                circuit_version=self.circuit_version,
            )
        try:
            c_zk = zk_commit(normalized, bytes(nonce))
            padded, intent_len = pad_intent(normalized)
        except ValueError as exc:
            return ProofResult(
                provider=self.name,
                proof_kind="zk_knowledge",
                status="failed",
                public_inputs=dict(public_inputs),
                detail=str(exc),
                circuit_version=self.circuit_version,
            )

        # Write Prover.toml-style witness for the circuit
        circuit = self._circuit_dir()
        prover_toml = circuit / "Prover.toml"
        # Noir expects arrays of u8 as lists of numbers
        intent_arr = ", ".join(str(b) for b in padded)
        nonce_arr = ", ".join(str(b) for b in nonce)
        expected = bytes.fromhex(str(c_zk["value"]))
        expected_arr = ", ".join(str(b) for b in expected)
        # The witness is the plaintext intent and the commitment nonce. Keep it
        # owner-only while nargo needs it and never leave it in the skill tree.
        fd = os.open(prover_toml, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(
                f'intent_len = "{intent_len}"\n'
                f"intent_bytes = [{intent_arr}]\n"
                f"nonce = [{nonce_arr}]\n"
                f"expected_commitment = [{expected_arr}]\n"
            )
        try:
            # Compile + prove (nargo versions vary; try common commands)
            compile = subprocess.run(
                ["nargo", "compile"],
                cwd=str(circuit),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if compile.returncode != 0:
                return ProofResult(
                    provider=self.name,
                    proof_kind="zk_knowledge",
                    status="failed",
                    public_inputs=dict(public_inputs),
                    detail=f"nargo compile failed: {(compile.stderr or compile.stdout)[:400]}",
                    circuit_version=self.circuit_version,
                )
            prove = subprocess.run(
                ["nargo", "prove"],
                cwd=str(circuit),
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if prove.returncode != 0:
                return ProofResult(
                    provider=self.name,
                    proof_kind="zk_knowledge",
                    status="failed",
                    public_inputs=dict(public_inputs),
                    detail=f"nargo prove failed: {(prove.stderr or prove.stdout)[:400]}",
                    circuit_version=self.circuit_version,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ProofResult(
                provider=self.name,
                proof_kind="zk_knowledge",
                status="failed",
                public_inputs=dict(public_inputs),
                detail=f"nargo execution error: {exc}",
                circuit_version=self.circuit_version,
            )
        finally:
            prover_toml.unlink(missing_ok=True)

        # Copy proof artifact if present
        proof_src = self._circuit_proof(circuit)
        proof_dst = out / "intent-proof.bin"
        if proof_src is not None:
            proof_dst.write_bytes(proof_src.read_bytes())
        else:
            # Still record prover inputs for debugging when proof file missing
            proof_dst.write_text(
                json.dumps(
                    {
                        "note": "nargo prove succeeded but proof file path unknown",
                        "public": public_inputs,
                    }
                ),
                encoding="utf-8",
            )

        pi = dict(public_inputs)
        pi["intent_commitment_zk"] = c_zk["value"]
        pi["intent_len"] = intent_len
        return ProofResult(
            provider=self.name,
            proof_kind="zk_knowledge",
            status="generated",
            public_inputs=pi,
            proof_path=str(proof_dst),
            verification_key_digest=None,
            circuit_version=self.circuit_version,
            detail="noir proof generated",
            intent_disclosed=False,
        )

    def verify(
        self,
        proof_path: Any,
        public_inputs: dict[str, Any],
        *,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        if not self.available():
            return False
        circuit = self._circuit_dir()
        # ``nargo verify`` checks whatever proof currently sits in the circuit
        # directory. Only trust its answer for the artifact we were handed.
        staged = self._circuit_proof(circuit)
        try:
            if (
                proof_path is None
                or staged is None
                or Path(proof_path).read_bytes() != staged.read_bytes()
            ):
                return False
        except OSError:
            return False
        try:
            proc = subprocess.run(
                ["nargo", "verify"],
                cwd=str(circuit),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            return proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False
