"""Inspect public carriers for digest / sigil_root (never print plaintext intent)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from stego_envelope import unpack_envelope
from stego_png import extract_lsb
from stego_svg import extract as extract_svg


def inspect_path(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    out: dict[str, Any] = {
        "ok": False,
        "artifact": str(p),
        "carrier": None,
        "format_version": None,
        "intent_digest": None,
        "sigil_root": None,
        "associated_proof": None,
    }
    if not p.is_file():
        out["detail"] = "file not found"
        return out

    suffix = p.suffix.lower()
    try:
        if suffix == ".svg" or _looks_svg(p):
            out["carrier"] = "SVG"
            text = p.read_text(encoding="utf-8")
            got = extract_svg(text)
            out["intent_digest"] = got.get("intent_digest")
            out["sigil_root"] = got.get("sigil_root")
            out["format_version"] = got.get("version") or (2 if got.get("sigil_root") else 1)
            out["channels_detected"] = got.get("channels_detected")
            out["ok"] = bool(out["intent_digest"])
            return out

        if suffix == ".png" or _looks_png(p):
            out["carrier"] = "PNG"
            data = p.read_bytes()
            peek = extract_lsb(data, 4)
            if peek == b"SF11":
                raw = extract_lsb(data, 4 + 1 + 1 + 32 + 32 + 4)
            else:
                raw = extract_lsb(data, 4 + 32)
            env = unpack_envelope(raw)
            out["format_version"] = env.get("format")
            out["intent_digest"] = env.get("intent_digest")
            out["sigil_root"] = env.get("sigil_root")
            out["ok"] = bool(out["intent_digest"] or out["sigil_root"])
            return out

        # run directory?
        if p.is_dir() or (p / "forge-packet.json").is_file():
            run = p if p.is_dir() else p.parent
            packet_path = run / "forge-packet.json"
            if packet_path.is_file():
                import json

                packet = json.loads(packet_path.read_text(encoding="utf-8"))
                out["carrier"] = "run"
                out["intent_digest"] = packet.get("intent_digest")
                ic = packet.get("intent_commitment") or {}
                out["intent_commitment"] = (
                    ic.get("value") if isinstance(ic, dict) else None
                )
                out["sigil_root"] = packet.get("sigil_root")
                out["proof"] = packet.get("proof")
                out["ok"] = True
                # optional proof file
                proofs = run / "proofs"
                if proofs.is_dir():
                    out["associated_proof"] = str(proofs)
                return out

        out["detail"] = f"unsupported artifact type {suffix!r}"
        return out
    except Exception as exc:  # noqa: BLE001
        out["detail"] = str(exc)
        return out


def _looks_png(p: Path) -> bool:
    try:
        return p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


def _looks_svg(p: Path) -> bool:
    try:
        head = p.read_text(encoding="utf-8", errors="ignore")[:200].lower()
        return "<svg" in head
    except OSError:
        return False
