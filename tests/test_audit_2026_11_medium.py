"""Regressions for the medium findings of the November 2026 audit of v0.18.0."""

from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

import pytest

from sigil_forge import construct, safe_io, stego_svg
from sigil_forge import stego_png
from sigil_forge.construct import run as construct_run
from sigil_forge.inspect_artifact import inspect_path
from sigil_forge.receipt import read_ledger
from sigil_forge.verify import run as verify_run
from sigil_forge.wallpaper.pipeline import build_wallpaper
from sigil_forge.wallpaper.vault import open_wallpaper_vault

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / "scripts" / "sigil_forge.py")]
INTENT = "I maintain calm focus"
OTHER = "I finish what I start"
PW = "pw-test"


def cli(*args: str, passphrase: str | None = PW, debug: bool = False):
    env = dict(os.environ)
    env.pop("SIGIL_FORGE_DEBUG", None)
    if passphrase:
        env["SIGIL_FORGE_PASSPHRASE"] = passphrase
    if debug:
        env["SIGIL_FORGE_DEBUG"] = "1"
    return subprocess.run([*CLI, *args], capture_output=True, text=True, env=env)


def _error(result) -> str:
    """The JSON error a command printed; fails if it printed a traceback."""
    assert "Traceback" not in result.stderr + result.stdout, result.stderr[-600:]
    return json.loads(result.stderr.strip().splitlines()[-1])["error"]


# ------------------------------------------------- shared bounded reader


def test_read_regular_refuses_everything_but_a_small_plain_file(tmp_path):
    good = tmp_path / "good.txt"
    good.write_bytes(b"hello")
    assert safe_io.read_regular(good, 5) == b"hello"
    assert safe_io.read_text(good, 100) == "hello"
    with pytest.raises(safe_io.UnsafeFile):
        safe_io.read_regular(good, 4)
    with pytest.raises(OSError):
        safe_io.read_regular(tmp_path, 100)
    with pytest.raises(OSError):
        safe_io.read_regular(tmp_path / "missing", 100)
    if hasattr(os, "symlink"):
        link = tmp_path / "link.txt"
        link.symlink_to(good)
        with pytest.raises(safe_io.UnsafeFile):
            safe_io.read_regular(link, 100)
    if hasattr(os, "mkfifo"):
        fifo = tmp_path / "fifo"
        os.mkfifo(fifo)
        start = time.monotonic()
        with pytest.raises(OSError):
            safe_io.read_regular(fifo, 100)
        assert time.monotonic() - start < 5


def test_storyboard_and_manifest_use_the_one_reader():
    from sigil_forge import forge_manifest, storyboard

    assert storyboard.read_regular is safe_io.read_regular
    assert forge_manifest.read_regular is safe_io.read_regular


# ------------------------------------------------------- A. open checks


@pytest.fixture(scope="module")
def sealed_runs(tmp_path_factory):
    out = []
    for name, intent in (("a", INTENT), ("b", OTHER)):
        root = tmp_path_factory.mktemp(name)
        packet = construct_run(intent, out_root=root, passphrase=PW, seal_packet=True, proof="commitment")
        out.append(Path(packet["artifacts"]["run_dir"]))
    return out


def _copy(run: Path, tmp_path: Path) -> Path:
    import shutil

    dest = tmp_path / "run"
    shutil.copytree(run, dest)
    return dest


def test_open_returns_the_intent_of_an_untouched_sealed_packet(sealed_runs):
    r = cli("open", str(sealed_runs[0] / "forge-packet.json"))
    assert r.returncode == 0 and r.stdout.strip() == INTENT


def test_open_refuses_a_sealed_part_from_another_run(sealed_runs, tmp_path):
    """Same passphrase on both, so decryption succeeds; only the digest check can object."""
    run = _copy(sealed_runs[0], tmp_path)
    packet = json.loads((run / "forge-packet.json").read_text(encoding="utf-8"))
    other = json.loads((sealed_runs[1] / "forge-packet.json").read_text(encoding="utf-8"))
    packet["sealed_intent"] = other["sealed_intent"]
    (run / "forge-packet.json").write_text(json.dumps(packet), encoding="utf-8")
    r = cli("open", str(run / "forge-packet.json"), "--json")
    assert r.returncode == 1
    assert "different run" in _error(r)
    assert OTHER not in r.stdout + r.stderr  # the foreign intent is not handed over as this run's


