"""Privacy: public artifacts must not leak plaintext intent."""

from __future__ import annotations

from pathlib import Path

from sigil_forge.construct import run


def test_public_svg_has_no_plaintext(tmp_path: Path):
    intent = "I maintain calm focus while shipping Sigil-Forge"
    packet = run(intent, out_root=tmp_path, square="saturn")
    svg = Path(packet["artifacts"]["svg"]).read_text(encoding="utf-8")
    assert intent.lower() not in svg.lower()
    # packet local may contain intent
    assert packet.get("normalized_intent") or packet.get("crypto", {}).get(
        "ciphertext_present"
    )


def test_public_png_has_no_plaintext_when_present(tmp_path: Path):
    intent = "I maintain calm focus while shipping Sigil-Forge"
    packet = run(intent, out_root=tmp_path, square="saturn")
    png = packet.get("artifacts", {}).get("png")
    if not png:
        return
    data = Path(png).read_bytes()
    assert intent.encode("utf-8") not in data
    assert intent.lower().encode("utf-8") not in data.lower()
