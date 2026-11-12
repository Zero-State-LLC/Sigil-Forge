"""Host AI background providers + construct --wallpaper one-shot."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sigil_forge.construct import run as construct_run
from sigil_forge.stego_png import write_rgb_png
from sigil_forge.wallpaper.composite import procedural_background, resize_rgb_nearest
from sigil_forge.wallpaper.pipeline import build_wallpaper
from sigil_forge.wallpaper.providers import (
    enrich_prompt_package,
    expand_provider_command,
    load_background_image,
)

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"


def test_expand_provider_command_placeholders():
    cmd = expand_provider_command(
        "tool --p {prompt_path} -o {out_path} -w {width} -h {height} -s {seed} --surf {surface}",
        prompt_path=Path("/tmp/p.json"),
        out_path=Path("/tmp/bg.png"),
        width=1080,
        height=1920,
        seed=42,
        surface="phone_lock",
    )
    assert "/tmp/p.json" in cmd
    assert "/tmp/bg.png" in cmd
    assert "1080" in cmd
    assert "1920" in cmd
    assert "42" in cmd
    assert "phone_lock" in cmd


def test_resize_rgb_nearest_identity_and_scale():
    rgb = bytes([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120])  # 2x2
    same = resize_rgb_nearest(rgb, 2, 2, 2, 2)
    assert same == rgb
    big = resize_rgb_nearest(rgb, 2, 2, 4, 4)
    assert len(big) == 4 * 4 * 3
    assert big[0:3] == bytes([10, 20, 30])


def test_ai_generated_standin_writes_enriched_prompt(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
    )
    run_dir = Path(packet["artifacts"]["run_dir"])
    result = build_wallpaper(
        run_dir,
        surface="phone_lock",
        background_method="ai_generated",
        model="test-model",
    )
    assert result["ok"] is True
    # Without host, method falls back to procedural stand-in
    assert result["background_method"] == "procedural"
    assert result["provider"] == "standin"
    assert any("standin" in n or "prompt_package" in n for n in result["notes"])

    prompt = json.loads(Path(result["prompt"]).read_text(encoding="utf-8"))
    assert "prompt" in prompt and "negative" in prompt
    assert prompt["canvas"]["width"] >= 512
    assert prompt["seed"] is not None
    assert prompt["contract"]["forbid_glyph_invention"] is True
    assert "provider_command_placeholders" in prompt

    spec = json.loads(Path(result["spec"]).read_text(encoding="utf-8"))
    assert "notes" in spec
    assert any("standin" in n or "prompt_package" in n for n in spec["notes"])


def test_ai_generated_host_file(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
    )
    run_dir = Path(packet["artifacts"]["run_dir"])
    # Build once to learn canvas size from prompt package path convention
    probe = build_wallpaper(run_dir, surface="desktop", background_method="procedural")
    assert probe["ok"]
    spec = json.loads(Path(probe["spec"]).read_text(encoding="utf-8"))
    w, h = spec["canvas"]["width"], spec["canvas"]["height"]

    # Synthetic "AI" background (distinct solid-ish procedural)
    host_bg = tmp_path / "host-ai-bg.png"
    rgb = procedural_background(w, h, seed=999, complexity=0.5, theme="solar")
    host_bg.write_bytes(write_rgb_png(w, h, rgb))

    result = build_wallpaper(
        run_dir,
        surface="desktop",
        background_method="ai_generated",
        background_path=host_bg,
        provider="host_file",
        model="local-diffusion-mock",
    )
    assert result["ok"] is True
    assert result["background_method"] == "ai_generated"
    assert result["provider"] == "host_file"
    spec2 = json.loads(Path(result["spec"]).read_text(encoding="utf-8"))
    assert spec2["generation"]["background_method"] == "ai_generated"
    assert spec2["generation"]["provider"] == "host_file"
    assert spec2["generation"]["model"] == "local-diffusion-mock"
    assert Path(spec2["generation"]["background_source"]).name == "host-ai-bg.png"


def test_ai_generated_host_command(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path / "run",
        kamea_encoding="latin_mod9_v1",
    )
    run_dir = Path(packet["artifacts"]["run_dir"])
    # Host script writes a valid RGB PNG at {out_path} using our writer via python
    helper = tmp_path / "fake_host.py"
    helper.write_text(
        f"""#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, {str(ROOT / "scripts")!r})
