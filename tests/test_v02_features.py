"""v0.2: layout PNG, polish package, open/unseal, goldens."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sigil_forge.construct import run as construct_run
from sigil_forge.crypto_payload import open_intent
from sigil_forge.fuse import build_layout
from sigil_forge.layout_raster import layout_to_png_bytes
from sigil_forge.normalize import normalize_intent
from sigil_forge.crypto_payload import intent_digest
from sigil_forge.stego_png import MAGIC, extract_lsb, unpack_payload
from sigil_forge.verify import run as verify_run

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"


def test_layout_raster_png_lsb_roundtrip(tmp_path: Path):
    n = normalize_intent("I maintain calm focus while shipping Sigil-Forge")
    d = intent_digest(n)
    lay = build_layout(n, d, square_override="saturn")
    png = layout_to_png_bytes(lay.monogram_points, lay.kamea_points)
    assert png.startswith(b"\x89PNG")

    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        out_root=tmp_path,
        square="saturn",
    )
    png_path = packet["artifacts"].get("png")
    assert png_path, "png_lsb should apply via layout_raster offline"
    assert Path(png_path).is_file()
    by_id = {c["id"]: c for c in packet["channels"]}
    assert by_id["png_lsb"]["status"] == "applied"
    assert "layout_raster" in by_id["png_lsb"]["detail"]

    raw = Path(png_path).read_bytes()
    # v0.12.1+: SF11 when sigil_root present; SF1 legacy still ok
    peek = extract_lsb(raw, 4)
    if peek == b"SF11":
        from sigil_forge.stego_envelope import unpack_envelope

        payload = extract_lsb(raw, 4 + 1 + 1 + 32 + 32 + 4)
        env = unpack_envelope(payload)
        assert env["intent_digest"] == packet["intent_digest"]
        assert env["sigil_root"] == packet.get("sigil_root")
    else:
        payload = extract_lsb(raw, 4 + 32)
        assert payload[:4] == MAGIC
        dig, sealed = unpack_payload(payload)
        assert dig.hex() == packet["intent_digest"]
        assert sealed is None

    v = verify_run(png_path)
    assert v["ok"] is True
    assert v["intent_digest"] == packet["intent_digest"]


def test_construct_polish_writes_prompt_and_gen_seed(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        out_root=tmp_path,
        square="saturn",
        write_polish=True,
        polish_style="ink on parchment",
    )
    by_id = {c["id"]: c for c in packet["channels"]}
    assert by_id["gen_seed"]["status"] == "applied"
    path = packet["artifacts"].get("polish_prompt_path")
    assert path and Path(path).is_file()
    pkg = json.loads(Path(path).read_text(encoding="utf-8"))
    assert set(pkg) >= {"prompt", "negative", "seed", "geometry_lock"}
    assert pkg["seed"] == int(packet["intent_digest"][:8], 16)
    assert "ink" in pkg["prompt"].lower() or "parchment" in pkg["prompt"].lower()


def test_open_unseals_packet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from sigil_forge.construct import PASSPHRASE_ENV

    monkeypatch.setenv(PASSPHRASE_ENV, "v02-test-secret")
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        out_root=tmp_path,
        square="saturn",
        seal_packet=True,
        passphrase=None,
    )
    sealed = packet["sealed_intent"]
    text = open_intent(sealed, "v02-test-secret")
    assert "calm focus" in text.lower()

    # CLI open
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "open",
            packet["artifacts"]["packet_json"],
            "--json",
        ],
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), PASSPHRASE_ENV: "v02-test-secret"},
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert "calm" in out["intent"].lower()


def test_golden_intents_match_engine():
    gold_dir = ROOT / "examples" / "intents"
    files = sorted(gold_dir.glob("*.json"))
    assert len(files) >= 3, f"expected ≥3 goldens, found {len(files)}"
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        n = normalize_intent(data["intent"])
        assert n == data["normalized_intent"], path.name
        from sigil_forge.spare import reduce_letters

        assert reduce_letters(n) == data["spare_letters"], path.name
        assert intent_digest(n) == data["intent_digest"], path.name
