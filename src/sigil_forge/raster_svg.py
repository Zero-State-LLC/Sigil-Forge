"""Optional SVG → PNG rasterization.

Tries available backends; returns ``None`` if none work so the construct
pipeline can mark channel ``png_lsb`` as ``skipped("no_raster_backend")``
without failing the build.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def svg_to_png_bytes(svg: str) -> Optional[bytes]:
    """Rasterize SVG string to PNG bytes, or None if no backend available.

    Backend order:
      1. cairosvg (Python)
      2. resvg CLI
      3. svglib + reportlab renderPM
    """
    data = svg.encode("utf-8") if isinstance(svg, str) else svg

    # 1. cairosvg
    try:
        import cairosvg  # type: ignore

        out = cairosvg.svg2png(bytestring=data)
        if out and out[:8] == b"\x89PNG\r\n\x1a\n":
            return out
    except Exception:
        pass

    # 2. resvg CLI
    resvg = shutil.which("resvg")
    if resvg:
        try:
            with tempfile.TemporaryDirectory() as td:
                tdp = Path(td)
                src = tdp / "in.svg"
                dst = tdp / "out.png"
                src.write_bytes(data)
                subprocess.run(
                    [resvg, str(src), str(dst)],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
                if dst.is_file():
                    out = dst.read_bytes()
                    if out[:8] == b"\x89PNG\r\n\x1a\n":
                        return out
        except Exception:
            pass

    # 3. svglib + reportlab
    try:
        from io import BytesIO

        from reportlab.graphics import renderPM  # type: ignore
        from svglib.svglib import svg2rlg  # type: ignore

        drawing = svg2rlg(BytesIO(data))
        if drawing is not None:
            out = renderPM.drawToString(drawing, fmt="PNG")
            if out and out[:8] == b"\x89PNG\r\n\x1a\n":
                return out
    except Exception:
        pass

    return None
