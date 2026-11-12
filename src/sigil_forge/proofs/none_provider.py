"""No-op proof provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from proofs.base import ProofResult


class NoneProvider:
    name = "none"

    def available(self) -> bool:
        return True

    def prove(
        self,
        witness: dict[str, Any],
        public_inputs: dict[str, Any],
        *,
        out_dir: Path | str,
    ) -> ProofResult:
        return ProofResult(
            provider=self.name,
            proof_kind="none",
            status="skipped",
            public_inputs=dict(public_inputs),
            detail="proof mode none",
        )

    def verify(
        self,
        proof_path: Any,
        public_inputs: dict[str, Any],
        *,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        return False
