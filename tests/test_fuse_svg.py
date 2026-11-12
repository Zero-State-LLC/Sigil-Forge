from sigil_forge.normalize import normalize_intent
from sigil_forge.crypto_payload import intent_digest
from sigil_forge.fuse import build_layout
from sigil_forge.svg_export import layout_to_svg


def test_layout_has_both_channels_when_letters_exist():
    n = normalize_intent("I maintain calm focus")
    d = intent_digest(n)
    lay = build_layout(n, d, square_override="saturn")
    assert lay.spare_letters == "mntclfs"
    assert len(lay.monogram_points) >= 2
    assert len(lay.kamea_points) >= 1


def test_svg_contains_paths_not_plaintext_intent():
    n = normalize_intent("I maintain calm focus")
    d = intent_digest(n)
    svg = layout_to_svg(build_layout(n, d, square_override="saturn"))
    assert "<svg" in svg
    assert "path" in svg.lower() or "polyline" in svg.lower()
    assert "i maintain calm focus" not in svg.lower()
