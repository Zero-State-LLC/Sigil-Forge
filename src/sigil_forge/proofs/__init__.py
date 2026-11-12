"""Proof-of-intent providers (optional ZK; core forge never requires them)."""

from sigil_forge.proofs.base import ProofResult, ProofProvider
from sigil_forge.proofs.registry import get_provider, list_providers

__all__ = [
    "ProofResult",
    "ProofProvider",
    "get_provider",
    "list_providers",
]
