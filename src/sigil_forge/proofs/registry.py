"""Proof provider registry."""

from __future__ import annotations

from typing import Any

from proofs.local_knowledge import LocalCapsuleProvider
from proofs.noir_provider import NoirProvider
from proofs.none_provider import NoneProvider
from proofs.risc0_provider import Risc0Provider

_PROVIDERS = {
    "none": NoneProvider,
    "local_capsule": LocalCapsuleProvider,
    "noir": NoirProvider,
    "risc0": Risc0Provider,
}


def get_provider(name: str) -> Any:
    key = (name or "none").strip().lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        raise ValueError(f"unknown proof provider {name!r}; known: {list(_PROVIDERS)}")
    return cls()


def list_providers() -> list[dict[str, Any]]:
    out = []
    for name, cls in _PROVIDERS.items():
        inst = cls()
        out.append({"name": name, "available": bool(inst.available())})
    return out
