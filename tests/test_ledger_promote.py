"""Human-gated ledger promotion: PROPOSED-only log + operator-local proposals."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sigil_forge.receipt import (
    append_ledger,
    append_learning_entry,
    build_ledger_entry,
    default_canon_proposals_path,
    export_proposed,
    list_learning,
    promote_entry,
    promote_to_canon_proposal,
    read_ledger,
)

CLI = Path(__file__).resolve().parents[1] / "scripts" / "sigil_forge.py"
ROOT = Path(__file__).resolve().parents[1]


def test_learning_entry_stays_proposed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ledger = tmp_path / "learning-ledger.jsonl"
    monkeypatch.setenv("SIGIL_FORGE_LEDGER", str(ledger))

    e = append_learning_entry(
        class_="channel_preference",
        summary="rose path coherent",
        run_id="run-1",
        channels=["rose_cross_path"],
    )
    assert e["canon_status"] == "PROPOSED"

    rows = list_learning(limit=10)
    assert len(rows) == 1
    assert rows[0]["canon_status"] == "PROPOSED"
    assert rows[0]["summary"] == "rose path coherent"

    # re-read raw file: still PROPOSED only
    raw = read_ledger(ledger, limit=10)
    assert raw[0]["canon_status"] == "PROPOSED"


def test_export_proposed_filters(tmp_path: Path):
    ledger = tmp_path / "learning-ledger.jsonl"
    e = build_ledger_entry(class_name="note", summary="ok")
    append_ledger(e, ledger)
    proposed = export_proposed(limit=10, ledger_path=ledger)
    assert len(proposed) == 1
    assert proposed[0]["canon_status"] == "PROPOSED"


def test_promote_requires_confirm(tmp_path: Path):
    entry = build_ledger_entry(class_name="channel_preference", summary="coherent")
    with pytest.raises(ValueError, match="confirm"):
        promote_to_canon_proposal(entry, confirm="", out_dir=tmp_path)
    with pytest.raises(ValueError, match="confirm"):
        promote_to_canon_proposal(entry, confirm="yes", out_dir=tmp_path)


def test_promote_rejects_non_proposed(tmp_path: Path):
    entry = build_ledger_entry(class_name="note", summary="x")
    entry["canon_status"] = "CANON"
    with pytest.raises(ValueError, match="PROPOSED"):
        promote_to_canon_proposal(entry, confirm="PROMOTE", out_dir=tmp_path)


def test_promote_writes_proposal_not_references(tmp_path: Path):
    entry = build_ledger_entry(
        class_name="channel_preference",
        summary="rose path coherent",
        run_id="run-promote",
        channels=["rose_cross_path"],
    )
    prop = promote_to_canon_proposal(entry, confirm="PROMOTE", out_dir=tmp_path)
    assert prop["canon_status"] == "HUMAN_PROMOTED"
    assert prop["source_canon_status"] == "PROPOSED"
    assert prop["kind"] == "sigil_forge_canon_proposal"
    assert prop["entry"]["canon_status"] == "PROPOSED"
    assert prop["entry"]["summary"] == "rose path coherent"
    assert not (tmp_path / "references").exists()

    proposals_path = tmp_path / "canon-proposals.jsonl"
    assert proposals_path.is_file()
    lines = proposals_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    loaded = json.loads(lines[0])
    assert loaded["canon_status"] == "HUMAN_PROMOTED"


def test_promote_does_not_mutate_ledger(tmp_path: Path):
    ledger = tmp_path / "learning-ledger.jsonl"
    entry = build_ledger_entry(class_name="note", summary="stay proposed")
    append_ledger(entry, ledger)
    promote_to_canon_proposal(
        entry,
        confirm="PROMOTE",
        out_path=tmp_path / "canon-proposals.jsonl",
    )
    rows = read_ledger(ledger, limit=10)
    assert len(rows) == 1
    assert rows[0]["canon_status"] == "PROPOSED"
    assert rows[0]["summary"] == "stay proposed"


def test_promote_entry_by_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ledger = tmp_path / "learning-ledger.jsonl"
    proposals = tmp_path / "canon-proposals.jsonl"
    monkeypatch.setenv("SIGIL_FORGE_LEDGER", str(ledger))
    monkeypatch.setenv("SIGIL_FORGE_CANON_PROPOSALS", str(proposals))

    append_learning_entry(class_="a", summary="first")
    append_learning_entry(class_="b", summary="second")

    prop = promote_entry(0, confirm="PROMOTE", limit=20)
    assert prop["canon_status"] == "HUMAN_PROMOTED"
    # index 0 is oldest in the window of last N (same order as read_ledger)
    assert prop["entry"]["summary"] in ("first", "second")
    assert proposals.is_file()
    assert not (ROOT / "references" / "mutated-by-promote").exists()


def test_promote_entry_requires_confirm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ledger = tmp_path / "learning-ledger.jsonl"
    monkeypatch.setenv("SIGIL_FORGE_LEDGER", str(ledger))
    append_learning_entry(class_="a", summary="x")
    with pytest.raises(ValueError, match="confirm"):
        promote_entry(0, confirm="")


def test_ledger_cli_promote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ledger = tmp_path / "learning-ledger.jsonl"
    proposals = tmp_path / "canon-proposals.jsonl"
    entry = build_ledger_entry(class_name="cli", summary="from cli")
    append_ledger(entry, ledger)

    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "ledger",
            "promote",
            "--index",
            "0",
            "--i-confirm",
            "PROMOTE",
            "--ledger",
            str(ledger),
            "--out",
            str(proposals),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert payload["proposal"]["canon_status"] == "HUMAN_PROMOTED"
    assert proposals.is_file()
    # ledger unchanged
    assert read_ledger(ledger)[0]["canon_status"] == "PROPOSED"


def test_ledger_cli_promote_rejects_bad_confirm(tmp_path: Path):
    ledger = tmp_path / "learning-ledger.jsonl"
    entry = build_ledger_entry(class_name="cli", summary="nope")
    append_ledger(entry, ledger)

    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "ledger",
            "promote",
            "--index",
            "0",
            "--i-confirm",
            "yes",
            "--ledger",
            str(ledger),
            "--out",
            str(tmp_path / "out.jsonl"),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode != 0
    assert not (tmp_path / "out.jsonl").exists()


def test_ledger_cli_list_still_works(tmp_path: Path):
    ledger = tmp_path / "learning-ledger.jsonl"
    append_ledger(build_ledger_entry(class_name="n", summary="listed"), ledger)
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "ledger",
            "--ledger",
            str(ledger),
            "--limit",
            "5",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert payload["count"] == 1


def test_default_canon_proposals_path_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    p = tmp_path / "custom-proposals.jsonl"
    monkeypatch.setenv("SIGIL_FORGE_CANON_PROPOSALS", str(p))
    assert default_canon_proposals_path() == p
