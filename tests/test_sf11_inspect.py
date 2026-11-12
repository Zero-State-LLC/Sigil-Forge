"""SF11 stego envelope, verify dual path, inspect, wallpaper root binding."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sigil_forge.construct import run as construct_run
from sigil_forge.stego_envelope import pack_sf11, unpack_envelope
from sigil_forge.stego_png import embed_lsb, write_rgb_png
from sigil_forge.stego_svg import extract as extract_svg
from sigil_forge.verify import run as verify_run
from sigil_forge.wallpaper.pipeline import build_wallpaper

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"


def test_sf11_pack_unpack_roundtrip():
    d = "ab" * 32
    r = "cd" * 32
    payload = pack_sf11(intent_digest=d, sigil_root=r)
    assert payload[:4] == b"SF11"
    env = unpack_envelope(payload)
    assert env["format"] == "SF11"
    assert env["intent_digest"] == d
    assert env["sigil_root"] == r


def test_sf11_png_lsb_and_verify(tmp_path: Path):
    rgb = bytes([40, 40, 40]) * (128 * 128)
    png = write_rgb_png(128, 128, rgb)
    d = "11" * 32
    r = "22" * 32
    payload = pack_sf11(intent_digest=d, sigil_root=r)
    out = embed_lsb(png, payload)
    p = tmp_path / "g.png"
    p.write_bytes(out)
    res = verify_run(p)
    assert res["ok"] is True
    assert res["intent_digest"] == d
    assert res["sigil_root"] == r
    assert res["stego_format"] == "SF11"


def test_construct_sf11_on_png_and_svg(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="sf11-pass",
        proof="commitment",
        kdf="pbkdf2-sha256",
    )
    run = Path(packet["artifacts"]["run_dir"])
    root = packet["sigil_root"]
    digest = packet["intent_digest"]
    # PNG
    png_res = verify_run(run / "glyph.png")
    assert png_res["ok"] is True
    assert png_res["intent_digest"] == digest
    assert png_res["sigil_root"] == root
    # SVG
    svg_res = verify_run(run / "glyph.svg")
    assert svg_res["ok"] is True
    assert svg_res.get("sigil_root") == root
    got = extract_svg((run / "glyph.svg").read_text(encoding="utf-8"))
    assert got.get("sigil_root") == root


def test_legacy_sf1_still_verifies(tmp_path: Path):
    # construct always SF11 now when root present — build raw SF1 manually
    from sigil_forge.stego_png import pack_payload

    rgb = bytes([20, 20, 20]) * (64 * 64)
    png = write_rgb_png(64, 64, rgb)
    d = bytes.fromhex("33" * 32)
    out = embed_lsb(png, pack_payload(d))
    p = tmp_path / "legacy.png"
    p.write_bytes(out)
    res = verify_run(p)
    assert res["ok"] is True
    assert res["intent_digest"] == "33" * 32
    assert res.get("stego_format") == "SF1"


def test_wallpaper_receipt_binds_root(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="wp-pass",
        proof="commitment",
        kdf="pbkdf2-sha256",
    )
    run = Path(packet["artifacts"]["run_dir"])
    wr = build_wallpaper(run, surface="phone_lock", background_method="procedural")
    assert wr["ok"] is True
    receipt = json.loads(Path(wr["receipt"]).read_text(encoding="utf-8"))
    assert receipt.get("sigil_root") == packet["sigil_root"]
    assert receipt.get("intent_commitment") == packet["intent_commitment"]["value"]
    assert receipt.get("intent_digest") == packet["intent_digest"]
    # wallpaper PNG should verify SF11
    wres = verify_run(Path(wr["wallpaper"]))
    assert wres["ok"] is True
    assert wres.get("sigil_root") == packet["sigil_root"]


def test_inspect_cli(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="ins-pass",
        proof="commitment",
        kdf="pbkdf2-sha256",
    )
    run = packet["artifacts"]["run_dir"]
    r = subprocess.run(
        [sys.executable, str(CLI), "inspect", f"{run}/glyph.png"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["sigil_root"] == packet["sigil_root"]
    assert out["carrier"] == "PNG"
