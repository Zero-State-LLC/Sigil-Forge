"""Wallpaper framework: immutable glyph, composition, receipts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sigil_forge.construct import run as construct_run
from sigil_forge.wallpaper.pipeline import build_wallpaper
from sigil_forge.wallpaper.seed import file_sha256, wallpaper_seed
from sigil_forge.wallpaper.spec import build_wallpaper_spec

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"


def test_wallpaper_seed_stable():
    a = wallpaper_seed(
        intent_digest="ab" * 32,
        surface="phone_lock",
        mode="focus",
        symbolic_theme="mercurial",
    )
    b = wallpaper_seed(
        intent_digest="ab" * 32,
        surface="phone_lock",
        mode="focus",
        symbolic_theme="mercurial",
    )
    c = wallpaper_seed(
        intent_digest="ab" * 32,
        surface="desktop",
        mode="focus",
        symbolic_theme="mercurial",
    )
    assert a == b
    assert a != c


def test_build_wallpaper_preserves_glyph_digest(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        out_root=tmp_path,
        square="saturn",
        kamea_encoding="latin_mod9_v1",
    )
    run_dir = Path(packet["artifacts"]["run_dir"])
    glyph = run_dir / "glyph.svg"
    before = file_sha256(str(glyph))

    result = build_wallpaper(
        run_dir,
        surface="phone_lock",
        mode="focus",
        intensity="balanced",
        symbolic_theme="mercurial",
        background_method="procedural",
    )
    assert result["ok"] is True
    assert result["geometry_preserved"] is True
    after = file_sha256(str(glyph))
    assert before == after  # canonical immutable

    spec_path = Path(result["spec"])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["schema_version"] == "1.0.0"
    assert spec["privacy"]["plaintext_intent_allowed"] is False
    assert spec["source"]["glyph_digest"] == before
    assert Path(result["wallpaper"]).is_file()
    assert Path(result["receipt"]).is_file()

    receipt = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    assert receipt["status"] == "verified"
    assert receipt["geometry_preserved"] is True
    assert receipt["plaintext_scan"] == "pass"

    # Prompt does not invent glyph
    prompt = json.loads(
        (run_dir / "wallpaper" / "background-prompt-phone_lock.json").read_text(
            encoding="utf-8"
        )
    )
    pl = prompt["prompt"].lower()
    assert (
        "added separately" in pl
        or "composited later" in pl
        or "do not attempt to invent" in pl
        or "vector sigil" in pl
    )
    assert "text" in prompt["negative"].lower()


def test_desktop_and_phone_home_composition(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
    )
    run_dir = Path(packet["artifacts"]["run_dir"])
    for surface in ("phone_home", "desktop"):
        r = build_wallpaper(run_dir, surface=surface, mode="stealth" if surface == "phone_home" else "focus")
        assert r["ok"] is True
        spec = build_wallpaper_spec(run_dir, surface=surface)
        assert spec["canvas"]["width"] >= 512
        assert 0 < spec["composition"]["scale"] <= 1


def test_wallpaper_cli(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
    )
    run_dir = packet["artifacts"]["run_dir"]
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "wallpaper",
            "--run",
            run_dir,
            "--surface",
            "desktop",
            "--mode",
            "ambient",
            "--theme",
            "lunar",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    out = json.loads(r.stdout)
    assert out["ok"] is True
