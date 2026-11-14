"""Wallpaper vault — encrypted product payload for the end-image carrier.

Product thesis (v0.13): the **wallpaper PNG** is the deliverable. Corpus methods
still forge geometry; intent, method provenance, digests, and packet surfaces
are sealed into the image (AES-GCM + LSB), not left as the public handoff.

Public header (SF12) keeps intent_digest + sigil_root for verify without
disclosing intent. Private vault needs passphrase.
"""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from typing import Any

from sigil_forge.crypto_payload import open_intent, seal_intent
from sigil_forge.safe_io import MAX_PNG_FILE_BYTES, read_regular
from sigil_forge.stego_png import (
    DIGEST_LEN,
    embed_lsb_rgb,
    extract_lsb,
    inflate_bounded,
    read_rgb_png,
)

SF12_MAGIC = b"SF12"
SF12_VERSION = 1
SF12_FLAG_DIGEST = 1 << 0
SF12_FLAG_ROOT = 1 << 1
SF12_FLAG_VAULT = 1 << 2
# fixed header before sealed: magic4 + ver1 + flags1 + digest32 + root32 + sealed_len4
SF12_HEADER_LEN = 4 + 1 + 1 + 32 + 32 + 4
# A carrier image is untrusted input. extract_payload_from_png caps the
# compressed payload at 512 kB; cap what it may inflate to as well.
SF12_MAX_SEALED_JSON = 8 * 1024 * 1024


def _hex32(h: str, *, name: str = "digest") -> bytes:
    clean = (h or "").strip().lower()
    if len(clean) != 64 or any(c not in "0123456789abcdef" for c in clean):
        raise ValueError(f"{name} must be 64 hex chars")
    raw = bytes.fromhex(clean)
    if len(raw) != DIGEST_LEN:
        raise ValueError(f"{name} length mismatch")
    return raw


def build_vault_document(
    *,
    packet: dict[str, Any],
    intent: str | None = None,
    wallpaper_spec: dict[str, Any] | None = None,
    wallpaper_spec_digest: str | None = None,
    skill_version: str | None = None,
) -> dict[str, Any]:
    """Assemble private vault JSON (to be sealed). No secrets beyond intent/nonce."""
    # Prefer explicit intent; else packet fields when present (may be omitted if sealed)
    raw_intent = intent
    if not raw_intent:
        raw_intent = packet.get("normalized_intent") or packet.get("intent")
    normalized = packet.get("normalized_intent")
    if not normalized and raw_intent:
        from sigil_forge.normalize import normalize_intent

        normalized = normalize_intent(str(raw_intent))

    pub_commit = packet.get("intent_commitment")
    if isinstance(pub_commit, dict):
        commit_public = {
            "scheme": pub_commit.get("scheme"),
            "value": pub_commit.get("value") or pub_commit.get("commitment"),
            "domain": pub_commit.get("domain"),
        }
    else:
        commit_public = None

    # Compact packet: drop bulky paths that are run-local
    packet_pub = {
        k: packet.get(k)
        for k in (
            "schema_version",
            "mode",
            "intent_digest",
            "intent_commitment",
            "intent_commitment_zk",
            "sigil_root",
            "compatibility",
            "methods",
            "channels",
            "ontology",
            "crypto",
            "framing_notes",
            "proof",
            "verify",
        )
        if k in packet
    }

    vault: dict[str, Any] = {
        "schema": "sigil-forge-wallpaper-vault/1",
        "product": "wallpaper",
        "skill_version": skill_version,
        "intent": raw_intent,
        "normalized_intent": normalized,
        "intent_digest": packet.get("intent_digest"),
        "intent_commitment": commit_public,
        "intent_commitment_zk": packet.get("intent_commitment_zk"),
        "sigil_root": packet.get("sigil_root"),
        "methods": packet.get("methods"),
        "channels": packet.get("channels"),
        "ontology": packet.get("ontology"),
        "forge_packet": packet_pub,
        "wallpaper_spec_digest": wallpaper_spec_digest,
    }
    if wallpaper_spec is not None:
        # Presentation only — no need for full artifact paths in vault
        vault["wallpaper"] = {
            "surface": (wallpaper_spec.get("canvas") or {}).get("surface")
            or (wallpaper_spec.get("presentation") or {}).get("surface"),
            "mode": (wallpaper_spec.get("presentation") or {}).get("mode"),
            "symbolic_theme": (wallpaper_spec.get("presentation") or {}).get(
                "symbolic_theme"
            ),
            "schema_version": wallpaper_spec.get("schema_version"),
        }
    # Drop nulls for compactness
    return {k: v for k, v in vault.items() if v is not None}


