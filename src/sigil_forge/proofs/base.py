"""Proof provider interface."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ProofResult:
    provider: str
    proof_kind: str
    status: str  # generated | skipped | failed | verified
    public_inputs: dict[str, Any] = field(default_factory=dict)
    proof_path: str | None = None
    verification_key_digest: str | None = None
    circuit_version: str | None = None
    detail: str = ""
    intent_disclosed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@runtime_checkable
class ProofProvider(Protocol):
    name: str

    def available(self) -> bool: ...

    def prove(
        self,
        witness: dict[str, Any],
        public_inputs: dict[str, Any],
        *,
        out_dir: Any,
    ) -> ProofResult: ...

    def verify(
        self,
        proof_path: Any,
        public_inputs: dict[str, Any],
        *,
        extra: dict[str, Any] | None = None,
    ) -> bool: ...
