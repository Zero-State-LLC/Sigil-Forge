"""PNG LSB stego: pure-Python RGB PNG + synthetic round-trip (no SVG raster)."""

from stego_png import embed_lsb, extract_lsb, pack_payload, read_rgb_png, write_rgb_png
from raster_svg import svg_to_png_bytes


def test_lsb_roundtrip_synthetic():
    raw = bytes([0, 0, 0] * (32 * 32))
    png = write_rgb_png(32, 32, raw)
    payload = b"SF1\x00" + b"\x11" * 32
    out = embed_lsb(png, payload)
    got = extract_lsb(out, len(payload))
    assert got == payload


def test_write_read_rgb_roundtrip():
    w, h = 8, 4
    # Distinct RGB pattern
    raw = bytes((i * 3) % 256 for i in range(w * h * 3))
    png = write_rgb_png(w, h, raw)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    rw, rh, got = read_rgb_png(png)
    assert (rw, rh) == (w, h)
    assert got == raw


def test_lsb_with_nonzero_carrier():
    """LSB embed must preserve non-LSB bits of carrier pixels."""
    w, h = 16, 16
    raw = bytes([(x * 17 + y * 31) % 256 for y in range(h) for x in range(w * 3)])
    png = write_rgb_png(w, h, raw)
    payload = pack_payload(b"\xab" * 32)
    out = embed_lsb(png, payload)
    assert extract_lsb(out, len(payload)) == payload
    _, _, stego_rgb = read_rgb_png(out)
    # All bits above LSB match original
    for a, b in zip(raw, stego_rgb):
        assert (a & 0xFE) == (b & 0xFE)


def test_pack_payload_magic_and_optional_sealed():
    digest = bytes(range(32))
    p = pack_payload(digest)
    assert p[:4] == b"SF1\x00"
    assert p[4:36] == digest
    assert len(p) == 36

    sealed = b"ciphertext-blob"
    p2 = pack_payload(digest, sealed=sealed)
    assert p2[:36] == p
    # length-prefixed (uint32 BE)
    assert p2[36:40] == (len(sealed)).to_bytes(4, "big")
    assert p2[40:] == sealed


def test_payload_too_large_raises():
    # 2x2 RGB = 12 bytes capacity = 12 bits usable for payload → 1 full byte max
    png = write_rgb_png(2, 2, bytes(12))
    try:
        embed_lsb(png, b"SF1\x00" + b"\x00" * 32)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "capacity" in str(e).lower() or "large" in str(e).lower()


def test_raster_svg_returns_none_without_backend():
    """Without optional raster deps, channel may skip — must not raise."""
    result = svg_to_png_bytes("<svg xmlns='http://www.w3.org/2000/svg'></svg>")
    # Either a real PNG or None; never raise. Synthetic path does not require raster.
    assert result is None or (isinstance(result, bytes) and result[:8] == b"\x89PNG\r\n\x1a\n")


def test_read_rgb_png_refuses_idat_larger_than_ihdr():
    """IDAT that inflates past what IHDR declares is rejected without inflating it all."""
    import struct
    import zlib

    import pytest

    from stego_png import _chunk

    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(b"\x00" * 50_000_000, 9))
        + _chunk(b"IEND", b"")
    )
    assert len(png) < 100_000
    with pytest.raises(ValueError, match="inflated size exceeds 4 bytes"):
        read_rgb_png(png)


def test_read_rgb_png_truncated_idat_still_raises_zlib_error():
    import struct
    import zlib

    import pytest

    from stego_png import _chunk

    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(b"\x00\x01\x02\x03")[:-3])
        + _chunk(b"IEND", b"")
    )
    with pytest.raises(zlib.error):
        read_rgb_png(png)


def test_read_rgb_png_refuses_oversized_or_empty_header():
    import struct
    import zlib

    import pytest

    from stego_png import MAX_PNG_PIXELS, _chunk

    def png(width, height):
        return (
            b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(b"\x00"))
            + _chunk(b"IEND", b"")
        )

    assert 7680 * 4320 < MAX_PNG_PIXELS  # an 8K wallpaper is still accepted
    for width, height in [(100_000, 100_000), (0, 10), (10, 0)]:
        with pytest.raises(ValueError, match="unsupported PNG size"):
            read_rgb_png(png(width, height))