def seal_vault(
    vault: dict[str, Any],
    passphrase: str,
    *,
    kdf: str | None = "auto",
) -> dict[str, Any]:
    """AES-GCM seal vault JSON (reuses crypto_payload path)."""
    pt = json.dumps(vault, sort_keys=True, separators=(",", ":"))
    return seal_intent(pt, passphrase, kdf=kdf)


def open_vault_blob(sealed: dict[str, Any], passphrase: str) -> dict[str, Any]:
    pt = open_intent(sealed, passphrase)
    data = json.loads(pt)
    if not isinstance(data, dict):
        raise ValueError("vault plaintext is not an object")
    return data


def pack_sf12(
    *,
    intent_digest: str,
    sigil_root: str | None,
    sealed_blob: dict[str, Any],
) -> bytes:
    """Pack SF12: public digests + zlib(json sealed AES blob) + CRC."""
    d = _hex32(intent_digest, name="intent_digest")
    if sigil_root:
        r = _hex32(sigil_root, name="sigil_root")
        flags = SF12_FLAG_DIGEST | SF12_FLAG_ROOT | SF12_FLAG_VAULT
    else:
        r = b"\x00" * DIGEST_LEN
        flags = SF12_FLAG_DIGEST | SF12_FLAG_VAULT
    sealed_json = json.dumps(sealed_blob, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    sealed_z = zlib.compress(sealed_json, 9)
    body = (
        SF12_MAGIC
        + bytes([SF12_VERSION, flags])
        + d
        + r
        + struct.pack(">I", len(sealed_z))
        + sealed_z
    )
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack(">I", crc)


def unpack_sf12(payload: bytes) -> dict[str, Any]:
    if len(payload) < SF12_HEADER_LEN + 4:
        raise ValueError("SF12 payload too short")
    if payload[:4] != SF12_MAGIC:
        raise ValueError(f"not SF12 magic: {payload[:4]!r}")
    ver = payload[4]
    flags = payload[5]
    if ver != SF12_VERSION:
        raise ValueError(f"unsupported SF12 version {ver}")
    digest = payload[6:38]
    root = payload[38:70]
    (sealed_len,) = struct.unpack(">I", payload[70:74])
    need = SF12_HEADER_LEN + sealed_len + 4
    if len(payload) < need:
        raise ValueError(f"SF12 truncated: need {need}, have {len(payload)}")
    sealed_z = payload[74 : 74 + sealed_len]
    (crc_got,) = struct.unpack(">I", payload[74 + sealed_len : need])
    body = payload[: 74 + sealed_len]
    crc_exp = zlib.crc32(body) & 0xFFFFFFFF
    if crc_got != crc_exp:
        raise ValueError("SF12 CRC mismatch")
    sealed_json = inflate_bounded(sealed_z, SF12_MAX_SEALED_JSON)
    sealed_blob = json.loads(sealed_json.decode("utf-8"))
    return {
        "format": "SF12",
        "format_version": ver,
        "flags": flags,
        "intent_digest": digest.hex() if flags & SF12_FLAG_DIGEST else None,
        "sigil_root": (
            root.hex()
            if (flags & SF12_FLAG_ROOT) and root != b"\x00" * DIGEST_LEN
            else None
        ),
        "sealed_blob": sealed_blob,
        "has_vault": bool(flags & SF12_FLAG_VAULT),
    }


def probe_png_public(data: bytes, *, max_bytes: int = 512_000) -> dict[str, Any]:
    """Public header of whatever payload a PNG carries: SF12, SF11 or SF1.

    Returns ``{format, intent_digest, sigil_root, has_vault}``. Nothing is
    decrypted and no passphrase is needed. For SF12 the whole payload is read
    and its CRC checked, so a damaged vault is reported, not half-read. Raises
    ValueError when the image carries none of the three formats.

    ``verify`` and ``inspect`` both use this, so they cannot disagree about
    which formats exist.
    """
    from sigil_forge.stego_envelope import unpack_envelope

    head = extract_lsb(data, min(SF12_HEADER_LEN, max_bytes))
    magic = head[:4]
    if magic == SF12_MAGIC:
        (sealed_len,) = struct.unpack(">I", head[70:74])
        total = SF12_HEADER_LEN + sealed_len + 4
        if total > max_bytes:
            raise ValueError(f"SF12 payload too large: {total}")
        got = unpack_sf12(extract_lsb(data, total))
        return {
            "format": "SF12",
            "intent_digest": got["intent_digest"],
            "sigil_root": got["sigil_root"],
            "has_vault": got["has_vault"],
        }
    if magic == b"SF11":
        env = unpack_envelope(extract_lsb(data, 4 + 1 + 1 + 32 + 32 + 4))
    elif magic == b"SF1\x00":
        env = unpack_envelope(extract_lsb(data, 4 + DIGEST_LEN))
    else:
        raise ValueError("bad PNG LSB magic")
    return {
        "format": env.get("format"),
        "intent_digest": env.get("intent_digest"),
        "sigil_root": env.get("sigil_root"),
        "has_vault": False,
    }


def extract_payload_from_png(png_path: Path | str, *, max_bytes: int = 512_000) -> bytes:
    """Extract LSB payload by probing magic + length headers."""
    data = read_regular(png_path, MAX_PNG_FILE_BYTES)
    # Read enough for SF12 header
    head = extract_lsb(data, min(SF12_HEADER_LEN, max_bytes))
    if head[:4] == SF12_MAGIC:
        (sealed_len,) = struct.unpack(">I", head[70:74])
        total = SF12_HEADER_LEN + sealed_len + 4
        if total > max_bytes:
            raise ValueError(f"SF12 payload too large: {total}")
        return extract_lsb(data, total)
    if head[:4] == b"SF11":
        return extract_lsb(data, 4 + 1 + 1 + 32 + 32 + 4)
    if head[:4] == b"SF1\x00":
        # SF1 fixed min 36; may have sealed len
        base = extract_lsb(data, 4 + DIGEST_LEN + 4)
        if len(base) >= 4 + DIGEST_LEN + 4:
            (n,) = struct.unpack(">I", base[4 + DIGEST_LEN : 4 + DIGEST_LEN + 4])
            if n > 0 and n < max_bytes:
                return extract_lsb(data, 4 + DIGEST_LEN + 4 + n)
        return extract_lsb(data, 4 + DIGEST_LEN)
    raise ValueError(f"unknown stego magic {head[:4]!r}")


def embed_vault_png(
    png_path: Path | str,
    *,
    intent_digest: str,
    sigil_root: str | None,
    sealed_blob: dict[str, Any],
) -> str:
    """Rewrite PNG with SF12 vault LSB payload; return new file sha256 hex."""
    path = Path(png_path)
    payload = pack_sf12(
        intent_digest=intent_digest,
        sigil_root=sigil_root,
        sealed_blob=sealed_blob,
    )
    w, h, rgb = read_rgb_png(read_regular(path, MAX_PNG_FILE_BYTES))
    out = embed_lsb_rgb(w, h, rgb, payload)
    path.write_bytes(out)
    from sigil_forge.wallpaper.seed import file_sha256

    return file_sha256(str(path))


def open_wallpaper_vault(
    png_path: Path | str,
    passphrase: str,
) -> dict[str, Any]:
    """Extract SF12 and decrypt vault; returns vault + public header fields."""
    raw = extract_payload_from_png(png_path)
    env = unpack_sf12(raw)
    vault = open_vault_blob(env["sealed_blob"], passphrase)
    return {
        "ok": True,
        "format": "SF12",
        "intent_digest": env.get("intent_digest"),
        "sigil_root": env.get("sigil_root"),
        "vault": vault,
        # Convenience mirrors
        "intent": vault.get("intent"),
        "normalized_intent": vault.get("normalized_intent"),
    }


def png_capacity_bytes(png_path: Path | str) -> int:
    w, h, rgb = read_rgb_png(read_regular(png_path, MAX_PNG_FILE_BYTES))
    return len(rgb) // 8  # 1 bit per sample
