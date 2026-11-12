"""Export fused Layout geometry to monochrome SVG (no plaintext intent)."""

from __future__ import annotations

from fuse import Layout


def _fmt_pt(p: tuple[float, float]) -> str:
    return f"{p[0]:.4f},{p[1]:.4f}"


def _polyline(points: list[tuple[float, float]], stroke: str) -> str:
    if not points:
        return ""
    pts = " ".join(_fmt_pt(p) for p in points)
    return (
        f'<polyline points="{pts}" fill="none" stroke="{stroke}" '
        f'stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def layout_to_svg(
    layout: Layout,
    stroke: str = "#0a0a0a",
    bg: str = "#f7f4ef",
) -> str:
    """Render layout as SVG string. Geometry only — no intent text."""
    min_x, min_y, w, h = layout.view_box
    mono = _polyline(layout.monogram_points, stroke)
    kamea = _polyline(layout.kamea_points, stroke)
    bind_parts = [
        _polyline(poly, stroke) for poly in (layout.bind_polylines or [])
    ]
    bind_inner = "\n    ".join(p for p in bind_parts if p)
    rose = _polyline(layout.rose_points or [], stroke)
    seal_strokes = getattr(layout, "planetary_seal_strokes", None) or []
    if seal_strokes:
        seal = "\n    ".join(
            p for p in (_polyline(poly, stroke) for poly in seal_strokes) if p
        )
    else:
        seal = _polyline(getattr(layout, "planetary_seal_path", None) or [], stroke)
    # Markers for Rose Cross start/terminal (geometry only — no letter labels)
    markers = ""
    sm = getattr(layout, "rose_start_marker", None) or []
    tm = getattr(layout, "rose_terminal_marker", None) or []
    if len(sm) == 2:
        markers += (
            f'<circle id="rose-start" cx="{sm[0]:.4f}" cy="{sm[1]:.4f}" '
            f'r="1.2" fill="none" stroke="{stroke}" stroke-width="0.8"/>'
        )
    if len(tm) == 2:
        markers += (
            f'<rect id="rose-terminal" x="{tm[0] - 1.0:.4f}" y="{tm[1] - 1.0:.4f}" '
            f'width="2.0" height="2.0" fill="none" stroke="{stroke}" stroke-width="0.8"/>'
        )
    # Deliberately omit spare_letters / normalized intent / rune names from SVG.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{min_x:g} {min_y:g} {w:g} {h:g}" '
        f'width="100%" height="100%">\n'
        f'  <rect x="{min_x:g}" y="{min_y:g}" width="{w:g}" height="{h:g}" '
        f'fill="{bg}"/>\n'
        f'  <g id="spare-monogram">\n'
        f"    {mono}\n"
        f"  </g>\n"
        f'  <g id="kamea-path">\n'
        f"    {kamea}\n"
        f"  </g>\n"
        f'  <g id="bind-runes">\n'
        f"    {bind_inner}\n"
        f"  </g>\n"
        f'  <g id="rose-cross-path">\n'
        f"    {rose}\n"
        f"    {markers}\n"
        f"  </g>\n"
        f'  <g id="planetary-seal">\n'
        f"    {seal}\n"
        f"  </g>\n"
        f"</svg>\n"
    )
