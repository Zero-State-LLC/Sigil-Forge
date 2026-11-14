"""Verify a forged artifact recovers the embedded intent digest."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sigil_forge.safe_io import (
    MAX_PNG_FILE_BYTES,
    MAX_SVG_BYTES,
    read_head,
    read_regular,
    read_text,
)
from sigil_forge.stego_svg import expected_epsilon_bits
from sigil_forge.stego_svg import extract as extract_svg

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _normalize_digest(value: Any) -> str | None:
    """Return lowercased digest string or None if missing/invalid type."""
    if not isinstance(value, str) or not value:
        return None
    return value.strip().lower()


def _digest_format_ok(digest: str | None) -> bool:
    return bool(digest) and _DIGEST_RE.fullmatch(digest or "") is not None


def _cross_check_epsilon(digest: str, epsilon_bits: list[int] | None) -> str | None:
    """When path_epsilon bits are present, require parity matches digest stream.

    Returns error detail, or None when ok / nothing to check.
    """
    if not epsilon_bits:
        return None
    expected = expected_epsilon_bits(digest, len(epsilon_bits))
    if not expected:
        return "path_epsilon bits present but digest has no hex bits"
    mismatches = 0
    for i, (got, exp) in enumerate(zip(epsilon_bits, expected)):
        if int(got) != int(exp):
            mismatches += 1
            if mismatches == 1:
                first = f"path_epsilon bit[{i}]={got} != digest stream bit {exp}"
    if mismatches:
        return f"{first} ({mismatches} of {len(epsilon_bits)} bits mismatched)"
    return None


def _cross_check_metrics(digest: str, metrics: list[str]) -> str | None:
    """When data-sf-metric attrs exist, require digest nibble prefixes.

    stego_svg writes digest[:8] then digest[8:16] on monogram/kamea groups.
    Returns error detail, or None when ok / nothing to check.
    """
    if not metrics:
        return None
    expected_slots = (digest[:8], digest[8:16])
    allowed = {s for s in expected_slots if s}
    for i, raw in enumerate(metrics):
        m = (raw or "").strip().lower()
        if not m or not re.fullmatch(r"[0-9a-f]+", m):
            return f"data-sf-metric[{i}] is not hex: {raw!r}"
        # Exact 8-nibble values must equal first-8 or next-8 of digest.
        if len(m) == 8:
            if m not in allowed:
                return (
                    f"data-sf-metric[{i}]={m!r} is not a digest nibble prefix "
                    f"(first 8={digest[:8]!r}, next 8={digest[8:16]!r})"
                )
            # Prefer document order: slot i matches expected_slots[i] when both full.
            if i < len(expected_slots) and len(metrics) >= 2 and m != expected_slots[i]:
                return (
                    f"data-sf-metric[{i}]={m!r} does not match digest "
                    f"nibble prefix {expected_slots[i]!r}"
                )
        else:
            # Shorter residual must still be a prefix of first-8 or next-8.
            if not any(slot.startswith(m) for slot in expected_slots):
                return (
                    f"data-sf-metric[{i}]={m!r} is not a prefix of digest "
                    f"nibble slots {digest[:8]!r}/{digest[8:16]!r}"
                )
    return None


def _fail(
    *,
    path: Path,
    kind: str,
    detail: str,
    digest: str | None = None,
    channels: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ok": False,
        "intent_digest": digest,
        "channels_checked": list(channels or []),
        "artifact": str(path),
        "kind": kind,
        "detail": detail,
    }
    out.update(extra)
    return out


def _apply_expected(
    result: dict[str, Any], expected_digest: str | None
) -> dict[str, Any]:
    """Compare recovered digest to operator-provided expected digest."""
    if expected_digest is None:
        return result
    exp = _normalize_digest(expected_digest)
    result["expected_digest"] = exp
    if not _digest_format_ok(exp):
        result["ok"] = False
        result["detail"] = (
            f"invalid --expected-digest (need ^[0-9a-f]{{64}}$), "
            f"got {expected_digest!r}"
        )
        return result
    if not result.get("ok"):
        return result
    got = result.get("intent_digest")
    if got != exp:
        result["ok"] = False
        result["detail"] = (
            f"digest mismatch: recovered {got!r} != expected {exp!r}"
        )
    return result


def _verify_svg(path: Path, expected_digest: str | None = None) -> dict[str, Any]:
    try:
        text = read_text(path, MAX_SVG_BYTES)
        got = extract_svg(text)
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        # Too large, not text, a link or pipe, or numbers no glyph contains.
        return _apply_expected(
            _fail(
                path=path,
                kind="svg",
                detail=f"svg read failed: {type(exc).__name__}",
                channels=[],
            ),
            expected_digest,
        )
    digest = _normalize_digest(got.get("intent_digest"))
    sigil_root = _normalize_digest(got.get("sigil_root"))
    channels = list(got.get("channels_detected") or [])
    metrics = list(got.get("metrics") or [])
    epsilon_bits = list(got.get("epsilon_bits") or [])

    if not digest:
        return _apply_expected(
            _fail(
                path=path,
                kind="svg",
                detail="no intent_digest recovered from SVG stego",
                channels=channels,
            ),
            expected_digest,
        )

    if not _digest_format_ok(digest):
        return _apply_expected(
            _fail(
                path=path,
                kind="svg",
                detail=(
                    f"intent_digest failed format ^[0-9a-f]{{64}}$, got {digest!r}"
                ),
                digest=digest,
                channels=channels,
            ),
            expected_digest,
        )

    metric_err = _cross_check_metrics(digest, metrics)
    if metric_err:
        return _apply_expected(
            _fail(
                path=path,
                kind="svg",
                detail=metric_err,
                digest=digest,
                channels=channels,
                metrics=metrics,
            ),
            expected_digest,
        )

    eps_err = _cross_check_epsilon(digest, epsilon_bits)
    if eps_err:
        return _apply_expected(
            _fail(
                path=path,
                kind="svg",
                detail=eps_err,
                digest=digest,
                channels=channels,
                epsilon_bit_count=len(epsilon_bits),
            ),
            expected_digest,
        )

    result: dict[str, Any] = {
        "ok": True,
        "intent_digest": digest,
        "channels_checked": channels,
        "artifact": str(path),
        "kind": "svg",
        "stego_format": "v2" if sigil_root else "v1",
    }
    if sigil_root:
        result["sigil_root"] = sigil_root
    if metrics:
        result["metrics"] = metrics
    if epsilon_bits:
        result["epsilon_bit_count"] = len(epsilon_bits)
    return _apply_expected(result, expected_digest)


def _verify_png(path: Path, expected_digest: str | None = None) -> dict[str, Any]:
    channels: list[str] = []
    try:
        from sigil_forge.wallpaper.vault import probe_png_public

        env = probe_png_public(read_regular(path, MAX_PNG_FILE_BYTES))
        digest_hex = env.get("intent_digest")
        channels.append("png_lsb")
        if env.get("format") == "SF11":
            channels.append("sf11_root")
        elif env.get("format") == "SF12":
            # The vault's public header and CRC were read; nothing was decrypted.
            channels.append("sf12_vault")
        if not _digest_format_ok(digest_hex):
            return _apply_expected(
                _fail(
                    path=path,
                    kind="png",
                    detail=(
                        f"intent_digest failed format ^[0-9a-f]{{64}}$, "
                        f"got {digest_hex!r}"
                    ),
                    digest=digest_hex,
                    channels=channels,
                ),
                expected_digest,
            )
        result: dict[str, Any] = {
            "ok": True,
            "intent_digest": digest_hex,
            "channels_checked": channels,
            "artifact": str(path),
            "kind": "png",
            "stego_format": env.get("format"),
        }
        if env.get("sigil_root"):
            result["sigil_root"] = env["sigil_root"]
        if env.get("has_vault"):
            result["has_vault"] = True
        return _apply_expected(result, expected_digest)
    except ValueError as exc:
        detail = str(exc) if str(exc) == "bad PNG LSB magic" else f"png extract failed: {exc}"
        return _apply_expected(
            _fail(path=path, kind="png", detail=detail, channels=channels),
            expected_digest,
        )
    except Exception as exc:  # noqa: BLE001 — verify reports failure
        return _apply_expected(
            _fail(
                path=path,
                kind="png",
                detail=f"png extract failed: {exc}",
                channels=channels,
            ),
            expected_digest,
        )


def run(
    artifact_path: Path | str,
    expected_digest: str | None = None,
) -> dict[str, Any]:
    """Verify artifact recovers digest.

    Returns ``{ok, intent_digest, channels_checked, ...}``.
    When checks fail, ``ok`` is False and ``detail`` explains why.

    ``expected_digest`` (optional): require recovered digest to equal this
    64-hex string (CLI ``--expected-digest``).
    """
    path = Path(artifact_path)
    if not path.is_file():
        return _apply_expected(
            {
                "ok": False,
                "intent_digest": None,
                "channels_checked": [],
                "artifact": str(path),
                "detail": "file not found",
            },
            expected_digest,
        )
    suffix = path.suffix.lower()
    if suffix == ".svg":
        return _verify_svg(path, expected_digest)
    if suffix == ".png":
        return _verify_png(path, expected_digest)
    # Try SVG text first (some paths lack extension)
    head = read_head(path, 256)  # sniff only; never loads the whole file
    if b"<svg" in head.lower() or b"<?xml" in head:
        return _verify_svg(path, expected_digest)
    if head.startswith(b"\x89PNG"):
        return _verify_png(path, expected_digest)
    return _apply_expected(
        {
            "ok": False,
            "intent_digest": None,
            "channels_checked": [],
            "artifact": str(path),
            "detail": f"unsupported artifact type: {suffix or 'unknown'}",
        },
        expected_digest,
    )
