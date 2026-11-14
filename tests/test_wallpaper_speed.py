"""The faster paths must produce exactly what the slow ones did."""

from __future__ import annotations

import hashlib

import pytest

from sigil_forge.stego_png import embed_lsb, embed_lsb_rgb, read_rgb_png, write_rgb_png
from sigil_forge.wallpaper.composite import procedural_background

_BIAS = {
    "saturnine": (20, 22, 28),
    "jovian": (18, 28, 48),
    "martial": (40, 18, 18),
    "solar": (48, 36, 18),
    "venusian": (42, 24, 32),
    "mercurial": (22, 30, 36),
    "lunar": (24, 28, 34),
    "neutral": (28, 28, 30),
    "custom": (28, 28, 30),
}


def _reference_background(width, height, *, seed, complexity, theme):
    """The per-pixel loop the engine used through v0.18.0, kept as the oracle."""
    bias = _BIAS.get(theme, (28, 28, 30))
    buf = bytearray(width * height * 3)
    for y in range(height):
        t = y / max(height - 1, 1)
        br = int(bias[0] * (0.7 + 0.5 * (1 - t)))
        bg = int(bias[1] * (0.7 + 0.45 * t))
        bb = int(bias[2] * (0.75 + 0.4 * (1 - abs(t - 0.4))))
        for x in range(width):
            n = 0
            if complexity > 0.05:
                h = (seed + x * 374761393 + y * 668265263) & 0xFFFFFFFF
                if (h % 1000) < int(complexity * 40):
                    n = (h >> 8) % 12 - 6
            i = (y * width + x) * 3
            buf[i] = max(0, min(255, br + n))
            buf[i + 1] = max(0, min(255, bg + n))
            buf[i + 2] = max(0, min(255, bb + n))
    return bytes(buf)


@pytest.mark.parametrize("theme", [*_BIAS, "not-a-theme"])
def test_background_is_byte_identical_to_the_per_pixel_loop(theme):
    for seed in (0, 1, 716315008, 2**32 - 1, 2**40 + 7, -5):
        for complexity in (0.0, 0.05, 0.051, 0.3, 1.0, 30.0):
            for width, height in ((1, 1), (7, 3), (64, 48), (33, 1), (1, 40)):
                args = dict(seed=seed, complexity=complexity, theme=theme)
                assert procedural_background(width, height, **args) == _reference_background(
                    width, height, **args
                ), (theme, seed, complexity, width, height)


def test_background_golden_digest():
    """Pins the output itself, so both implementations cannot drift together."""
    got = procedural_background(1170, 2532, seed=716315008, complexity=0.3, theme="mercurial")
    assert hashlib.sha256(got).hexdigest().startswith("62fabe34ecd1")


def test_noise_is_actually_present_and_sparse():
    quiet = procedural_background(200, 200, seed=7, complexity=0.0, theme="neutral")
    noisy = procedural_background(200, 200, seed=7, complexity=0.3, theme="neutral")
    changed = sum(1 for i in range(0, len(quiet), 3) if quiet[i : i + 3] != noisy[i : i + 3])
    assert 0 < changed < 200 * 200 * 0.05


def test_embedding_into_pixels_matches_embedding_into_a_png():
    rgb = procedural_background(40, 30, seed=3, complexity=0.3, theme="lunar")
    png = write_rgb_png(40, 30, rgb)
    payload = b"SF1\x00" + bytes(range(32))
    direct = embed_lsb_rgb(40, 30, rgb, payload)
    assert direct == embed_lsb(png, payload)
    assert read_rgb_png(direct)[:2] == (40, 30)
    with pytest.raises(ValueError):
        embed_lsb_rgb(40, 30, rgb, b"")
    with pytest.raises(ValueError):
        embed_lsb_rgb(2, 2, bytes(12), b"x" * 10)