from stego_png import write_rgb_png
from wallpaper.composite import procedural_background
out = Path(sys.argv[1])
w, h = int(sys.argv[2]), int(sys.argv[3])
seed = int(sys.argv[4])
rgb = procedural_background(w, h, seed=seed, complexity=0.2, theme="lunar")
out.write_bytes(write_rgb_png(w, h, rgb))
""",
        encoding="utf-8",
    )
    cmd = (
        f"{sys.executable} {helper} {{out_path}} {{width}} {{height}} {{seed}}"
    )
    result = build_wallpaper(
        run_dir,
        surface="phone_home",
        background_method="ai_generated",
        provider_command=cmd,
        model="fake-host",
        require_ai=True,
    )
    assert result["ok"] is True, result
    assert result["background_method"] == "ai_generated"
    assert result["provider"] in ("host_command",)
    assert Path(result["background"]).is_file()


def test_require_ai_fails_without_host(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
    )
    run_dir = Path(packet["artifacts"]["run_dir"])
    try:
        build_wallpaper(
            run_dir,
            surface="phone_lock",
            background_method="ai_generated",
            require_ai=True,
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "ai_generated required" in str(exc)


def test_construct_wallpaper_one_shot(tmp_path: Path):
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "construct",
            "--intent",
            "I maintain calm focus",
            "--out",
            str(tmp_path / "out"),
            "--kamea-encoding",
            "latin_mod9_v1",
            "--wallpaper",
            "--surface",
            "phone_lock",
            "--wp-mode",
            "focus",
            "--theme",
            "mercurial",
            "--background-method",
            "ai_generated",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert "wallpapers" in out
    assert len(out["wallpapers"]) == 1
    assert out["wallpapers"][0]["ok"] is True
    assert Path(out["wallpapers"][0]["prompt"]).is_file()


def test_load_background_resize(tmp_path: Path):
    small = procedural_background(64, 64, seed=1, complexity=0.1, theme="neutral")
    p = tmp_path / "s.png"
    p.write_bytes(write_rgb_png(64, 64, small))
    rgb = load_background_image(p, 128, 96, allow_resize=True)
    assert rgb is not None
    assert len(rgb) == 128 * 96 * 3


def test_enrich_prompt_package_keys():
    pkg = enrich_prompt_package(
        {"prompt": "x", "negative": "y"},
        width=10,
        height=20,
        seed=3,
        surface="desktop",
        out_hint="/tmp/bg.png",
    )
    assert pkg["canvas"] == {"width": 10, "height": 20}
    assert pkg["seed"] == 3
    assert pkg["output_hint"] == "/tmp/bg.png"


def test_host_command_path_with_spaces_and_quotes_stays_one_argument(tmp_path: Path):
    """A path must never split into, or inject, extra provider arguments."""
    import json
    import sys

    from sigil_forge.wallpaper.providers import run_host_command

    odd = tmp_path / "my runs; --extra 'x'"
    odd.mkdir()
    out_path = odd / "bg.png"
    recorder = tmp_path / "rec.py"
    recorder.write_text(
        "import json, sys\n"
        "open(sys.argv[3], 'w').write(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    ok, _, err = run_host_command(
        f"{sys.executable} {recorder} --prompt {{prompt_path}} {{out_path}} -w {{width}}",
        prompt_path=odd / "p.json",
        out_path=out_path,
        width=8,
        height=8,
        seed=1,
        surface="desktop",
    )
    assert ok, err
    argv = json.loads(out_path.read_text())
    assert argv == ["--prompt", str(odd / "p.json"), str(out_path), "-w", "8"]
