"""png-stats: real LSB-plane statistics, no detector claim."""

import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from sigil_forge.png_stats import MAX_FILE_BYTES, NOTE, analyze_png
from sigil_forge.stego_envelope import pack_sf11
from sigil_forge.stego_png import embed_lsb, pack_payload, write_rgb_png
from sigil_forge.wallpaper.vault import pack_sf12

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = str(ROOT / "scripts" / "sigil_forge.py")
D = "ab" * 32
R = "cd" * 32


def _png(tmp_path, name, w, h, rgb):
    p = tmp_path / name
    p.write_bytes(write_rgb_png(w, h, bytes(rgb)))
    return p


def _random_rgb(n, seed=1234):
    rng = random.Random(seed)
    return bytes(rng.randrange(256) for _ in range(n))


def test_all_even_hand_computed(tmp_path):
    # 12 samples: six 0s, four 2s, two 4s. Pairs (0,1),(2,3),(4,5):
    # 36/6 + 16/4 + 4/2 = 12, three pairs used -> df 2.
    rgb = [0] * 6 + [2] * 4 + [4] * 2
    r = analyze_png(_png(tmp_path, "even.png", 4, 1, rgb))
    assert r["samples"] == 12
    assert r["lsb_ones"] == 0
    assert r["lsb_ones_ratio"] == 0.0
    assert r["chi_square_pairs"] == 12.0
    assert r["chi_square_df"] == 2


def test_random_differs_from_even(tmp_path):
    even = analyze_png(_png(tmp_path, "e.png", 32, 32, bytes(v & 0xFE for v in _random_rgb(3072))))
    rnd = analyze_png(_png(tmp_path, "r.png", 32, 32, _random_rgb(3072)))
    assert 0.45 < rnd["lsb_ones_ratio"] < 0.55
    assert even["lsb_ones"] == 0
    assert rnd["chi_square_pairs"] != even["chi_square_pairs"]
    assert rnd["chi_square_df"] == 127


def test_tiny_image_every_field(tmp_path):
    p = _png(tmp_path, "t.png", 2, 1, [1, 2, 3, 3, 3, 255])
    r = analyze_png(p)
    assert r == {
        "path": str(p),
        "width": 2,
        "height": 1,
        "samples": 6,
        "lsb_ones": 5,
        "lsb_ones_ratio": 0.833333,
        "lsb_ones_ratio_r": 1.0,
        "lsb_ones_ratio_g": 0.5,
        "lsb_ones_ratio_b": 1.0,
        # counts 1:1, 2:1, 3:3, 255:1 -> pairs (0,1)=1, (2,3)=4/4, (254,255)=1
        "chi_square_pairs": 3.0,
        "chi_square_df": 2,
        "header": None,
        "header_found": False,
        "note": NOTE,
    }


@pytest.mark.parametrize(
    "name,payload",
    [
        ("SF1", pack_payload(bytes.fromhex(D))),
        ("SF11", pack_sf11(intent_digest=D, sigil_root=R)),
        ("SF12", pack_sf12(intent_digest=D, sigil_root=R, sealed_blob={"k": "v"})),
    ],
)
def test_embedding_flips_header(tmp_path, name, payload):
    carrier = write_rgb_png(64, 64, _random_rgb(64 * 64 * 3, seed=7))
    before_p = tmp_path / "before.png"
    after_p = tmp_path / "after.png"
    before_p.write_bytes(carrier)
    after_p.write_bytes(embed_lsb(carrier, payload))
    before = analyze_png(before_p)
    after = analyze_png(after_p)
    assert before["header_found"] is False and before["header"] is None
    assert after["header_found"] is True and after["header"] == name
    assert after["lsb_ones"] != before["lsb_ones"]


def _run(*args, cwd=None, env=None):
    return subprocess.run(
        [sys.executable, SCRIPT, *args], capture_output=True, text=True, cwd=cwd, env=env
    )


def test_cli_json_equals_analyze(tmp_path):
    p = _png(tmp_path, "c.png", 8, 8, _random_rgb(192))
    r = _run("png-stats", str(p))
    assert r.returncode == 0
    assert json.loads(r.stdout) == analyze_png(p)


def test_cli_out_file_identical(tmp_path):
    p = _png(tmp_path, "c.png", 8, 8, _random_rgb(192))
    out = tmp_path / "sub" / "dir" / "stats.json"
    r = _run("png-stats", str(p), "--out", str(out))
    assert r.returncode == 0
    assert json.loads(out.read_text()) == json.loads(r.stdout) == analyze_png(p)


def _bad_inputs(tmp_path):
    notpng = tmp_path / "x.png"
    notpng.write_bytes(b"hello, not a png")
    big = tmp_path / "big.png"
    with open(big, "wb") as fh:
        fh.truncate(MAX_FILE_BYTES + 1)
    return [notpng, tmp_path / "missing.png", big]


def test_cli_errors_exit_one_without_output(tmp_path):
    for bad in _bad_inputs(tmp_path):
        out = tmp_path / "o" / f"{bad.name}.json"
        r = _run("png-stats", str(bad), "--out", str(out))
        assert r.returncode == 1, bad
        assert r.stdout == "", bad
        assert r.stderr.strip(), bad
        assert not out.exists() and not out.parent.exists(), bad


def test_cap_is_enforced_by_function(tmp_path):
    p = _png(tmp_path, "c.png", 2, 2, bytes(12))
    with pytest.raises(ValueError):
        analyze_png(p, max_bytes=10)


def test_help_wording_and_listing():
    r = _run("png-stats", "--help")
    assert r.returncode == 0
    assert "not a detector" in " ".join(r.stdout.split())
    assert "png-stats" in _run("help").stdout
    assert "png-stats" in _run("--help").stdout


def test_nothing_written_besides_out(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    img = _png(tmp_path, "c.png", 8, 8, _random_rgb(192))
    home = tmp_path / "home"
    state = tmp_path / "state"
    tmp = tmp_path / "tmp"
    for d in (home, state, tmp):
        d.mkdir()
    env = dict(
        os.environ,
        HOME=str(home),
        HERMES_HOME=str(home / ".hermes"),
        SIGIL_FORGE_STATE_DIR=str(state),
        TMPDIR=str(tmp),
    )

    def snap():
        return sorted(
            str(q.relative_to(tmp_path)) for q in tmp_path.rglob("*")
        )

    before = snap()
    r = _run("png-stats", str(img), cwd=work, env=env)
    assert r.returncode == 0
    assert snap() == before
    assert not any(q.suffix == ".pyc" for q in work.rglob("*"))
