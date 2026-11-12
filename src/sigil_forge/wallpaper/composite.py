"""Deterministic composite: procedural/operator background + canonical glyph.

ALLOWED: uniform scale, translation, opacity, glow approximation.
FORBIDDEN: topology mutation of the master glyph paths.
"""

from __future__ import annotations

import re
from pathlib import Path

from stego_png import write_rgb_png
from wallpaper.seed import file_sha256

# --- minimal pure RGB PNG helpers for wallpaper canvas ---


def _hash_color(seed: int, i: int) -> tuple[int, int, int]:
    x = (seed ^ (i * 0x9E3779B97F4A7C15)) & 0xFFFFFFFFFFFFFFFF
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
    r = (x >> 16) & 0xFF
    g = (x >> 8) & 0xFF
    b = x & 0xFF
    return r, g, b


def procedural_background(
    width: int,
    height: int,
    *,
    seed: int,
    complexity: float = 0.3,
    theme: str = "neutral",
) -> bytes:
    """Generate a quiet atmospheric RGB buffer (no glyphs/text)."""
    # Theme bias
    bias = {
        "saturnine": (20, 22, 28),
        "jovian": (18, 28, 48),
        "martial": (40, 18, 18),
        "solar": (48, 36, 18),
        "venusian": (42, 24, 32),
        "mercurial": (22, 30, 36),
        "lunar": (24, 28, 34),
        "neutral": (28, 28, 30),
        "custom": (28, 28, 30),
    }.get(theme, (28, 28, 30))

    buf = bytearray(width * height * 3)
    # Soft vertical gradient + seeded noise speckles
    for y in range(height):
        t = y / max(height - 1, 1)
        br = int(bias[0] * (0.7 + 0.5 * (1 - t)))
        bg = int(bias[1] * (0.7 + 0.45 * t))
        bb = int(bias[2] * (0.75 + 0.4 * (1 - abs(t - 0.4))))
        for x in range(width):
            n = 0
            if complexity > 0.05:
                # sparse noise
                h = (seed + x * 374761393 + y * 668265263) & 0xFFFFFFFF
                if (h % 1000) < int(complexity * 40):
                    n = (h >> 8) % 12 - 6
            i = (y * width + x) * 3
            buf[i] = max(0, min(255, br + n))
            buf[i + 1] = max(0, min(255, bg + n))
            buf[i + 2] = max(0, min(255, bb + n))

    # Large soft radial quiet field for sigil (slightly lighter)
    return bytes(buf)


def _parse_svg_polylines(svg_text: str) -> list[list[tuple[float, float]]]:
    """Extract polyline point lists from canonical glyph SVG (read-only)."""
    polys: list[list[tuple[float, float]]] = []
    for m in re.finditer(r'points="([^"]+)"', svg_text):
        pts: list[tuple[float, float]] = []
        for pair in m.group(1).split():
            if "," not in pair:
                continue
            a, b = pair.split(",", 1)
            try:
                pts.append((float(a), float(b)))
            except ValueError:
                continue
        if len(pts) >= 2:
            polys.append(pts)
    return polys


def _bresenham(
    buf: bytearray,
    w: int,
    h: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    rgb: tuple[int, int, int],
    alpha: float,
) -> None:
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    a = max(0.0, min(1.0, alpha))
    while True:
        if 0 <= x < w and 0 <= y < h:
            i = (y * w + x) * 3
            buf[i] = int(buf[i] * (1 - a) + rgb[0] * a)
            buf[i + 1] = int(buf[i + 1] * (1 - a) + rgb[1] * a)
            buf[i + 2] = int(buf[i + 2] * (1 - a) + rgb[2] * a)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def composite_glyph_on_background(
    background_rgb: bytes,
    width: int,
    height: int,
    *,
    glyph_svg: str,
    cx: float,
    cy: float,
    scale: float,
    opacity: float,
    glow: float = 0.0,
    stroke_rgb: tuple[int, int, int] = (230, 230, 235),
) -> bytes:
    """Overlay canonical polyline geometry onto RGB background.

    Glyph paths are read from SVG and mapped with uniform scale + translation only.
    """
    if len(background_rgb) != width * height * 3:
        raise ValueError("background buffer size mismatch")
    buf = bytearray(background_rgb)
    polys = _parse_svg_polylines(glyph_svg)
    if not polys:
        return bytes(buf)

    # Source bbox in viewBox 0..100
    all_pts = [p for poly in polys for p in poly]
    min_x = min(p[0] for p in all_pts)
    max_x = max(p[0] for p in all_pts)
    min_y = min(p[1] for p in all_pts)
    max_y = max(p[1] for p in all_pts)
    src_w = max(max_x - min_x, 1e-6)
    src_h = max(max_y - min_y, 1e-6)

    target_w = scale * width
    target_h = scale * height
    # Fit uniformly
    s = min(target_w / src_w, target_h / src_h)
    # Center of placement in pixels
    px_c = cx * width
    py_c = cy * height
    src_cx = (min_x + max_x) / 2.0
    src_cy = (min_y + max_y) / 2.0

    def map_pt(x: float, y: float) -> tuple[int, int]:
        dx = (x - src_cx) * s
        dy = (y - src_cy) * s
        return int(round(px_c + dx)), int(round(py_c + dy))

    # Soft glow pass (thicker low-alpha strokes)
    if glow > 0.05:
        g_alpha = opacity * 0.35 * glow
        for poly in polys:
            for i in range(len(poly) - 1):
                x0, y0 = map_pt(*poly[i])
                x1, y1 = map_pt(*poly[i + 1])
                for ox, oy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                    _bresenham(
                        buf, width, height, x0 + ox, y0 + oy, x1 + ox, y1 + oy, stroke_rgb, g_alpha
                    )

    for poly in polys:
        for i in range(len(poly) - 1):
            x0, y0 = map_pt(*poly[i])
            x1, y1 = map_pt(*poly[i + 1])
            _bresenham(buf, width, height, x0, y0, x1, y1, stroke_rgb, opacity)

    return bytes(buf)


def load_operator_background(path: Path, width: int, height: int) -> bytes | None:
    """Load operator PNG if it is filter-0 RGB matching size; else None."""
    try:
        from stego_png import read_rgb_png

        w, h, rgb = read_rgb_png(path.read_bytes())
        if w == width and h == height:
            return rgb
    except Exception:
        return None
    return None


def resize_rgb_nearest(
    rgb: bytes,
    src_w: int,
    src_h: int,
    dst_w: int,
    dst_h: int,
) -> bytes:
    """Nearest-neighbor resize of contiguous RGB buffer (stdlib only)."""
    if src_w < 1 or src_h < 1 or dst_w < 1 or dst_h < 1:
        raise ValueError("invalid dimensions for resize")
    if len(rgb) != src_w * src_h * 3:
        raise ValueError("rgb length does not match source dimensions")
    if src_w == dst_w and src_h == dst_h:
        return rgb
    out = bytearray(dst_w * dst_h * 3)
    for y in range(dst_h):
        sy = min(src_h - 1, (y * src_h) // dst_h)
        for x in range(dst_w):
            sx = min(src_w - 1, (x * src_w) // dst_w)
            si = (sy * src_w + sx) * 3
            di = (y * dst_w + x) * 3
            out[di] = rgb[si]
            out[di + 1] = rgb[si + 1]
            out[di + 2] = rgb[si + 2]
    return bytes(out)


def write_wallpaper_png(path: Path, width: int, height: int, rgb: bytes) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(write_rgb_png(width, height, rgb))
    return file_sha256(str(path))
