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
