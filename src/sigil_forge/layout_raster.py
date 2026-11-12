"""Stdlib-only Layout → 8-bit RGB PNG (no cairosvg/resvg required).

Renders monogram + kamea polylines onto a square canvas so ``png_lsb`` can
apply reliably offline. Geometry is drawn from layout points (viewBox 0..100),
not by parsing SVG — keeps the procedural master as the source of truth.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from stego_png import write_rgb_png

# Default export size — enough LSB capacity for SF1 digest payload (36 bytes).
DEFAULT_SIZE = 256
BG = (247, 244, 239)  # match svg_export default bg #f7f4ef
FG = (10, 10, 10)  # #0a0a0a


def _plot(x: float, y: float, size: int, canvas: float = 100.0) -> tuple[int, int]:
    """Map layout coords (0..canvas) → pixel indices, clamped."""
    px = int(round((x / canvas) * (size - 1)))
    py = int(round((y / canvas) * (size - 1)))
    px = max(0, min(size - 1, px))
    py = max(0, min(size - 1, py))
    return px, py


def _set_pixel(buf: bytearray, size: int, x: int, y: int, rgb: tuple[int, int, int]) -> None:
    i = (y * size + x) * 3
    buf[i] = rgb[0]
    buf[i + 1] = rgb[1]
    buf[i + 2] = rgb[2]


def _bresenham(
    buf: bytearray,
    size: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    rgb: tuple[int, int, int],
) -> None:
    """Draw a 1-pixel-wide line (Bresenham)."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        _set_pixel(buf, size, x, y, rgb)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def _polyline(
    buf: bytearray,
    size: int,
    points: Sequence[tuple[float, float]],
    rgb: tuple[int, int, int],
    canvas: float = 100.0,
) -> None:
    if len(points) < 2:
        if len(points) == 1:
            px, py = _plot(points[0][0], points[0][1], size, canvas)
            _set_pixel(buf, size, px, py, rgb)
        return
    for i in range(len(points) - 1):
        x0, y0 = _plot(points[i][0], points[i][1], size, canvas)
        x1, y1 = _plot(points[i + 1][0], points[i + 1][1], size, canvas)
        _bresenham(buf, size, x0, y0, x1, y1, rgb)


def layout_to_rgb(
    monogram_points: Iterable[tuple[float, float]],
    kamea_points: Iterable[tuple[float, float]],
    *,
    size: int = DEFAULT_SIZE,
    bg: tuple[int, int, int] = BG,
    fg: tuple[int, int, int] = FG,
    bind_polylines: Iterable[Iterable[tuple[float, float]]] | None = None,
    rose_points: Iterable[tuple[float, float]] | None = None,
    planetary_seal_strokes: Iterable[Iterable[tuple[float, float]]] | None = None,
) -> bytes:
    """Return raw RGB bytes (size*size*3) for a layout."""
    if size < 8:
        raise ValueError("size must be >= 8")
    buf = bytearray(size * size * 3)
    # fill bg
    for i in range(0, len(buf), 3):
        buf[i] = bg[0]
        buf[i + 1] = bg[1]
        buf[i + 2] = bg[2]
    mono = list(monogram_points)
    kamea = list(kamea_points)
    _polyline(buf, size, mono, fg)
    _polyline(buf, size, kamea, fg)
    if bind_polylines:
        for poly in bind_polylines:
            _polyline(buf, size, list(poly), fg)
    if rose_points:
        _polyline(buf, size, list(rose_points), fg)
    if planetary_seal_strokes:
        for poly in planetary_seal_strokes:
            _polyline(buf, size, list(poly), fg)
    return bytes(buf)


def layout_to_png_bytes(
    monogram_points: Iterable[tuple[float, float]],
    kamea_points: Iterable[tuple[float, float]],
    *,
    size: int = DEFAULT_SIZE,
    bind_polylines: Iterable[Iterable[tuple[float, float]]] | None = None,
    rose_points: Iterable[tuple[float, float]] | None = None,
    planetary_seal_strokes: Iterable[Iterable[tuple[float, float]]] | None = None,
) -> bytes:
    """Render layout geometry to a filter-0 8-bit RGB PNG (stdlib path)."""
    rgb = layout_to_rgb(
        monogram_points,
        kamea_points,
        size=size,
        bind_polylines=bind_polylines,
        rose_points=rose_points,
        planetary_seal_strokes=planetary_seal_strokes,
    )
    return write_rgb_png(size, size, rgb)