def test_open_capsule_refuses_a_capsule_whose_digest_was_changed(sealed_runs, tmp_path):
    run = _copy(sealed_runs[0], tmp_path)
    path = run / "intent-capsule.json"
    assert cli("open", str(path), "--capsule").stdout.strip() == INTENT
    capsule = json.loads(path.read_text(encoding="utf-8"))
    other = json.loads((sealed_runs[1] / "intent-capsule.json").read_text(encoding="utf-8"))
    capsule["compatibility"]["intent_digest"] = other["compatibility"]["intent_digest"]
    path.write_text(json.dumps(capsule), encoding="utf-8")
    r = cli("open", str(path), "--capsule")
    assert r.returncode == 1 and "does not match" in _error(r)


@pytest.mark.parametrize("content", ["[]", "5", '"text"', "{not json", b"\xff\xfe\x00"])
def test_open_reports_unreadable_files_cleanly(tmp_path, content):
    path = tmp_path / "thing.json"
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    r = cli("open", str(path))
    assert r.returncode == 1 and _error(r)


# ------------------------------------------- B. runs never overwrite runs


def test_same_run_id_gets_a_new_folder_and_the_first_run_is_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(construct, "make_run_id", lambda digest, when=None: "20260101T000000Z-abcdef01")
    first = construct_run(INTENT, out_root=tmp_path)
    first_dir = Path(first["artifacts"]["run_dir"])
    before = {p.name: p.read_bytes() for p in first_dir.iterdir() if p.is_file()}

    second = construct_run(INTENT, out_root=tmp_path)
    third = construct_run(INTENT, out_root=tmp_path)

    assert first["artifacts"]["run_id"] == "20260101T000000Z-abcdef01"
    assert second["artifacts"]["run_id"] == "20260101T000000Z-abcdef01-2"
    assert third["artifacts"]["run_id"] == "20260101T000000Z-abcdef01-3"
    assert {p.name: p.read_bytes() for p in first_dir.iterdir() if p.is_file()} == before
    for packet in (first, second, third):
        run = Path(packet["artifacts"]["run_dir"])
        assert run.name == packet["artifacts"]["run_id"]
        assert verify_run(run / "glyph.svg")["ok"] is True
        if os.name == "posix":
            assert run.stat().st_mode & 0o777 == 0o700


