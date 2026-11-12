"""Proof-of-intent providers (optional ZK; core forge never requires them)."""

from proofs.base import ProofResult, ProofProvider
from proofs.registry import get_provider, list_providers

__all__ = [
    "ProofResult",
    "ProofProvider",
    "get_provider",
    "list_providers",
]
