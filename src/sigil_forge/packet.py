"""Assemble forge-packet JSON (+ optional Markdown summary)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from policy_lint import assert_no_efficacy

SCHEMA_VERSION = "1.2"

_REQUIRED_KEYS = (
    "schema_version",
    "mode",
    "intent_digest",
    "channels",
    "methods",
    "artifacts",
    "crypto",
    "verify",
    "framing_notes",
)

_CREATIVE_FRAMING = (
    "Creative / focus tool: externalize and compress intent as a durable symbol. "
    "Methods are historical craft, symbolic encoding, and data embedding—"
    "not claims that symbols compel outcomes."
)

_PRACTICE_FRAMING = (
    "Practice profile: same construction as creative mode. Optional personal notes "
    "(gaze, place, discard) are operator-owned. No efficacy claims; methods are craft "
    "history and multi-channel encoding only."
)


def framing_notes(mode: str) -> str:
    if mode == "practice":
        return _PRACTICE_FRAMING
    return _CREATIVE_FRAMING


def structural_check(packet: dict[str, Any]) -> list[str]:
    """Return list of missing/invalid required keys (empty if ok)."""
    errors: list[str] = []
    for key in _REQUIRED_KEYS:
        if key not in packet:
            errors.append(f"missing required key: {key}")
    if "channels" in packet:
        if not isinstance(packet["channels"], list):
            errors.append("channels must be a list")
        else:
            for i, ch in enumerate(packet["channels"]):
                if not isinstance(ch, dict):
                    errors.append(f"channels[{i}] must be object")
                    continue
                for k in ("id", "status", "detail"):
                    if k not in ch:
                        errors.append(f"channels[{i}] missing {k}")
                if ch.get("status") not in (None, "applied", "skipped"):
                    errors.append(f"channels[{i}] bad status: {ch.get('status')!r}")
    if "mode" in packet and packet["mode"] not in ("creative", "practice"):
        errors.append(f"bad mode: {packet['mode']!r}")
    return errors


def validate_packet(packet: dict[str, Any], schema_path: Path | None = None) -> None:
    """Validate packet; raise ValueError on structural or schema failure."""
    errors = structural_check(packet)
    if errors:
        raise ValueError("forge-packet structural check failed: " + "; ".join(errors))
    if schema_path is None:
        return
    if not schema_path.is_file():
        return
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=packet, schema=schema)


def build_packet(
    *,
    mode: str,
    intent_digest: str,
    channels: list[dict[str, Any]],
    methods: dict[str, Any],
    artifacts: dict[str, Any],
    crypto: dict[str, Any],
    verify_cmd: str,
    normalized_intent: str | None = None,
    sealed_blob: dict[str, Any] | None = None,
    interop: dict[str, Any] | None = None,
    include_normalized: bool = True,
    ontology: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a forge-packet dict matching design §9 + ontology/provenance."""
    notes = framing_notes(mode)
    assert_no_efficacy(notes, field="framing_notes")
    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "intent_digest": intent_digest.lower(),
        "channels": list(channels),
        "methods": methods,
        "artifacts": artifacts,
        "crypto": crypto,
        "verify": verify_cmd,
        "framing_notes": notes,
        "interop": interop if interop is not None else {},
        "ontology": ontology if ontology is not None else {},
        "provenance": provenance if provenance is not None else {},
    }
    if include_normalized and normalized_intent is not None:
        packet["normalized_intent"] = normalized_intent
    if sealed_blob is not None:
        packet["sealed_intent"] = sealed_blob
    return packet


def to_markdown(packet: dict[str, Any]) -> str:
    """Human-readable summary (no efficacy claims)."""
    lines: list[str] = [
        "# Forge packet",
        "",
        f"- **schema_version:** {packet.get('schema_version', '')}",
        f"- **mode:** {packet.get('mode', '')}",
        f"- **intent_digest:** `{packet.get('intent_digest', '')}`",
        "",
        "## Methods",
        "",
    ]
    methods = packet.get("methods") or {}
    spare = methods.get("spare") or {}
    kamea = methods.get("kamea") or {}
    lines.append(f"- Spare: {spare.get('reduction', 'n/a')}")
    if spare.get("letter_count") is not None:
        lines.append(f"  - letter_count: {spare['letter_count']}")
    lines.append(
        f"- Kamea: planet={kamea.get('planet', 'n/a')}, "
        f"order={kamea.get('order', 'n/a')}, cipher={kamea.get('cipher', 'n/a')}"
    )
    lines.extend(["", "## Channels", ""])
    for ch in packet.get("channels") or []:
        lines.append(
            f"- `{ch.get('id')}`: **{ch.get('status')}** — {ch.get('detail', '')}"
        )
    lines.extend(["", "## Artifacts", ""])
    arts = packet.get("artifacts") or {}
    for key, path in arts.items():
        if path:
            lines.append(f"- **{key}:** `{path}`")
    crypto = packet.get("crypto") or {}
    lines.extend(
        [
            "",
            "## Crypto",
            "",
            f"- algorithm: {crypto.get('algorithm', 'none')}",
            f"- key_policy: {crypto.get('key_policy', 'none')}",
            f"- ciphertext_present: {crypto.get('ciphertext_present', False)}",
            "",
            "## Verify",
            "",
            f"```\n{packet.get('verify', '')}\n```",
            "",
            "## Framing",
            "",
            packet.get("framing_notes", ""),
            "",
        ]
    )
    if packet.get("normalized_intent"):
        lines.extend(
            [
                "## Normalized intent (local packet only)",
                "",
                packet["normalized_intent"],
                "",
            ]
        )
    elif packet.get("sealed_intent"):
        lines.extend(
            [
                "## Intent",
                "",
                "Sealed (passphrase required). Plaintext omitted from packet.",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def write_packet_files(packet: dict[str, Any], run_dir: Path) -> dict[str, str]:
    """Write forge-packet.json and forge-packet.md; return paths."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "forge-packet.json"
    md_path = run_dir / "forge-packet.md"
    json_path.write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(to_markdown(packet), encoding="utf-8")
    return {"packet_json": str(json_path), "packet_md": str(md_path)}
