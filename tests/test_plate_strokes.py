"""Stroke-faithful planetary plate digitizations."""

from __future__ import annotations

import json
from pathlib import Path

from sigil_forge.construct import run as construct_run
from sigil_forge.planetary_seals import intelligence_character, seal_for, spirit_character, traditional_seal_path
from sigil_forge.plate_strokes import load_plate_corpus, resolve_plate_entry, traditional_plate_strokes

ROOT = Path(__file__).resolve().parents[1]


def test_plate_corpus_has_seven_planets_intel_spirit():
    data = load_plate_corpus()
    assert data.get("plate_corpus_id")
    entries = data["entries"]
    assert set(entries) == {
        "saturn",
        "jupiter",
        "mars",
        "sol",
        "venus",
        "mercury",
        "luna",
    }
    for planet, roles in entries.items():
        for kind in ("intelligence_character", "spirit_character"):
            assert kind in roles, planet
            assert roles[kind]["strokes"], planet
            assert roles[kind]["coordinate_space"] == "unit_box"


def test_traditional_plate_has_multiple_strokes():
    plate = traditional_plate_strokes("saturn")
    assert plate["construction"] == "successive_plus_frame_plate_v1"
    assert len(plate["strokes"]) >= 2  # path + frame (+ ticks)
    assert len(plate["primary_path"]) == 9


def test_intelligence_auto_prefers_plate():
    intel = intelligence_character("jupiter", geometry="auto")
    assert intel.claimed_historical_status == "stroke_digitization_plate_v1"
    assert intel.provenance.get("status") == "plate_stroke_digitization"
    assert len(intel.strokes) >= 2
    assert intel.entity_name == "Iophiel"


def test_spirit_plate_geometry_forced():
    spirit = spirit_character("mars", geometry="plate")
    assert spirit.provenance.get("construction") == "stroke_digitization_v1"
    assert spirit.entity_name == "Bartzabel"
    # multi-stroke
    assert len(spirit.strokes) >= 2


def test_name_on_kamea_still_available():
    intel = intelligence_character("jupiter", geometry="name_on_kamea")
    assert intel.claimed_historical_status == "corpus_name_path_agrippan"
    assert intel.provenance.get("construction") == "name_on_kamea"
    assert len(intel.strokes) == 1


def test_reconstruction_mode():
    spirit = spirit_character("jupiter", geometry="reconstruction")
    assert spirit.claimed_historical_status == "engine_reconstruction_documented"
    assert len(spirit.path) == 16


def test_traditional_auto_is_plate():
    trad = traditional_seal_path("venus", geometry="auto")
    assert trad.claimed_historical_status == "stroke_digitization_plate_v1"
    assert len(trad.strokes) >= 2
    assert trad.successive_values == list(range(1, 50))


def test_construct_plate_in_svg(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        square="saturn",
        kamea_encoding="latin_mod9_v1",
        planetary_seal=True,
        planetary_seal_kind="intelligence_character",
        planetary_geometry="plate",
    )
    ps = packet["methods"]["planetary_seal"]
    assert ps["claimed_historical_status"] == "stroke_digitization_plate_v1"
    assert len(ps.get("strokes") or []) >= 2
    svg = Path(packet["artifacts"]["svg"]).read_text(encoding="utf-8")
    # multi-stroke → multiple polylines in planetary-seal group
    seal_section = svg.split('id="planetary-seal"')[1].split("</g>")[0]
    assert seal_section.count("<polyline") >= 2


def test_seal_for_geometry_param():
    a = seal_for("luna", kind="spirit_character", geometry="plate")
    b = seal_for("luna", kind="spirit_character", geometry="name_on_kamea")
    assert a.claimed_historical_status != b.claimed_historical_status
    assert a.path != b.path or len(a.strokes) != len(b.strokes)


def test_resolve_plate_entry_maps_unit_box():
    ent = resolve_plate_entry("sol", "intelligence_character")
    assert ent is not None
    assert ent["coordinate_space"] == "kamea_cells"
    # sol order 6 → unit points * 6
    for poly in ent["strokes"]:
        for x, y in poly:
            assert 0.0 <= x <= 6.0 + 1e-6
            assert 0.0 <= y <= 6.0 + 1e-6


def test_plate_json_file_valid():
    p = ROOT / "references" / "planetary-plate-strokes.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0.0"
