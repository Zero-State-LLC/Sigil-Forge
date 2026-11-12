"""zkVM / RISC Zero adapter stub (v0.13-exp path).

Core forge never requires a zkVM. When tools are absent, status=skipped.
Full guest program for restricted forge_core is future work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from proofs.base import ProofResult


class Risc0Provider:
    name = "risc0"
    circuit_version = "0-exp"

    def available(self) -> bool:
        # Do not hard-require cargo/risc0 tooling offline
        try:
            import shutil

            return shutil.which("cargo") is not None and (
                (Path.home() / ".cargo" / "bin" / "r0vm").is_file()
                or shutil.which("r0vm") is not None
            )
        except Exception:
            return False

    def prove(
        self,
        witness: dict[str, Any],
        public_inputs: dict[str, Any],
        *,
        out_dir: Path | str,
    ) -> ProofResult:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        if not self.available():
            return ProofResult(
                provider=self.name,
                proof_kind="zk_forge",
                status="skipped",
                public_inputs=dict(public_inputs),
                detail="risc0_unavailable",
                circuit_version=self.circuit_version,
            )
        # Toolchain present but guest not implemented yet
        return ProofResult(
            provider=self.name,
            proof_kind="zk_forge",
            status="skipped",
            public_inputs=dict(public_inputs),
            detail="risc0_guest_not_implemented",
            circuit_version=self.circuit_version,
        )

    def verify(
        self,
        proof_path: Any,
        public_inputs: dict[str, Any],
        *,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        return False
