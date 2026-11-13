"""Storyboard: ordered forge runs plus a digest-only index, all-or-nothing."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from sigil_forge import construct
from sigil_forge.cli import _read_intents_file
from sigil_forge.normalize import normalize_intent
from sigil_forge.storyboard import StoryboardUsageError, build_storyboard
from sigil_forge.verify import run as verify_run

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / "scripts" / "sigil_forge.py")]

A = "I maintain calm focus while shipping"
B = "I rest and recover after long work"
C = "I welcome steady learning"
HARM = "I will murder my neighbor tomorrow"
SEAL = "forge an Enochian seal for the air tablet"


def _empty(root: Path) -> bool:
    return not root.exists() or not any(root.iterdir())


def test_two_intents_make_two_verified_runs(tmp_path):
    board = build_storyboard([A, B], out_root=tmp_path)
    frames = board["frames"]
    assert [f["index"] for f in frames] == [1, 2]
    assert frames[0]["intent_digest"] != frames[1]["intent_digest"]
    assert frames[0]["sigil_root"] != frames[1]["sigil_root"]
    for f in frames:
        run_dir = tmp_path / f["run_dir"]
        assert run_dir.is_dir()
        assert (run_dir / "forge-packet.json").is_file()
        assert (run_dir / "glyph.svg").is_file()
        v = verify_run(run_dir / "glyph.svg")
        assert v["ok"] is True
        assert v["intent_digest"] == f["intent_digest"]
    assert Path(board["index_path"]).is_file()


def test_board_id_depends_on_order(tmp_path):
    one = build_storyboard([A, B], out_root=tmp_path)
    again = build_storyboard([A, B], out_root=tmp_path)
    rev = build_storyboard([B, A], out_root=tmp_path)
    assert one["board_id"] == again["board_id"]
    assert rev["board_id"] != one["board_id"]
    assert len(one["board_id"]) == 16


def test_index_is_public_digests_only(tmp_path):
    board = build_storyboard([A, B], out_root=tmp_path)
    text = Path(board["index_path"]).read_text(encoding="utf-8")
    low = text.lower()
    for intent in (A, B):
        assert intent not in text
        assert normalize_intent(intent) not in low
    doc = json.loads(text)
    assert doc["schema"] == "sigil-forge-storyboard/1"
    assert doc["board_id"] == board["board_id"]

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)

    for k in keys(doc):
        if k == "intent_digest":
            continue
        assert not any(w in k.lower() for w in ("intent", "nonce", "passphrase"))
    assert "nonce" not in low and "passphrase" not in low


def test_harmful_frame_refuses_everything(tmp_path):
    with pytest.raises(ValueError) as storyboard_err:
        build_storyboard([A, HARM, C], out_root=tmp_path)
    with pytest.raises(ValueError) as construct_err:
        construct.run(HARM, out_root=tmp_path / "probe")
    msg = str(storyboard_err.value)
    assert str(construct_err.value) in msg
    assert "frame 2" in msg
    assert "murder" not in msg and "neighbor" not in msg
    assert _empty(tmp_path)


def test_authority_seal_frame_refused(tmp_path):
    with pytest.raises(ValueError) as ei:
        build_storyboard([A, SEAL], out_root=tmp_path)
    assert "AUTHORITY_SEAL_EXCLUDED" in str(ei.value)
    assert "frame 2" in str(ei.value)
    assert _empty(tmp_path)


@pytest.mark.parametrize(
    "intents",
    [[], [f"intent number {i} about steady work" for i in range(13)], ["   "], [A, "\n\t "]],
)
def test_bad_counts_and_blank_intents(tmp_path, intents):
    with pytest.raises(StoryboardUsageError):
        build_storyboard(intents, out_root=tmp_path)
    assert _empty(tmp_path)


def test_twelve_is_allowed_and_duplicates_rejected(tmp_path):
    with pytest.raises(StoryboardUsageError):
        build_storyboard([A, "  " + A.upper()], out_root=tmp_path)
    assert _empty(tmp_path)
    board = build_storyboard(
        [f"frame {i} holds a different steady thought" for i in range(12)],
        out_root=tmp_path,
    )
    assert len(board["frames"]) == 12


def test_mid_run_failure_rolls_back(tmp_path, monkeypatch):
    real = construct.run
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(*a, **kw)

    monkeypatch.setattr(construct, "run", flaky)
    with pytest.raises(RuntimeError):
        build_storyboard([A, B, C], out_root=tmp_path)
    assert calls["n"] == 2
    assert [p for p in tmp_path.iterdir() if p.is_dir()] == []


def test_mid_run_failure_keeps_prior_runs(tmp_path, monkeypatch):
    existing = construct.run(C, out_root=tmp_path)
    real = construct.run
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(*a, **kw)

    monkeypatch.setattr(construct, "run", flaky)
    with pytest.raises(RuntimeError):
        build_storyboard([A, B], out_root=tmp_path)
    assert Path(existing["artifacts"]["run_dir"]).is_dir()
    assert [p.name for p in tmp_path.iterdir()] == [existing["artifacts"]["run_id"]]


def test_intents_file_skips_comments_and_blanks(tmp_path):
    f = tmp_path / "i.txt"
    f.write_text(f"# title\n\n{A}\n   \n  # note\n{B}\n", encoding="utf-8")
    assert _read_intents_file(f) == [A, B]


def test_intents_file_over_cap_refused(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("a" * (64 * 1024 + 1), encoding="utf-8")
    with pytest.raises(ValueError):
        _read_intents_file(f)


def _cli(args, env_extra=None):
    env = dict(os.environ)
    env.pop("SIGIL_FORGE_PASSPHRASE", None)
    env.update(env_extra or {})
    return subprocess.run(
        CLI + args, capture_output=True, text=True, env=env, cwd=str(ROOT)
    )


def test_cli_ok(tmp_path):
    out = tmp_path / "out"
    r = _cli(["storyboard", "--intent", A, "--intent", B, "--out", str(out)])
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    assert doc["ok"] is True
    assert len(doc["frames"]) == 2
    assert Path(doc["index_path"]).is_file()
    assert A not in Path(doc["index_path"]).read_text(encoding="utf-8")


def test_cli_intents_file_then_intent(tmp_path):
    f = tmp_path / "i.txt"
    f.write_text(f"# c\n{A}\n", encoding="utf-8")
    out = tmp_path / "out"
    r = _cli(["storyboard", "--intents-file", str(f), "--intent", B, "--out", str(out)])
    assert r.returncode == 0, r.stderr
    frames = json.loads(r.stdout)["frames"]
    assert len(frames) == 2
    direct = build_storyboard([A, B], out_root=tmp_path / "direct")
    assert [x["intent_digest"] for x in frames] == [
        x["intent_digest"] for x in direct["frames"]
    ]


def test_cli_refusal_writes_nothing(tmp_path):
    out = tmp_path / "out"
    r = _cli(["storyboard", "--intent", A, "--intent", HARM, "--out", str(out)])
    assert r.returncode == 1
    assert json.loads(r.stderr)["ok"] is False
    assert "murder" not in r.stderr
    assert _empty(out)


def test_cli_usage_errors_exit_2(tmp_path):
    out = tmp_path / "out"
    r = _cli(["storyboard", "--out", str(out)])
    assert r.returncode == 2
    assert _empty(out)


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_cli_default_paths_are_private(tmp_path):
    state = tmp_path / "state"
    r = _cli(
        ["storyboard", "--intent", A, "--intent", B],
        {"SIGIL_FORGE_STATE_DIR": str(state)},
    )
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    index = Path(doc["index_path"])
    sb = state / "products" / "storyboards"
    assert index.parent == sb.resolve() or index.parent == sb
    assert stat.S_IMODE(os.stat(sb).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(index).st_mode) == 0o600


def test_help_lists_storyboard():
    r = _cli(["help"])
    assert r.returncode == 0
    assert "storyboard" in r.stdout


# ------------------------------------------------- sheet, board root, verify

import base64  # noqa: E402
import hashlib  # noqa: E402
import re  # noqa: E402

from sigil_forge import storyboard as sb  # noqa: E402
from sigil_forge.storyboard import verify_index, verify_sheet, verify_storyboard  # noqa: E402


@pytest.fixture(scope="module")
def board(tmp_path_factory):
    root = tmp_path_factory.mktemp("board")
    return root, build_storyboard([A, B, C], out_root=root)


def _copy_board(board, tmp_path) -> tuple[Path, Path, Path]:
    import shutil

    root, built = board
    dest = tmp_path / "copy"
    shutil.copytree(root, dest)
    index = dest / "storyboards" / Path(built["index_path"]).name
    sheet = dest / "storyboards" / Path(built["sheet_path"]).name
    return dest, index, sheet


def test_board_writes_a_sheet_and_a_root(board):
    root, built = board
    index = json.loads(Path(built["index_path"]).read_text(encoding="utf-8"))
    sheet = Path(built["sheet_path"])
    assert sheet.name == f"storyboard-{built['board_id']}.svg"
    assert re.fullmatch(r"[0-9a-f]{64}", index["board_root"])
    assert index["sheet"] == {
        "path": sheet.name,
        "sha256": hashlib.sha256(sheet.read_bytes()).hexdigest(),
    }
    for f in index["frames"]:
        glyph = (root / f["run_dir"] / "glyph.svg").read_bytes()
        assert f["glyph_sha256"] == hashlib.sha256(glyph).hexdigest()
    if os.name == "posix":
        assert stat.S_IMODE(sheet.stat().st_mode) == 0o600


def test_sheet_embeds_every_glyph_byte_for_byte_in_order(board):
    root, built = board
    text = Path(built["sheet_path"]).read_text(encoding="utf-8")
    images = sb._FRAME_IMAGE.findall(text)
    assert [int(n) for n, _ in images] == [1, 2, 3]
    for (_, data), frame in zip(images, built["frames"]):
        assert base64.b64decode(data) == (root / frame["run_dir"] / "glyph.svg").read_bytes()


def test_sheet_and_index_hold_no_private_data(board):
    _, built = board
    for path in (built["sheet_path"], built["index_path"]):
        text = Path(path).read_text(encoding="utf-8")
        decoded = text + "".join(
            base64.b64decode(b).decode("utf-8", "replace")
            for b in re.findall(r"[A-Za-z0-9+/=]{200,}", text)
        )
        for intent in (A, B, C):
            assert intent.lower() not in decoded.lower()
            assert normalize_intent(intent) not in decoded.lower()
        assert "nonce" not in decoded.lower()
        assert "passphrase" not in decoded.lower()


def test_verify_passes_from_the_index_and_from_the_sheet_alone(board, tmp_path):
    _, built = board
    from_index = verify_storyboard(built["index_path"])
    assert from_index["ok"] is True and from_index["kind"] == "index"
    assert from_index["board_root"] == built["board_root"]
    assert from_index["frame_count"] == 3 and from_index["legacy_index"] is False

    alone = tmp_path / "somewhere-else.svg"
    alone.write_bytes(Path(built["sheet_path"]).read_bytes())
    from_sheet = verify_storyboard(alone)
    assert from_sheet["ok"] is True and from_sheet["kind"] == "sheet"
    assert from_sheet["board_id"] == built["board_id"]
    assert from_sheet["board_root"] == built["board_root"]
    assert [f["intent_digest"] for f in from_sheet["frames"]] == [
        f["intent_digest"] for f in built["frames"]
    ]


def test_board_root_depends_on_order_and_on_every_field(board):
    _, built = board
    frames = [dict(f) for f in built["frames"]]
    base = sb.board_root_for(frames)
    assert base == built["board_root"]
    swapped = [dict(frames[1], index=1), dict(frames[0], index=2), frames[2]]
    assert sb.board_root_for(swapped) != base
    for key in ("intent_digest", "sigil_root", "glyph_sha256"):
        changed = [dict(f) for f in frames]
        changed[0][key] = "0" * 64
        assert sb.board_root_for(changed) != base


def _edit(path: Path, fn) -> None:
    path.write_text(fn(path.read_text(encoding="utf-8")), encoding="utf-8")


def _swap_first_two_images(text: str) -> str:
    images = sb._FRAME_IMAGE.findall(text)
    a, b = images[0][1], images[1][1]
    return text.replace(a, "\0").replace(b, a).replace("\0", b)


def _replace_meta(text: str, fn) -> str:
    raw = sb._BOARD_META.search(text).group(1)
    meta = json.loads(base64.b64decode(raw))
    fn(meta)
    new = base64.b64encode(json.dumps(meta, sort_keys=True).encode()).decode()
    return text.replace(raw, new)


@pytest.mark.parametrize(
    "tamper",
    [
        _swap_first_two_images,
        lambda t: _replace_meta(t, lambda m: m.update(board_root="0" * 64)),
        lambda t: _replace_meta(t, lambda m: m.update(board_id="0" * 16)),
        lambda t: _replace_meta(t, lambda m: m.pop("board_root")),
        lambda t: _replace_meta(t, lambda m: m["frames"].pop()),
        lambda t: _replace_meta(t, lambda m: m["frames"][0].update(d="0" * 64)),
        lambda t: _replace_meta(t, lambda m: m.update(v=2)),
        lambda t: t.replace('data-sf-frame="2"', 'data-sf-frame="3"', 1),
        lambda t: t.replace("</svg>", '<image href="x.png"/></svg>'),
        lambda t: t.replace("<sf:board>", "<sf:board>!!"),
        lambda t: re.sub(r"<sf:board>.*?</sf:board>", "", t),
    ],
)
def test_a_tampered_sheet_does_not_verify(board, tmp_path, tamper):
    _, _, sheet = _copy_board(board, tmp_path)
    _edit(sheet, tamper)
    got = verify_sheet(sheet)
    assert got["ok"] is False and got["detail"] != "ok"


def test_a_sheet_with_an_altered_glyph_does_not_verify(board, tmp_path):
    """Change one embedded glyph and fix up nothing else."""
    _, _, sheet = _copy_board(board, tmp_path)
    text = sheet.read_text(encoding="utf-8")
    data = sb._FRAME_IMAGE.findall(text)[0][1]
    glyph = base64.b64decode(data).replace(b'fill="#f7f4ef"', b'fill="#ffffff"')
    sheet.write_text(text.replace(data, base64.b64encode(glyph).decode()), encoding="utf-8")
    assert verify_sheet(sheet)["ok"] is False


def test_a_frame_from_another_board_cannot_be_swapped_in(board, tmp_path):
    """The record still describes the original frame, so the swap is caught."""
    root, built = board
    other = build_storyboard(["I keep my promises to myself"], out_root=tmp_path / "other")
    foreign = (tmp_path / "other" / other["frames"][0]["run_dir"] / "glyph.svg").read_bytes()
    _, index, sheet = _copy_board(board, tmp_path)
    text = sheet.read_text(encoding="utf-8")
    data = sb._FRAME_IMAGE.findall(text)[0][1]
    sheet.write_text(text.replace(data, base64.b64encode(foreign).decode()), encoding="utf-8")
    assert verify_sheet(sheet)["ok"] is False
    got = verify_index(index)
    assert got["ok"] is False and "sheet" in got["detail"]


def test_index_verify_catches_a_changed_or_missing_run(board, tmp_path):
    dest, index, _ = _copy_board(board, tmp_path)
    first = json.loads(index.read_text(encoding="utf-8"))["frames"][0]["run_dir"]
    glyph = dest / first / "glyph.svg"
    glyph.write_bytes(glyph.read_bytes().replace(b'fill="#f7f4ef"', b'fill="#ffffff"'))
    got = verify_index(index)
    assert got["ok"] is False and "frame 1" in got["detail"]
    glyph.unlink()
    got = verify_index(index)
    assert got["ok"] is False and "missing" in got["detail"]


def test_index_verify_catches_a_changed_or_missing_sheet(board, tmp_path):
    _, index, sheet = _copy_board(board, tmp_path)
    sheet.write_text(sheet.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert "sheet changed" in verify_index(index)["detail"]
    sheet.unlink()
    got = verify_index(index)
    assert got["ok"] is False and "sheet is missing" in got["detail"]


@pytest.mark.parametrize("bad", ["../outside", "/etc", "a/b", "", ".hidden", "x" * 200, 5, None])
def test_index_run_dir_must_be_a_plain_folder_name(board, tmp_path, bad):
    _, index, _ = _copy_board(board, tmp_path)
    data = json.loads(index.read_text(encoding="utf-8"))
    data["frames"][0]["run_dir"] = bad
    index.write_text(json.dumps(data), encoding="utf-8")
    got = verify_index(index)
    assert got["ok"] is False and "malformed index" in got["detail"]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="needs symlinks")
def test_index_verify_does_not_follow_a_symlinked_run(board, tmp_path):
    dest, index, _ = _copy_board(board, tmp_path)
    first = json.loads(index.read_text(encoding="utf-8"))["frames"][0]["run_dir"]
    real = dest / first
    moved = tmp_path / "moved"
    real.rename(moved)
    real.symlink_to(moved, target_is_directory=True)
    got = verify_index(index)
    assert got["ok"] is False and "frame 1" in got["detail"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="something-else/1"),
        lambda d: d.update(frames=[]),
        lambda d: d.update(frames=d["frames"] * 5),
        lambda d: d["frames"][1].update(index=7),
        lambda d: d["frames"][0].update(intent_digest="xyz"),
        lambda d: d.update(board_id="nope"),
        lambda d: d.update(board_root="0" * 64),
        lambda d: d.pop("sheet"),
        lambda d: d["sheet"].update(path="../../etc/passwd"),
    ],
)
def test_a_tampered_index_does_not_verify(board, tmp_path, mutate):
    _, index, _ = _copy_board(board, tmp_path)
    data = json.loads(index.read_text(encoding="utf-8"))
    mutate(data)
    index.write_text(json.dumps(data), encoding="utf-8")
    assert verify_index(index)["ok"] is False


def test_an_index_from_before_board_root_still_verifies_and_says_so(board, tmp_path):
    _, index, sheet = _copy_board(board, tmp_path)
    data = json.loads(index.read_text(encoding="utf-8"))
    for key in ("board_root", "sheet"):
        data.pop(key)
    for f in data["frames"]:
        f.pop("glyph_sha256")
    index.write_text(json.dumps(data), encoding="utf-8")
    sheet.unlink()
    got = verify_index(index)
    assert got["ok"] is True and got["legacy_index"] is True
    assert "before board_root" in got["detail"]


def test_oversized_and_unreadable_inputs_are_refused(tmp_path):
    big = tmp_path / "big.svg"
    big.write_bytes(b"<svg>" + b" " * (sb.MAX_SHEET_BYTES + 1))
    assert verify_storyboard(big)["ok"] is False
    big_index = tmp_path / "big.json"
    big_index.write_bytes(b" " * (sb.MAX_INDEX_BYTES + 1))
    assert verify_storyboard(big_index)["ok"] is False
    assert verify_storyboard(tmp_path / "missing.json")["detail"] == "file not found"
    junk = tmp_path / "junk.json"
    junk.write_bytes(b"\xff\xfe not json")
    assert verify_storyboard(junk)["ok"] is False


def test_failed_board_leaves_no_sheet_or_index(tmp_path, monkeypatch):
    calls = {"n": 0}
    real = construct.run

    def flaky(intent, **kw):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated failure on frame 2")
        return real(intent, **kw)

    monkeypatch.setattr(construct, "run", flaky)
    with pytest.raises(RuntimeError):
        build_storyboard([A, B], out_root=tmp_path)
    assert not list(tmp_path.rglob("storyboard-*"))
    assert not [p for p in tmp_path.iterdir() if p.is_dir() and p.name != "storyboards"]


def test_cli_storyboard_verify_exit_codes(board, tmp_path):
    _, built = board
    ok = subprocess.run([*CLI, "storyboard-verify", built["sheet_path"]], capture_output=True, text=True)
    assert ok.returncode == 0 and json.loads(ok.stdout)["ok"] is True
    _, _, sheet = _copy_board(board, tmp_path)
    _edit(sheet, _swap_first_two_images)
    bad = subprocess.run([*CLI, "storyboard-verify", str(sheet)], capture_output=True, text=True)
    assert bad.returncode == 1 and json.loads(bad.stdout)["ok"] is False


# ------------------------------------------------ findings from review of #43


def test_failed_rebuild_keeps_the_earlier_board(tmp_path, monkeypatch):
    """Rebuilding the same intents must not destroy the board that was there."""
    first = build_storyboard([A, B], out_root=tmp_path)
    index, sheet = Path(first["index_path"]), Path(first["sheet_path"])
    before = (index.read_bytes(), sheet.read_bytes())
    runs_before = sorted(p.name for p in tmp_path.iterdir())
    real = sb.write_private_text

    def fail_on_index(path, text):
        if Path(path).suffix == ".json":
            raise OSError("disk full")
        return real(path, text)

    # Run ids carry a one-second timestamp; wait so the rebuild gets new ones,
    # as any real rebuild would.
    import time

    time.sleep(1.1)
    monkeypatch.setattr(sb, "write_private_text", fail_on_index)
    with pytest.raises(OSError):
        build_storyboard([A, B], out_root=tmp_path)
    monkeypatch.undo()

    assert (index.read_bytes(), sheet.read_bytes()) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == runs_before
    assert verify_index(index)["ok"] is True


def test_rollback_never_removes_a_run_folder_that_was_already_there(tmp_path, monkeypatch):
    """A rebuild in the same clock second reuses run folder names."""
    first = build_storyboard([A, B], out_root=tmp_path)
    names = sorted(f["run_dir"] for f in first["frames"])
    real = construct.run

    def same_ids_then_fail(intent, **kw):
        if intent == B:
            raise RuntimeError("simulated failure on frame 2")
        packet = real(intent, **kw)
        return packet

    monkeypatch.setattr(construct, "run", same_ids_then_fail)
    with pytest.raises(RuntimeError):
        build_storyboard([A, B], out_root=tmp_path)
    for name in names:
        assert (tmp_path / name).is_dir(), name


def test_failed_first_build_removes_the_folder_it_made(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "write_private_text", lambda *a: (_ for _ in ()).throw(OSError("no")))
    with pytest.raises(OSError):
        build_storyboard([A, B], out_root=tmp_path)
    assert not (tmp_path / "storyboards").exists()
    assert _empty(tmp_path)


def _sheet_with(board, tmp_path, edit) -> Path:
    _, _, sheet = _copy_board(board, tmp_path)
    _edit(sheet, edit)
    return sheet


@pytest.mark.parametrize(
    "smuggle",
    [
        # every real frame hidden in a comment: nothing renders
        lambda t: re.sub(r"(  <image data-sf-frame[^\n]*\n)+", lambda m: "<!--\n" + m.group(0) + "-->\n", t, count=1),
        # a prefixed image drawn over the sheet
        lambda t: t.replace("</svg>", '<svg:image xmlns:svg="http://www.w3.org/2000/svg" href="x.png" width="500" height="500"/></svg>'),
        lambda t: t.replace("</svg>", "<script>alert(1)</script></svg>"),
        lambda t: t.replace("  <metadata>", "  <!-- note -->\n  <metadata>"),
        lambda t: t.replace('fill="#f7f4ef"/>\n  <image', 'fill="#000000"/>\n  <image', 1),
        lambda t: t + "\n",
        lambda t: t.replace(' x="6" y="6"', ' x="600" y="600"', 1),
    ],
)
def test_a_sheet_with_anything_extra_does_not_verify(board, tmp_path, smuggle):
    """What a viewer shows must be exactly what was checked."""
    sheet = _sheet_with(board, tmp_path, smuggle)
    assert sheet.read_text(encoding="utf-8") != Path(board[1]["sheet_path"]).read_text(encoding="utf-8")
    got = verify_sheet(sheet)
    assert got["ok"] is False, got["detail"]


def test_non_utf8_and_non_svg_frames_fail_without_raising(board, tmp_path):
    dest, index, sheet = _copy_board(board, tmp_path)
    text = sheet.read_text(encoding="utf-8")
    data = sb._FRAME_IMAGE.findall(text)[0][1]
    sheet.write_text(text.replace(data, base64.b64encode(b"\xff\xfe<<<").decode()), encoding="utf-8")
    assert verify_storyboard(sheet)["ok"] is False
    first = json.loads(index.read_text(encoding="utf-8"))["frames"][0]["run_dir"]
    (dest / first / "glyph.svg").write_bytes(b"\xff\xfe")
    got = verify_storyboard(index)
    assert got["ok"] is False and "frame 1" in got["detail"]


@pytest.mark.parametrize("value", [1.0, True, "1", None, [1]])
def test_index_frame_number_must_be_a_real_integer(board, tmp_path, value):
    _, index, _ = _copy_board(board, tmp_path)
    data = json.loads(index.read_text(encoding="utf-8"))
    data["frames"][0]["index"] = value
    index.write_text(json.dumps(data), encoding="utf-8")
    got = verify_storyboard(index)
    assert got["ok"] is False and "malformed index" in got["detail"]


@pytest.mark.parametrize("junk", ["[]", "7", "null", '"x"', '{"frames": 3}', '{"schema": 1, "frames": {}}'])
def test_wrong_json_shapes_fail_without_raising(tmp_path, junk):
    path = tmp_path / "storyboard-x.json"
    path.write_text(junk, encoding="utf-8")
    assert verify_storyboard(path)["ok"] is False


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs FIFOs")
def test_a_fifo_is_refused_instead_of_blocking(board, tmp_path):
    import threading

    dest, index, sheet = _copy_board(board, tmp_path)
    first = json.loads(index.read_text(encoding="utf-8"))["frames"][0]["run_dir"]
    glyph = dest / first / "glyph.svg"
    glyph.unlink()
    os.mkfifo(glyph)
    lone = tmp_path / "lone.svg"
    os.mkfifo(lone)

    results: dict[str, dict] = {}

    def work():
        results["index"] = verify_storyboard(index)
        results["sheet"] = verify_storyboard(lone)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout=20)
    assert not t.is_alive(), "verify blocked on a FIFO"
    assert results["index"]["ok"] is False and "frame 1" in results["index"]["detail"]
    assert results["sheet"]["ok"] is False


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="needs symlinks")
def test_symlinked_glyph_and_sheet_are_refused(board, tmp_path):
    dest, index, sheet = _copy_board(board, tmp_path)
    first = json.loads(index.read_text(encoding="utf-8"))["frames"][0]["run_dir"]
    glyph = dest / first / "glyph.svg"
    real = tmp_path / "real-glyph.svg"
    glyph.rename(real)
    glyph.symlink_to(real)
    assert "frame 1" in verify_index(index)["detail"]
    real_sheet = tmp_path / "real-sheet.svg"
    sheet.rename(real_sheet)
    sheet.symlink_to(real_sheet)
    assert verify_sheet(sheet)["ok"] is False


def test_the_same_frame_twice_does_not_verify(board, tmp_path):
    root, built = board
    f = dict(built["frames"][0])
    glyph = (root / f["run_dir"] / "glyph.svg").read_bytes()
    frames = [dict(f, index=1), dict(f, index=2)]
    text = sb.build_sheet_svg(
        sb.board_id_for([f["intent_digest"]] * 2), sb.board_root_for(frames), frames, [glyph, glyph]
    )
    path = tmp_path / "twice.svg"
    path.write_text(text, encoding="utf-8")
    got = verify_sheet(path)
    assert got["ok"] is False and "twice" in got["detail"]


def _rebuilt_without_last_frame(board, tmp_path) -> Path:
    """What anyone can do: drop a frame and write a new, self-consistent sheet."""
    root, built = board
    frames = [dict(f) for f in built["frames"][:2]]
    glyphs = [(root / f["run_dir"] / "glyph.svg").read_bytes() for f in frames]
    text = sb.build_sheet_svg(
        sb.board_id_for([f["intent_digest"] for f in frames]), sb.board_root_for(frames), frames, glyphs
    )
    path = tmp_path / "rebuilt.svg"
    path.write_text(text, encoding="utf-8")
    return path


def test_expected_root_is_what_ties_a_board_to_its_author(board, tmp_path):
    """Consistency alone cannot catch a rebuilt board; the expected root does."""
    _, built = board
    rebuilt = _rebuilt_without_last_frame(board, tmp_path)
    plain = verify_storyboard(rebuilt)
    assert plain["ok"] is True and plain["anchored"] is False

    anchored = verify_storyboard(rebuilt, expected_root=built["board_root"])
    assert anchored["ok"] is False and "expected root" in anchored["detail"]

    for source in (built["sheet_path"], built["index_path"]):
        good = verify_storyboard(source, expected_root=built["board_root"].upper())
        assert good["ok"] is True and good["anchored"] is True
        assert verify_storyboard(source)["anchored"] is False
        assert verify_storyboard(source, expected_root="not-hex")["ok"] is False


def test_stripping_an_index_to_the_old_form_cannot_pass_an_expected_root(board, tmp_path):
    """The downgrade still reports itself, and never satisfies an expected root."""
    _, index, sheet = _copy_board(board, tmp_path)
    data = json.loads(index.read_text(encoding="utf-8"))
    for key in ("board_root", "sheet"):
        data.pop(key)
    data["frames"] = data["frames"][:2]
    for f in data["frames"]:
        f.pop("glyph_sha256")
    data["board_id"] = sb.board_id_for([f["intent_digest"] for f in data["frames"]])
    index.write_text(json.dumps(data), encoding="utf-8")
    plain = verify_index(index)
    assert plain["legacy_index"] is True and plain["anchored"] is False
    got = verify_index(index, expected_root=board[1]["board_root"])
    assert got["ok"] is False and "no board_root" in got["detail"]


def test_cli_expect_root(board, tmp_path):
    _, built = board
    ok = subprocess.run(
        [*CLI, "storyboard-verify", built["sheet_path"], "--expect-root", built["board_root"]],
        capture_output=True, text=True,
    )
    assert ok.returncode == 0 and json.loads(ok.stdout)["anchored"] is True
    bad = subprocess.run(
        [*CLI, "storyboard-verify", built["sheet_path"], "--expect-root", "0" * 64],
        capture_output=True, text=True,
    )
    assert bad.returncode == 1 and json.loads(bad.stdout)["ok"] is False
