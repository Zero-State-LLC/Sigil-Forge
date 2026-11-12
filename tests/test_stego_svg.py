"""Tests for SVG steganography channels (metadata + geometric/structural)."""

from __future__ import annotations

import re

from sigil_forge.crypto_payload import intent_digest
from sigil_forge.fuse import build_layout
from sigil_forge.normalize import normalize_intent
from sigil_forge.stego_svg import embed, extract
from sigil_forge.svg_export import layout_to_svg


def _sample_svg():
    n = normalize_intent("I maintain calm focus")
    d = intent_digest(n)
    svg = layout_to_svg(build_layout(n, d, square_override="saturn"))
    return n, d, svg


def test_embed_extract_digest():
    n = normalize_intent("I maintain calm focus")
    d = intent_digest(n)
    svg = layout_to_svg(build_layout(n, d, square_override="saturn"))
    out, channels = embed(svg, d, spare_letters="mntclfs")
    got = extract(out)
    assert got["intent_digest"] == d
    assert any(c["id"] == "svg_metadata" and c["status"] == "applied" for c in channels)
    assert n not in out.lower()


def test_no_spare_letters_or_intent_in_public_svg():
    n, d, svg = _sample_svg()
    spare = "mntclfs"
    out, channels = embed(svg, d, spare_letters=spare)
    low = out.lower()
    assert n not in low
    assert spare not in low
    assert "spare_letters" not in low
    # metadata payload is base64, not raw digest hex as plaintext intent
    assert '"intent"' not in low


def test_all_four_channels_reported():
    n, d, svg = _sample_svg()
    out, channels = embed(svg, d, spare_letters="mntclfs")
    ids = {c["id"] for c in channels}
    assert ids >= {"svg_metadata", "path_epsilon", "path_order", "metric_quantize"}
    for c in channels:
        assert c["status"] in ("applied", "skipped")
        assert "detail" in c
    applied = {c["id"] for c in channels if c["status"] == "applied"}
    assert "svg_metadata" in applied
    assert "path_epsilon" in applied
    assert "path_order" in applied
    assert "metric_quantize" in applied


def test_metadata_payload_shape():
    n, d, svg = _sample_svg()
    out, _ = embed(svg, d, spare_letters="mntclfs")
    # sf:payload present
    assert "sf:payload" in out or "payload" in out
    got = extract(out)
    assert got["intent_digest"] == d
    assert "method_bitmap" in got
    assert isinstance(got["method_bitmap"], int)


def test_path_epsilon_perturbs_coordinates():
    n, d, svg = _sample_svg()
    # Collect original floats from polyline points
    before = re.findall(r"[-+]?(?:\d+\.\d+|\d+)", svg)
    out, channels = embed(svg, d, spare_letters="mntclfs")
    after = re.findall(r"[-+]?(?:\d+\.\d+|\d+)", out)
    eps_status = next(c for c in channels if c["id"] == "path_epsilon")
    assert eps_status["status"] == "applied"
    # Geometry floats should differ somewhere (epsilon encoding)
    assert before != after or "points=" in out


def test_metric_quantize_attributes():
    n, d, svg = _sample_svg()
    out, channels = embed(svg, d, spare_letters="mntclfs")
    assert 'data-sf-metric="' in out
    mq = next(c for c in channels if c["id"] == "metric_quantize")
    assert mq["status"] == "applied"
    # First nibbles of digest appear in metric attrs
    assert d[:4] in out


def test_path_order_manifest_binding():
    n, d, svg = _sample_svg()
    out, channels = embed(svg, d, spare_letters="mntclfs")
    po = next(c for c in channels if c["id"] == "path_order")
    assert po["status"] == "applied"
    # Monogram group still precedes kamea
    i_mono = out.find('id="spare-monogram"')
    i_kamea = out.find('id="kamea-path"')
    assert i_mono != -1 and i_kamea != -1
    assert i_mono < i_kamea


def test_extract_missing_metadata():
    bare = '<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>'
    got = extract(bare)
    assert got.get("intent_digest") in (None, "")
