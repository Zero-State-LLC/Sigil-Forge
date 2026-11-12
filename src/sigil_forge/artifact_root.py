"""Binary Merkle tree for sigil_root (Proof of Intent).

Leaves are type-tagged and sorted lexicographically by leaf_type.
Odd nodes pad by duplicating the last hash (Bitcoin-style).

Never include sigil_root itself or run-receipt as a leaf.
"""

from __future__ import annotations

from typing import Any

from crypto_domains import MERKLE_LEAF_V1, MERKLE_NODE_V1, domain_sha256


def _as_bytes(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        return value
    s = (value or "").strip().lower()
    if len(s) == 64 and all(c in "0123456789abcdef" for c in s):
        return bytes.fromhex(s)
    return s.encode("utf-8")


def leaf_hash(leaf_type: str, value: str | bytes) -> bytes:
    if not leaf_type or not isinstance(leaf_type, str):
        raise ValueError("leaf_type required")
    return domain_sha256(MERKLE_LEAF_V1, leaf_type.encode("utf-8"), _as_bytes(value))


def node_hash(left: bytes, right: bytes) -> bytes:
    if len(left) != 32 or len(right) != 32:
        raise ValueError("node children must be 32-byte hashes")
    return domain_sha256(MERKLE_NODE_V1, left, right)


def merkle_root(leaves: list[tuple[str, str | bytes]]) -> str:
    """Compute hex root from (leaf_type, value) pairs. Empty → error."""
    if not leaves:
        raise ValueError("merkle_root requires at least one leaf")
    # Sort by type for determinism; reject duplicate types
    sorted_leaves = sorted(leaves, key=lambda x: x[0])
    types = [t for t, _ in sorted_leaves]
    if len(types) != len(set(types)):
        raise ValueError(f"duplicate leaf types: {types}")
    level = [leaf_hash(t, v) for t, v in sorted_leaves]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        nxt: list[bytes] = []
        for i in range(0, len(level), 2):
            nxt.append(node_hash(level[i], level[i + 1]))
        level = nxt
    return level[0].hex()


def build_sigil_root(leaf_map: dict[str, str | bytes | None]) -> dict[str, Any]:
    """Build root from optional leaf map (None values omitted)."""
    leaves: list[tuple[str, str | bytes]] = []
    for k in sorted(leaf_map.keys()):
        v = leaf_map[k]
        if v is None or v == "":
            continue
        leaves.append((k, v))
    if not leaves:
        raise ValueError("no leaves for sigil_root")
    root = merkle_root(leaves)
    return {
        "schema_version": "1.0.0",
        "domain": "SIGIL-FORGE/ARTIFACT-ROOT/V1",
        "sigil_root": root,
        "leaves": [
            {"type": t, "value": v if isinstance(v, str) else v.hex()}
            for t, v in sorted(leaves, key=lambda x: x[0])
        ],
    }
