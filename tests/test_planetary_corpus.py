"""Planetary character corpus + name-on-kamea intelligence/spirit paths."""

from __future__ import annotations

import json
from pathlib import Path

from sigil_forge.construct import run as construct_run
from sigil_forge.planetary_corpus import list_corpus_summary, load_corpus, role_entry
from sigil_forge.planetary_seals import intelligence_character, spirit_character, traditional_seal_path
from sigil_forge.kamea import encode_hebrew_gematria

ROOT = Path(__file__).resolve().parents[1]


def test_corpus_covers_seven_planets():
    data = load_corpus()
    assert data["corpus_id"]
    planets = data["planets"]
    assert set(planets) == {
        "saturn",
        "jupiter",
        "mars",
        "sol",
        "venus",
        "mercury",
        "luna",
    }
    summary = list_corpus_summary()
    assert len(summary) == 7
    assert all(s["intelligence"] and s["spirit"] for s in summary)


def test_native_hebrew_gematria():
    original, reduced, ops, notes, translit = encode_hebrew_gematria("אגיאל", "saturn")
    assert translit == "native_hebrew"
    assert original
    assert reduced
    assert all(1 <= r <= 9 for r in reduced)


def test_intelligence_auto_is_plate_with_entity_metadata():
    intel = intelligence_character("jupiter")  # default geometry=auto → plate
    assert intel.artifact_class == "intelligence_character"
    assert intel.claimed_historical_status == "stroke_digitization_plate_v1"
    assert intel.entity_name == "Iophiel"
    assert intel.entity_number == 136
    assert len(intel.strokes) >= 2
    assert intel.path != traditional_seal_path("jupiter").path


def test_spirit_name_on_kamea_explicit():
    spirit = spirit_character("saturn", geometry="name_on_kamea")
    assert spirit.entity_name == "Zazel"
    assert spirit.claimed_historical_status == "corpus_name_path_agrippan"
    assert spirit.provenance.get("entity_name_hebrew")
    assert len(spirit.path) >= 1


def test_traditional_seal_still_successive():
    trad = traditional_seal_path("mars")
    assert len(trad.path) == 25
    assert trad.successive_values == list(range(1, 26))


def test_construct_with_intelligence_corpus(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        square="jupiter",
        kamea_encoding="latin_mod9_v1",
        planetary_seal=True,
        planetary_seal_kind="intelligence_character",
        planetary_geometry="name_on_kamea",
    )
    ps = packet["methods"]["planetary_seal"]
    assert ps.get("entity_name") == "Iophiel"
    assert ps.get("claimed_historical_status") == "corpus_name_path_agrippan"
    ont = packet["ontology"]["methods"]
    mids = {m["method_id"] for m in ont}
    assert any(m.startswith("planetary.intelligence_character.") for m in mids)


def test_role_entry_numbers():
    intel = role_entry("sol", "intelligence_character")
    assert intel["number"] == 111
    spirit = role_entry("sol", "spirit_character")
    assert spirit["number"] == 666


def test_corpus_file_json_valid():
    p = ROOT / "references" / "planetary-character-corpus.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0.0"
