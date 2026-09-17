"""Host AI / operator background providers (offline-safe).

Background sources (``background_method``):
  - ``procedural`` — pure-Python atmosphere (default, no network)
  - ``operator_supplied`` — local PNG path via ``--background``
  - ``ai_generated`` — host-provided AI image (file and/or command)

The skill never calls a commercial image API directly. Hosts wire tools via:
  - ``--background PATH`` (pre-rendered PNG from any tool)
  - ``--provider-command`` / env ``SIGIL_FORGE_BG_COMMAND`` (executable + args template)
  - prompt package always written under ``wallpaper/background-prompt-*.json``

Provider ids recorded in wallpaper-spec.generation.provider:
  procedural | operator | host_file | host_command | standin
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wallpaper.composite import (
    load_operator_background,
    procedural_background,
    resize_rgb_nearest,
)


@dataclass
class BackgroundResult:
    rgb: bytes
    background_method: str
    provider: str | None
    model: str | None = None
    notes: list[str] = field(default_factory=list)
    command_ran: str | None = None
    source_path: str | None = None


def _env_command() -> str | None:
    v = (os.environ.get("SIGIL_FORGE_BG_COMMAND") or "").strip()
    return v or None


def expand_provider_command(
    template: str,
    *,
    prompt_path: Path,
    out_path: Path,
    width: int,
    height: int,
    seed: int,
    surface: str,
) -> str:
    """Expand {placeholders} in a host command template.

    Placeholders: prompt_path, out_path, width, height, seed, surface.
    Unknown ``{name}`` left as-is is not supported — use only documented keys.
    """
    mapping = {
        "prompt_path": str(prompt_path),
        "out_path": str(out_path),
        "width": str(width),
        "height": str(height),
        "seed": str(seed),
        "surface": surface,
    }
    # Support both {key} and $KEY style for convenience
    out = template
    for k, v in mapping.items():
        out = out.replace("{" + k + "}", v)
        out = out.replace("$" + k.upper(), v)
    return out


def run_host_command(
    template: str,
    *,
    prompt_path: Path,
    out_path: Path,
    width: int,
    height: int,
    seed: int,
    surface: str,
    timeout_s: float = 300.0,
) -> tuple[bool, str, str]:
    """Run host provider command without a shell.

    Returns (ok, expanded_cmd, error_message).

    The expanded template is parsed with ``shlex.split`` and executed via
    ``subprocess.run(..., shell=False)``. Shell metacharacters, pipes, and
    redirects are not supported — operators should pass an executable plus
    argument template (quote path placeholders when paths may contain spaces).
    """
    expanded = expand_provider_command(
        template,
        prompt_path=prompt_path,
        out_path=out_path,
        width=width,
        height=height,
        seed=seed,
        surface=surface,
    )
    try:
        args = shlex.split(expanded, posix=True)
    except ValueError as exc:
        return False, expanded, f"provider command parse error: {exc}"
    if not args:
        return False, expanded, "provider command is empty after parsing"
    try:
        proc = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, expanded, f"provider command timed out after {timeout_s}s"
    except OSError as exc:
        return False, expanded, f"provider command failed to start: {exc}"
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:500]
        return False, expanded, f"provider command exit {proc.returncode}: {err}"
    if not out_path.is_file():
        return False, expanded, f"provider command did not write {out_path}"
    return True, expanded, ""


def load_background_image(
    path: Path,
    width: int,
    height: int,
    *,
    allow_resize: bool = True,
) -> bytes | None:
    """Load PNG as RGB buffer sized to canvas.

    Exact-size match preferred; otherwise nearest-neighbor resize when allowed.
    Absolute and relative operator paths are allowed; NUL bytes are rejected.
    """
    raw = os.fspath(path)
    if "\x00" in raw:
        return None
    path = Path(raw)
    if not path.is_file():
        return None
    # Exact path first (historical helper)
    exact = load_operator_background(path, width, height)
    if exact is not None:
        return exact
    if not allow_resize:
        return None
    try:
        from stego_png import read_rgb_png

        w, h, rgb = read_rgb_png(path.read_bytes())
        if w == width and h == height:
            return rgb
        return resize_rgb_nearest(rgb, w, h, width, height)
    except Exception:
        return None


def resolve_background(
    *,
    background_method: str,
    width: int,
    height: int,
    seed: int,
    complexity: float,
    theme: str,
    surface: str,
    prompt_path: Path,
    bg_file: Path,
    background_path: Path | str | None = None,
    provider: str | None = None,
    provider_command: str | None = None,
    model: str | None = None,
    require_ai: bool = False,
    allow_resize: bool = True,
) -> BackgroundResult:
    """Resolve RGB background according to method + host wiring.

    Offline defaults: procedural always available. AI path is fail-open to
    procedural stand-in unless ``require_ai`` is True.
    """
    method = (background_method or "procedural").strip()
    notes: list[str] = []
    cmd_template = (provider_command or _env_command() or "").strip() or None
    explicit_path = Path(background_path) if background_path else None

    if method == "procedural":
        rgb = procedural_background(
            width, height, seed=seed, complexity=complexity, theme=theme
        )
        return BackgroundResult(
            rgb=rgb,
            background_method="procedural",
            provider=provider or "procedural",
            model=model,
        )

    if method == "operator_supplied":
        if not explicit_path:
            if require_ai:
                raise ValueError(
                    "operator_supplied requires --background PATH (or set require false)"
                )
            rgb = procedural_background(
                width, height, seed=seed, complexity=complexity, theme=theme
            )
            notes.append("operator_supplied_missing_path_fallback_procedural")
            return BackgroundResult(
                rgb=rgb,
                background_method="procedural",
                provider="standin",
                model=model,
                notes=notes,
            )
        rgb = load_background_image(
            explicit_path, width, height, allow_resize=allow_resize
        )
        if rgb is None:
            if require_ai:
                raise ValueError(
                    f"operator background unusable or wrong format: {explicit_path}"
                )
            rgb = procedural_background(
                width, height, seed=seed, complexity=complexity, theme=theme
            )
            notes.append("operator_background_unusable_fallback_procedural")
            return BackgroundResult(
                rgb=rgb,
                background_method="procedural",
                provider="standin",
                model=model,
                notes=notes,
                source_path=str(explicit_path),
            )
        return BackgroundResult(
            rgb=rgb,
            background_method="operator_supplied",
            provider=provider or "operator",
            model=model,
            source_path=str(explicit_path),
        )

    if method == "ai_generated":
        # 1) Explicit host file (agent generated offline then passed back)
        if explicit_path and explicit_path.is_file():
            rgb = load_background_image(
                explicit_path, width, height, allow_resize=allow_resize
            )
            if rgb is not None:
                return BackgroundResult(
                    rgb=rgb,
                    background_method="ai_generated",
                    provider=provider or "host_file",
                    model=model,
                    source_path=str(explicit_path),
                )
            notes.append("ai_host_file_unusable")

        # 2) Host command (ComfyUI wrapper, local diffusion, etc.)
        if cmd_template:
            ok, expanded, err = run_host_command(
                cmd_template,
                prompt_path=prompt_path,
                out_path=bg_file,
                width=width,
                height=height,
                seed=seed,
                surface=surface,
            )
            if ok:
                rgb = load_background_image(
                    bg_file, width, height, allow_resize=allow_resize
                )
                if rgb is not None:
                    return BackgroundResult(
                        rgb=rgb,
                        background_method="ai_generated",
                        provider=provider or "host_command",
                        model=model,
                        command_ran=expanded,
                        source_path=str(bg_file),
                    )
                notes.append("host_command_wrote_unreadable_png")
            else:
                notes.append(f"host_command_failed:{err}")

        # 3) Stand-in or hard fail
        if require_ai:
            raise ValueError(
                "ai_generated required but no usable host background "
                f"(notes={notes}; provide --background, --provider-command, "
                "or SIGIL_FORGE_BG_COMMAND)"
            )
        rgb = procedural_background(
            width, height, seed=seed, complexity=complexity, theme=theme
        )
        notes.append(
            "ai_generated_procedural_standin_prompt_package_ready_for_host"
        )
        return BackgroundResult(
            rgb=rgb,
            background_method="procedural",
            provider="standin",
            model=model,
            notes=notes,
            command_ran=None,
        )

    raise ValueError(f"unknown background_method {method!r}")


def enrich_prompt_package(
    prompt_pkg: dict[str, Any],
    *,
    width: int,
    height: int,
    seed: int,
    surface: str,
    out_hint: str,
) -> dict[str, Any]:
    """Add host-tool hints to the background prompt JSON package."""
    out = dict(prompt_pkg)
    out["canvas"] = {"width": width, "height": height}
    out["seed"] = seed
    out["surface"] = surface
    out["output_hint"] = out_hint
    out["contract"] = {
        "role": "background_only",
        "forbid_glyph_invention": True,
        "composite": "sigil_forge_places_canonical_vector_after_generation",
    }
    out["provider_command_placeholders"] = [
        "prompt_path",
        "out_path",
        "width",
        "height",
        "seed",
        "surface",
    ]
    return out
