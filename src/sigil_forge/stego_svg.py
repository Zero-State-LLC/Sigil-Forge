"""SVG steganography: metadata + geometric/structural channels.

Channels (v1):
  - svg_metadata: namespaced metadata/sf:payload with base64 JSON
    {v:1, d:<digest_hex>, m:<method_bitmap>} — never plaintext intent
  - path_epsilon: ±EPS coordinate LSB-analogue from digest bits
  - path_order: manifest binding (monogram group before kamea); order_token
    is derived from digest (not stored as spare/plaintext)
  - metric_quantize: data-sf-metric attributes carry digest nibbles

Public SVG must not contain plaintext intent or spare reduced letters.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any, TypedDict

EPS = 0.001

# Namespaces
SVG_NS = "http://www.w3.org/2000/svg"
SF_NS = "https://sigil-forge.local/ns"

# Method bitmap bits for channels applied in this module
MB_SVG_METADATA = 1 << 0
MB_PATH_EPSILON = 1 << 1
MB_PATH_ORDER = 1 << 2
MB_METRIC_QUANTIZE = 1 << 3

_CHANNEL_BITS = {
    "svg_metadata": MB_SVG_METADATA,
    "path_epsilon": MB_PATH_EPSILON,
    "path_order": MB_PATH_ORDER,
    "metric_quantize": MB_METRIC_QUANTIZE,
}

# Float token in path d / polyline points (sign, int/frac)
_FLOAT_RE = re.compile(r"[-+]?(?:\d+\.\d+|\d+\.|\.\d+|\d+)(?:[eE][-+]?\d+)?")


class ChannelStatus(TypedDict):
    id: str
    status: str  # "applied" | "skipped"
    detail: str


def _status(cid: str, status: str, detail: str) -> ChannelStatus:
    return {"id": cid, "status": status, "detail": detail}


def _digest_bits(digest_hex: str) -> list[int]:
    """Expand hex digest to a list of bits (MSB-first per nibble)."""
    bits: list[int] = []
    h = digest_hex.lower().strip()
    for ch in h:
        try:
            n = int(ch, 16)
        except ValueError:
            continue
        for shift in (3, 2, 1, 0):
            bits.append((n >> shift) & 1)
    return bits


def _order_token(digest_hex: str) -> str:
    """Deterministic order token derived from digest (not stored as spare)."""
    return digest_hex[:16].lower()


def _encode_float_bit(val: float, bit: int) -> float:
    """Quantize to EPS grid with parity = bit (geometric LSB)."""
    q = int(round(val / EPS))
    if bit:
        if q % 2 == 0:
            q += 1
    else:
        if q % 2 != 0:
            q -= 1
    return q * EPS


def _decode_float_bit(val: float) -> int:
    q = int(round(val / EPS))
    return q % 2


def _perturb_float_string(s: str, bit: int) -> str:
    val = float(s)
    new_val = _encode_float_bit(val, bit)
    # Preserve a stable decimal form (avoid scientific notation for stego coords)
    text = f"{new_val:.6f}".rstrip("0").rstrip(".")
    if text in ("", "-", "+"):
        text = "0"
    return text


def _apply_path_epsilon(svg: str, digest_hex: str) -> tuple[str, int]:
    """Perturb floats in points= and d= attributes; return (svg, n_floats)."""
    bits = _digest_bits(digest_hex)
    if not bits:
        return svg, 0
    bit_i = 0
    count = 0

    def repl_attr(match: re.Match[str]) -> str:
        nonlocal bit_i, count
        attr = match.group(1)
        quote = match.group(2)
        body = match.group(3)

        def repl_float(fm: re.Match[str]) -> str:
            nonlocal bit_i, count
            bit = bits[bit_i % len(bits)]
            bit_i += 1
            count += 1
            return _perturb_float_string(fm.group(0), bit)

        new_body = _FLOAT_RE.sub(repl_float, body)
        return f'{attr}={quote}{new_body}{quote}'

    # Only touch geometry-bearing attributes
    pattern = re.compile(
        r'\b(points|d)=([\'"])(.*?)\2',
        flags=re.IGNORECASE | re.DOTALL,
    )
    out = pattern.sub(repl_attr, svg)
    return out, count


def _apply_metric_quantize(svg: str, digest_hex: str) -> tuple[str, int]:
    """Attach data-sf-metric nibble runs to path groups."""
    h = digest_hex.lower().strip()
    # First 8 hex chars on spare-monogram, next 8 on kamea-path
    mono_m = h[:8] if len(h) >= 8 else h
    kamea_m = h[8:16] if len(h) >= 16 else h[8:] if len(h) > 8 else h
    applied = 0

    def inject_group(svg_in: str, group_id: str, metric: str) -> str:
        nonlocal applied
        if not metric:
            return svg_in
        # Match opening <g ... id="group_id" ...> (id anywhere in tag)
        pat = re.compile(
            rf'(<g\b[^>]*\bid=["\']{re.escape(group_id)}["\'][^>]*)(>)',
            flags=re.IGNORECASE,
        )

        def add_attr(m: re.Match[str]) -> str:
            nonlocal applied
            open_tag = m.group(1)
            if "data-sf-metric=" in open_tag:
                open_tag = re.sub(
                    r'\s*data-sf-metric=["\'][^"\']*["\']',
                    "",
                    open_tag,
                )
            applied += 1
            return f'{open_tag} data-sf-metric="{metric}"{m.group(2)}'

        return pat.sub(add_attr, svg_in, count=1)

    out = inject_group(svg, "spare-monogram", mono_m)
    out = inject_group(out, "kamea-path", kamea_m)
    return out, applied


def _path_order_ok(svg: str) -> bool:
    """True when spare-monogram appears before kamea-path (construction order)."""
    i_mono = svg.find('id="spare-monogram"')
    if i_mono < 0:
        i_mono = svg.lower().find('id="spare-monogram"')
    i_kamea = svg.find('id="kamea-path"')
    if i_kamea < 0:
        i_kamea = svg.lower().find('id="kamea-path"')
    if i_mono < 0 or i_kamea < 0:
        return False
    return i_mono < i_kamea


def _insert_metadata(svg: str, payload_b64: str) -> str:
    """Insert <metadata><sf:payload>...</sf:payload></metadata> after <svg ...>."""
    # Ensure xmlns:sf on root
    if "xmlns:sf=" not in svg:
        svg = re.sub(
            r"(<svg\b)",
            rf'\1 xmlns:sf="{SF_NS}"',
            svg,
            count=1,
            flags=re.IGNORECASE,
        )

    meta_block = (
        f"<metadata>\n"
        f"    <sf:payload>{payload_b64}</sf:payload>\n"
        f"  </metadata>\n"
    )

    # Replace existing metadata block if present
    if re.search(r"<metadata[\s>]", svg, flags=re.IGNORECASE):
        svg = re.sub(
            r"<metadata\b[^>]*>.*?</metadata>\s*",
            meta_block,
            svg,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return svg

    # Insert after opening <svg ...>
    m = re.search(r"<svg\b[^>]*>", svg, flags=re.IGNORECASE)
    if not m:
        return meta_block + svg
    insert_at = m.end()
    return svg[:insert_at] + "\n  " + meta_block + svg[insert_at:]


def _build_payload(
    digest_hex: str,
    method_bitmap: int,
    *,
    sigil_root: str | None = None,
) -> str:
    from stego_envelope import svg_metadata_payload

    obj = svg_metadata_payload(
        intent_digest=digest_hex,
        method_bitmap=int(method_bitmap),
        sigil_root=sigil_root,
    )
    raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _parse_payload_b64(b64: str) -> dict[str, Any] | None:
    try:
        raw = base64.b64decode(b64.strip(), validate=False)
        obj = json.loads(raw.decode("utf-8"))
        if not isinstance(obj, dict):
            return None
        return obj
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def embed(
    svg: str,
    digest_hex: str,
    spare_letters: str,
    extras: dict | None = None,
) -> tuple[str, list[ChannelStatus]]:
    """Embed digest into SVG via v1 stego channels.

    spare_letters is accepted for API symmetry with the forge pipeline but is
    intentionally **not** written into the public SVG (privacy lock).
    """
    del spare_letters  # never embed reduced spare string in public SVG
    extras = extras or {}
    channels: list[ChannelStatus] = []
    out = svg
    bitmap = 0

    # Extra method bits from caller (e.g. upstream craft channels) may OR in
    if "method_bitmap" in extras:
        try:
            bitmap |= int(extras["method_bitmap"])
        except (TypeError, ValueError):
            pass

    # --- path_epsilon (geometry) ---
    try:
        out, n_floats = _apply_path_epsilon(out, digest_hex)
        if n_floats > 0:
            bitmap |= MB_PATH_EPSILON
            channels.append(
                _status(
                    "path_epsilon",
                    "applied",
                    f"perturbed {n_floats} floats eps={EPS}",
                )
            )
        else:
            channels.append(
                _status("path_epsilon", "skipped", "no path/polyline floats")
            )
    except Exception as exc:  # noqa: BLE001 — channel isolation
        channels.append(_status("path_epsilon", "skipped", f"error: {exc}"))

    # --- metric_quantize (data attributes) ---
    try:
        out, n_groups = _apply_metric_quantize(out, digest_hex)
        if n_groups > 0:
            bitmap |= MB_METRIC_QUANTIZE
            channels.append(
                _status(
                    "metric_quantize",
                    "applied",
                    f"data-sf-metric on {n_groups} group(s)",
                )
            )
        else:
            channels.append(
                _status("metric_quantize", "skipped", "no path groups found")
            )
    except Exception as exc:  # noqa: BLE001
        channels.append(_status("metric_quantize", "skipped", f"error: {exc}"))

    # --- path_order (manifest binding; monogram before kamea) ---
    token = _order_token(digest_hex)
    if _path_order_ok(out):
        bitmap |= MB_PATH_ORDER
        channels.append(
            _status(
                "path_order",
                "applied",
                f"manifest binding monogram<kamea order_token={token}",
            )
        )
    else:
        channels.append(
            _status(
                "path_order",
                "skipped",
                "expected spare-monogram before kamea-path",
            )
        )

    # --- svg_metadata last so bitmap reflects sibling channels ---
    try:
        bitmap |= MB_SVG_METADATA
        sigil_root = extras.get("sigil_root")
        if isinstance(sigil_root, str) and not sigil_root.strip():
            sigil_root = None
        payload_b64 = _build_payload(digest_hex, bitmap, sigil_root=sigil_root)
        out = _insert_metadata(out, payload_b64)
        ver = 2 if sigil_root else 1
        channels.append(
            _status(
                "svg_metadata",
                "applied",
                f"sf:payload v={ver} m={bitmap}"
                + (f" root={str(sigil_root)[:12]}…" if sigil_root else ""),
            )
        )
    except Exception as exc:  # noqa: BLE001
        # clear metadata bit if insert failed
        bitmap &= ~MB_SVG_METADATA
        channels.append(_status("svg_metadata", "skipped", f"error: {exc}"))

    # Stable channel report order
    order = ["svg_metadata", "path_epsilon", "path_order", "metric_quantize"]
    by_id = {c["id"]: c for c in channels}
    channels = [by_id[i] for i in order if i in by_id]

    return out, channels


def extract(svg: str) -> dict[str, Any]:
    """Extract stego fields from an SVG string.

    Returns at least ``intent_digest`` (hex str or None if missing).
    """
    result: dict[str, Any] = {
        "intent_digest": None,
        "method_bitmap": None,
        "version": None,
        "channels_detected": [],
    }

    # Prefer sf:payload text (with or without namespace prefix)
    m = re.search(
        r"<sf:payload\b[^>]*>(.*?)</sf:payload>",
        svg,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        # Clark/expanded or unprefixed payload inside metadata
        m = re.search(
            r"<payload\b[^>]*>(.*?)</payload>",
            svg,
            flags=re.IGNORECASE | re.DOTALL,
        )
    if m:
        obj = _parse_payload_b64(m.group(1))
        if obj is not None:
            d = obj.get("d")
            if isinstance(d, str) and d:
                result["intent_digest"] = d.lower()
            if "m" in obj:
                try:
                    result["method_bitmap"] = int(obj["m"])
                except (TypeError, ValueError):
                    pass
            if "v" in obj:
                result["version"] = obj["v"]
            r = obj.get("r")
            if isinstance(r, str) and r:
                result["sigil_root"] = r.lower()
            result["channels_detected"].append("svg_metadata")

    # metric_quantize detection
    metrics = re.findall(
        r'data-sf-metric=["\']([0-9a-fA-F]+)["\']',
        svg,
    )
    if metrics:
        result["channels_detected"].append("metric_quantize")
        result["metrics"] = [x.lower() for x in metrics]

    if _path_order_ok(svg):
        result["channels_detected"].append("path_order")
        if result["intent_digest"]:
            result["order_token"] = _order_token(result["intent_digest"])

    # path_epsilon: recoverable when floats sit on EPS parity grid
    geom_bits: list[int] = []
    for attr_m in re.finditer(
        r'\b(?:points|d)=([\'"])(.*?)\1',
        svg,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        for fm in _FLOAT_RE.finditer(attr_m.group(2)):
            try:
                geom_bits.append(_decode_float_bit(float(fm.group(0))))
            except ValueError:
                continue
    if geom_bits:
        result["channels_detected"].append("path_epsilon")
        result["epsilon_bit_count"] = len(geom_bits)
        result["epsilon_bits"] = geom_bits

    return result


def inject_sigil_root(svg: str, sigil_root: str) -> str:
    """Update sf:payload to v2 including sigil_root without touching geometry."""
    root = (sigil_root or "").strip().lower()
    if len(root) != 64:
        raise ValueError("sigil_root must be 64 hex chars")
    m = re.search(
        r"(<sf:payload\b[^>]*>)(.*?)(</sf:payload>)",
        svg,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        # No payload — leave unchanged (caller may re-embed)
        return svg
    obj = _parse_payload_b64(m.group(2))
    if not obj:
        return svg
    d = obj.get("d") or ""
    bitmap = int(obj.get("m") or 0)
    payload_b64 = _build_payload(str(d), bitmap, sigil_root=root)
    return svg[: m.start(2)] + payload_b64 + svg[m.end(2) :]


def expected_epsilon_bits(digest_hex: str, n: int) -> list[int]:
    """Digest-derived bits that path_epsilon embeds into the first n floats."""
    bits = _digest_bits(digest_hex)
    if not bits or n <= 0:
        return []
    return [bits[i % len(bits)] for i in range(n)]
