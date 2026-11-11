"""v0.3: bind-runes, rose-cross path, receipts, learning ledger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bind_runes import build_bind_polylines, latin_to_runes
from construct import run as construct_run
from fuse import build_layout
from normalize import normalize_intent
from crypto_payload import intent_digest
from receipt import (
    append_ledger,
    build_ledger_entry,
    read_ledger,
)
from rose_cross import build_rose_path, letter_to_slot
from verify import run as verify_run


def test_latin_to_runes_and_bind_geometry():
    runes = latin_to_runes("thorr")
    assert "ᚦ" in runes  # th digraph
    polys, used = build_bind_polylines("mntclfs")
    assert used
    assert polys
    assert all(len(p) >= 2 for p in polys)


def test_rose_path_slots():
    assert letter_to_slot("a") == 0
    pts, slots = build_rose_path("mntclfs")
    assert len(pts) >= 2
    assert slots
    assert all(0 <= s < 22 for s in slots)


def test_layout_includes_bind_and_rose():
    n = normalize_intent("I maintain calm focus while shipping")
    d = intent_digest(n)
    lay = build_layout(n, d, square_override="saturn")
    assert lay.bind_polylines
    assert lay.bind_runes
    assert lay.rose_points
    assert lay.rose_slots


def test_construct_applies_new_channels_and_receipt(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        out_root=tmp_path,
        square="saturn",
    )
    by_id = {c["id"]: c for c in packet["channels"]}
    assert "bind_runes" in by_id
    assert "rose_cross_path" in by_id
    assert by_id["bind_runes"]["status"] == "applied"
    assert by_id["rose_cross_path"]["status"] == "applied"
    assert "bind_runes" in packet["methods"]
    assert "rose_cross" in packet["methods"]

    svg = Path(packet["artifacts"]["svg"]).read_text(encoding="utf-8")
    assert 'id="bind-runes"' in svg
    assert 'id="rose-cross-path"' in svg
    # No rune unicode names forced into public SVG as readable labels
    assert "ᚠ" not in svg

    receipt_path = Path(packet["artifacts"]["run_dir"]) / "run-receipt.json"
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["kind"] == "sigil_forge_run_receipt"
    assert receipt["intent_digest"] == packet["intent_digest"]
    assert "bind_runes" in receipt["channels_applied"]
    assert "rose_cross_path" in receipt["channels_applied"]
    assert receipt["canon_status"] == "OBSERVATION"
    assert len(receipt["receipt_hash"]) == 64

    v = verify_run(packet["artifacts"]["svg"])
    assert v["ok"] is True


def test_learning_ledger_proposed_only(tmp_path: Path):
    ledger = tmp_path / "learning-ledger.jsonl"
    entry = build_ledger_entry(
        class_name="channel_preference",
        summary="bind_runes + rose felt coherent",
        run_id="test-run",
        channels=["bind_runes", "rose_cross_path"],
    )
    assert entry["canon_status"] == "PROPOSED"
    append_ledger(entry, ledger)
    rows = read_ledger(ledger, limit=10)
    assert len(rows) == 1
    assert rows[0]["class"] == "channel_preference"

    with pytest.raises(ValueError):
        bad = dict(entry)
        bad["canon_status"] = "CANON"
        append_ledger(bad, ledger)
