"""Descriptive statistics for the least-significant-bit plane of a PNG.

These are plain counts and one chi-square figure. They are NOT a
steganography detector: a carrier with natural noise and one with an
embedded payload can score alike, and the output carries no verdict.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from sigil_forge.stego_envelope import SF11_MAGIC
from sigil_forge.stego_png import MAGIC as SF1_MAGIC
from sigil_forge.stego_png import read_rgb_png
from sigil_forge.wallpaper.vault import SF12_MAGIC

MAX_FILE_BYTES = 64 * 1024 * 1024

NOTE = (
    "Descriptive statistics only. Not a steganography detector; a carrier "
    "with natural noise and one with an embedded payload can score alike."
)

_LSB_TABLE = bytes(v & 1 for v in range(256))
_HEADERS = ((SF12_MAGIC, "SF12"), (SF11_MAGIC, "SF11"), (SF1_MAGIC, "SF1"))


def _ratio(ones: int, total: int) -> float:
    return round(ones / total, 6) if total else 0.0


def chi_square_pairs(counts: list[int]) -> tuple[float, int]:
    """Pairs-of-values chi-square over a 256-bin histogram.

    For each k in 0..127 let a = counts[2k], b = counts[2k+1] and the
    expected count of each member be (a + b) / 2. Pairs with a + b == 0 are
    skipped. The statistic is the sum over used pairs of
    ((a-e)^2 + (b-e)^2) / e, which equals (a-b)^2 / (a+b).
    Degrees of freedom = (number of used pairs) - 1.
    """
    stat = 0.0
    used = 0
    for k in range(128):
        a, b = counts[2 * k], counts[2 * k + 1]
        if a + b == 0:
            continue
        used += 1
        stat += (a - b) ** 2 / (a + b)
    return stat, max(used - 1, 0)


def _header(rgb: bytes) -> str | None:
    """Name the payload format whose magic sits in the first 32 LSBs."""
    if len(rgb) < 32:
        return None
    head = bytearray(4)
    for i in range(32):
        head[i >> 3] = (head[i >> 3] << 1) | (rgb[i] & 1)
    for magic, name in _HEADERS:
        if bytes(head) == magic:
            return name
    return None


def analyze_png(path: Path | str, *, max_bytes: int = MAX_FILE_BYTES) -> dict[str, Any]:
    """Return LSB-plane statistics for an 8-bit RGB PNG (raises on bad input)."""
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"file not found: {p}")
    from sigil_forge.safe_io import read_regular

    try:
        data = read_regular(p, max_bytes)
    except OSError as exc:
        raise ValueError(f"cannot read PNG: {exc.args[0] if exc.args else type(exc).__name__}") from None
    width, height, rgb = read_rgb_png(data)

    samples = len(rgb)
    plane = rgb.translate(_LSB_TABLE)
    ones = plane.count(1)
    channel = {
        name: _ratio(plane[i::3].count(1), samples // 3)
        for i, name in enumerate("rgb")
    }
    counter = Counter(rgb)
    hist = [counter.get(v, 0) for v in range(256)]
    chi, df = chi_square_pairs(hist)
    header = _header(rgb)
    return {
        "path": str(p),
        "width": width,
        "height": height,
        "samples": samples,
        "lsb_ones": ones,
        "lsb_ones_ratio": _ratio(ones, samples),
        "lsb_ones_ratio_r": channel["r"],
        "lsb_ones_ratio_g": channel["g"],
        "lsb_ones_ratio_b": channel["b"],
        "chi_square_pairs": round(chi, 6),
        "chi_square_df": df,
        "header": header,
        "header_found": header is not None,
        "note": NOTE,
    }