def test_a_failed_forge_releases_the_folder_it_claimed(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("simulated failure late in the forge")

    monkeypatch.setattr(construct, "write_packet_files", boom)
    with pytest.raises(RuntimeError):
        construct_run(INTENT, out_root=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_forges_running_at_once_each_keep_their_run(tmp_path):
    procs = [
        subprocess.Popen(
            [*CLI, "construct", "--intent", "same second test", "--out", str(tmp_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for _ in range(4)
    ]
    outs = [p.communicate() for p in procs]
    assert [p.returncode for p in procs] == [0, 0, 0, 0], [e for _, e in outs]
    ids = {json.loads(o)["run_id"] for o, _ in outs}
    assert len(ids) == 4
    assert {p.name for p in tmp_path.iterdir()} == ids
    for run_id in ids:
        assert verify_run(tmp_path / run_id / "glyph.svg")["ok"] is True


# --------------------------------------------- C. hostile SVG and PNG


def test_scanning_gives_what_the_old_regex_gave(tmp_path):
    """The linear scan replaced a lazy regex; same answers on ordinary input."""
    old = re.compile(r"<sf:payload\b[^>]*>(.*?)</sf:payload>", re.IGNORECASE | re.DOTALL)
    packet = construct_run(INTENT, out_root=tmp_path)
    real = (Path(packet["artifacts"]["run_dir"]) / "glyph.svg").read_text(encoding="utf-8")
    samples = [
        real,
        "<svg><sf:payload>abc</sf:payload></svg>",
        '<svg><SF:Payload a="1">abc\n def</SF:PAYLOAD></svg>',
        "<svg><sf:payload>one</sf:payload><sf:payload>two</sf:payload></svg>",
        "<svg><sf:payload>never closed</svg>",
        "<svg><sf:payloadx>no</sf:payloadx><sf:payload>yes</sf:payload></svg>",
        "<svg></svg>",
        "<svg><sf:payload></sf:payload></svg>",
    ]
    for text in samples:
        m = old.search(text)
        assert stego_svg._element_text(text, text.lower(), "sf:payload") == (m.group(1) if m else None)
    old_attr = re.compile(r'\b(?:points|d)=([\'"])(.*?)\1', re.IGNORECASE | re.DOTALL)
    for text in [real, '<p d="1 2" points=\'3,4\' D="5"/>', '<p d="1 2', "<p id='x' d='1'/>"]:
        assert list(stego_svg._geometry_attr_values(text)) == [m.group(2) for m in old_attr.finditer(text)]


@pytest.mark.parametrize(
    "body",
    ["<sf:payload>" * 300_000, ' d="' * 800_000, "<payload " * 400_000, " points='" * 400_000],
)
def test_a_crafted_svg_cannot_stall_verify(tmp_path, body):
    """These took minutes: the old patterns were quadratic on unterminated input."""
    path = tmp_path / "crafted.svg"
    path.write_text("<svg>" + body + "</svg>", encoding="utf-8")
    assert path.stat().st_size <= safe_io.MAX_SVG_BYTES
    start = time.monotonic()
    got = verify_run(path)
    inspected = inspect_path(path)
    assert time.monotonic() - start < 20
    assert got["ok"] is False and inspected["ok"] is False


def test_oversized_binary_and_linked_svg_are_refused_cleanly(tmp_path):
    big = tmp_path / "big.svg"
    big.write_bytes(b"<svg>" + b" " * safe_io.MAX_SVG_BYTES + b"</svg>")
    binary = tmp_path / "binary.svg"
    binary.write_bytes(b"\xff\xfe<svg>")
    for path in (big, binary):
        got = verify_run(path)
        assert got["ok"] is False and "svg read failed" in got["detail"]
        assert inspect_path(path)["ok"] is False
    if hasattr(os, "symlink"):
        packet = construct_run(INTENT, out_root=tmp_path / "r")
        link = tmp_path / "link.svg"
        link.symlink_to(Path(packet["artifacts"]["run_dir"]) / "glyph.svg")
        assert verify_run(link)["ok"] is False


def test_infinite_and_nan_coordinates_do_not_raise(tmp_path):
    path = tmp_path / "inf.svg"
    path.write_text('<svg><path d="M 1e999 0 -1e999 nan 5.001"/></svg>', encoding="utf-8")
    assert verify_run(path)["ok"] is False
    for value in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(ValueError):
            stego_svg._decode_float_bit(value)


def _png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    raw = zlib.compress(b"\x00" * (height * (1 + width * 3)), 9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", raw)
        + chunk(b"IEND", b"")
    )


def test_a_decompression_bomb_png_is_refused_before_it_is_inflated(tmp_path):
    """A 300 KB file claiming 100 megapixels used to cost over a gigabyte."""
    bomb = tmp_path / "bomb.png"
    bomb.write_bytes(_png(9990, 9990))
    assert bomb.stat().st_size < 400_000
    start = time.monotonic()
    for got in (verify_run(bomb), inspect_path(bomb)):
        assert got["ok"] is False and "unsupported PNG size" in got["detail"]
    assert time.monotonic() - start < 5
    r = cli("png-stats", str(bomb))
    assert r.returncode != 0 and "Traceback" not in r.stderr


def test_pixel_limit_still_covers_every_real_wallpaper():
    from sigil_forge.wallpaper.profiles import SURFACE_CANVAS

    largest = max(p["width"] * p["height"] for p in SURFACE_CANVAS.values())
    assert largest * 4 < stego_png.MAX_PNG_PIXELS  # room to spare
    assert 7680 * 4320 < stego_png.MAX_PNG_PIXELS < 100_000_000  # 8K fits; the old limit does not


def test_png_readers_cap_the_file_size(tmp_path, monkeypatch):
    monkeypatch.setattr("sigil_forge.verify.MAX_PNG_FILE_BYTES", 1000)
    monkeypatch.setattr("sigil_forge.inspect_artifact.MAX_PNG_FILE_BYTES", 1000)
    monkeypatch.setattr("sigil_forge.wallpaper.vault.MAX_PNG_FILE_BYTES", 1000)
    path = tmp_path / "large.png"
    path.write_bytes(_png(64, 64) + b"\x00" * 2000)
    assert verify_run(path)["ok"] is False
    assert inspect_path(path)["ok"] is False
    with pytest.raises(OSError):
        open_wallpaper_vault(path, PW)


# --------------------------------------------------- D. phoneme file


def test_phoneme_file_is_owner_only(tmp_path):
    packet = construct_run("zephyr quill mordant", out_root=tmp_path, phonetic=True)
    path = Path(packet["artifacts"]["phoneme_sequence_path"])
    data = json.loads(path.read_text(encoding="utf-8"))
    # Pins why it is private: the intent can be read back from it.
    letters = re.sub(r"[^a-z]", "", str(data.get("mantric_form", "")).lower())
    assert letters == "zephyrquillmordant"
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


# ------------------------------------------------ E. vault honesty


def test_asking_for_a_vault_without_a_passphrase_is_an_error(tmp_path):
    packet = construct_run(INTENT, out_root=tmp_path)
    run = Path(packet["artifacts"]["run_dir"])
    with pytest.raises(ValueError, match="needs a passphrase"):
        build_wallpaper(run, surface="phone_lock", embedded_payload="vault")
    auto = build_wallpaper(run, surface="phone_lock")  # auto still works unsealed
    assert auto["ok"] is True and auto["vault_status"] == "skipped"
    r = cli("construct", "--intent", INTENT, "--wallpaper", "--embed", "vault",
            "--out", str(tmp_path / "cli"), passphrase=None)
    assert r.returncode == 1 and "needs a passphrase" in _error(r)


def test_a_vault_made_from_a_sealed_packet_holds_the_intent(sealed_runs, tmp_path):
    run = _copy(sealed_runs[0], tmp_path)
    packet = json.loads((run / "forge-packet.json").read_text(encoding="utf-8"))
    assert not packet.get("intent") and not packet.get("normalized_intent")
    result = build_wallpaper(run, surface="phone_lock", passphrase=PW, embedded_payload="vault")
    assert result["vault_status"] == "embedded"
    opened = open_wallpaper_vault(result["wallpaper"], PW)
    assert opened["intent"] == INTENT
    r = cli("open", "--wallpaper", result["wallpaper"])
    assert r.returncode == 0 and r.stdout.strip() == INTENT
    assert cli("open", result["wallpaper"]).stdout.strip() == INTENT  # a .png needs no flag


def test_a_vault_cannot_be_built_from_a_sealed_packet_with_the_wrong_passphrase(sealed_runs, tmp_path):
    run = _copy(sealed_runs[0], tmp_path)
    with pytest.raises(ValueError, match="does not open it"):
        build_wallpaper(run, surface="phone_lock", passphrase="not-the-passphrase", embedded_payload="vault")


# ------------------------------------- F. clean errors, never a traceback


def _bad_inputs(tmp_path: Path) -> list[list[str]]:
    a_file = tmp_path / "a-file"
    a_file.write_text("x", encoding="utf-8")
    binary = tmp_path / "binary.jsonl"
    binary.write_bytes(b"\xff\xfe")
    array = tmp_path / "array.jsonl"
    array.write_text("[1, 2]\n", encoding="utf-8")
    d, f, b = str(tmp_path), str(a_file), str(binary)
    return [
        ["construct", "--intent", INTENT, "--out", f],
        ["policy", "check", "--file", str(tmp_path / "missing")],
        ["policy", "check", "--file", d],
        ["policy", "check", "--file", b],
        ["ledger", "--ledger", b],
        ["ledger", "--ledger", str(array)],
        ["open", b],
        ["open", d],
        ["verify", d],
        ["verify", f],
        ["inspect", f],
        ["png-stats", f],
        ["png-stats", d],
        ["verify-proof", f],
        ["verify-root", f],
        ["storyboard-verify", f],
        ["storyboard", "--intents-file", b],
        ["wallpaper", "--run", f],
        ["wizard", "--session", "no-such-session", "--next"],
        ["wizard", "--apply", b],
    ]


def test_no_command_prints_a_traceback_on_bad_input(tmp_path):
    for argv in _bad_inputs(tmp_path):
        r = cli(*argv)
        assert "Traceback" not in r.stderr + r.stdout, f"{argv[:2]}: {r.stderr[-400:]}"
        assert r.returncode in (0, 1, 2), argv


def test_unexpected_errors_become_one_json_line_and_debug_shows_the_traceback(tmp_path):
    target = tmp_path / "a-file"
    target.write_text("x", encoding="utf-8")
    r = cli("construct", "--intent", INTENT, "--out", str(target))
    assert r.returncode == 1
    error = _error(r)
    assert error.startswith(("FileExistsError", "NotADirectoryError"))
    assert "\n" not in error
    debug = cli("construct", "--intent", INTENT, "--out", str(target), debug=True)
    assert debug.returncode != 0 and "Traceback" in debug.stderr


def test_ledger_limit_of_zero_or_less_returns_nothing(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text("".join(json.dumps({"n": i}) + "\n" for i in range(5)) + "[1]\n", encoding="utf-8")
    assert [e["n"] for e in read_ledger(path, limit=2)] == [4]  # the array line is skipped
    assert [e["n"] for e in read_ledger(path, limit=3)] == [3, 4]
    assert read_ledger(path, limit=0) == []
    assert read_ledger(path, limit=-1) == []


def test_wizard_reports_a_non_text_intent_instead_of_crashing():
    from sigil_forge import wizard

    sid = wizard.create_session("quick")["session_id"]
    out = wizard.session_next(sid, merge_answers={"intent": 5})
    assert out["ignored_answers"] == ["intent (not text)"]
    assert (out.get("step") or {}).get("id") == "intent"  # still waiting for a real one
