"""Method-corpus fidelity: kamea encodings, ontology, Spare family, rose, seals."""

from __future__ import annotations

from pathlib import Path

import pytest

from sigil_forge.construct import run as construct_run
from sigil_forge.kamea import (
    DEFAULT_KAMEA_ENCODING,
    build_kamea_path,
    encode_hebrew_gematria,
    square_max,
)
from sigil_forge.ontology import SPARE_MODES, assert_not_entity_seal_request, default_packet_ontology
from sigil_forge.planetary_seals import traditional_seal_path
from sigil_forge.rose_cross import ROSE_PETALS, build_rose_cross_path
from sigil_forge.spare import run_spare


def test_default_kamea_encoding_is_hebrew_gematria():
    assert DEFAULT_KAMEA_ENCODING == "hebrew_gematria"


def test_hebrew_gematria_visits_cells_beyond_mod9_on_jupiter():
    # Multi-letter name producing values that need reduction / >9 originals
    text = "Michael"
    original, reduced, ops, notes, translit = encode_hebrew_gematria(text, "jupiter")
    assert original, "expected original gematria values"
    assert any(v > 9 for v in original), f"expected values >9, got {original}"
    n_max = square_max("jupiter")  # 16
    assert all(1 <= r <= n_max for r in reduced)
    # At least one reduced value may still be >9 (Jupiter has cells 10–16)
    assert any(r > 9 for r in reduced) or ops, (
        "expected either reduced>9 (full square use) or reduction ops"
    )
    prov = build_kamea_path(letters=text, square_name="jupiter", encoding="hebrew_gematria")
    assert prov.encoding_system == "hebrew_gematria"
    assert prov.original_numeric_sequence == original
    assert prov.reduced_numeric_sequence == reduced
    assert len(prov.path) == len(reduced) or len(prov.path) > 0
    # Path points correspond to cells holding reduced values
    from sigil_forge.kamea import KAMEA_SQUARES

    square = KAMEA_SQUARES["jupiter"]
    for (x, y), val in zip(prov.path, prov.reduced_numeric_sequence):
        c, r = int(x - 0.5), int(y - 0.5)
        assert square[r][c] == val


def test_latin_mod9_v1_preserved_and_labeled():
    letters = list("mntclfs")
    prov = build_kamea_path(
        letters="maintain calm focus",
        square_name="luna",
        encoding="latin_mod9_v1",
        letter_list=letters,
    )
    assert prov.encoding_system == "latin_mod9_v1"
    assert all(1 <= n <= 9 for n in prov.original_numeric_sequence)
    assert "compatibility" in prov.claimed_historical_status or "mod9" in (
        prov.claimed_historical_status
    )


def test_construct_packet_ontology_and_kamea_provenance(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        out_root=tmp_path,
        square="jupiter",
        kamea_encoding="hebrew_gematria",
    )
    assert packet.get("ontology")
    assert packet["ontology"]["schema"] == "sigil-method-ontology/v1"
    families = {m["family"] for m in packet["ontology"]["methods"]}
    assert "intent_compression" in families
    assert "name_path" in families
    assert "encoded_carrier" in families
    assert "goetic_seal" not in families
    assert "enochian_seal" in set(packet["ontology"]["excluded_from_default_forge"])

    kamea = packet["methods"]["kamea"]
    assert kamea["encoding_system"] == "hebrew_gematria"
    assert "original_numeric_sequence" in kamea
    assert "reduced_numeric_sequence" in kamea
    assert "reduction_operations" in kamea
    assert packet["provenance"]["kamea"]["encoding_system"] == "hebrew_gematria"


def test_construct_latin_mod9_explicit(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        out_root=tmp_path,
        square="luna",
        kamea_encoding="latin_mod9_v1",
    )
    assert packet["methods"]["kamea"]["encoding_system"] == "latin_mod9_v1"
    assert all(
        1 <= n <= 9 for n in packet["methods"]["kamea"]["original_numeric_sequence"]
    )


def test_spare_family_letter_monogram_and_assisted(tmp_path: Path):
    mono = run_spare("i maintain calm focus", mode="letter_monogram")
    assert mono.determinism == "deterministic"
    assert mono.spare_letters

    pic = run_spare(
        "i maintain calm focus",
        mode="pictorial",
        intent_digest="ab" * 32,
    )
    assert pic.semantic_verification == "NOT_COMPUTABLE"
    assert pic.determinism == "assisted"
    assert pic.artifact is not None
    assert "letter_monogram" in SPARE_MODES
    assert "phonetic_mantric" in SPARE_MODES

    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        spare_mode="pictorial",
        kamea_encoding="latin_mod9_v1",
    )
    assert packet["methods"]["spare"]["mode"] == "pictorial"
    assert packet["methods"]["spare"]["semantic_verification"] == "NOT_COMPUTABLE"


def test_rose_cross_hebrew_petals_and_markers():
    assert len(ROSE_PETALS) == 22
    rose = build_rose_cross_path("Michael")
    assert rose.method_id == "rose_cross.hebrew_petal_path"
    assert len(rose.coordinates) == len(rose.petal_indices)
    assert len(rose.coordinates) >= 1
    assert rose.start_marker and rose.terminal_marker
    assert all(0 <= i < 22 for i in rose.petal_indices)


def test_planetary_seal_distinct_from_kamea_path():
    seal = traditional_seal_path("jupiter")
    assert seal.artifact_class == "traditional_seal"
    assert seal.provenance.get("not_kamea_name_path") is True
    # Full 1..16 path on Jupiter
    assert len(seal.path) == 16
    name_path = build_kamea_path(
        letters="Michael", square_name="jupiter", encoding="hebrew_gematria"
    )
    # Different construction: seal is full successive values; name path is shorter
    assert len(name_path.path) != len(seal.path) or name_path.path != seal.path


def test_construct_planetary_seal_channel(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        square="saturn",
        planetary_seal=True,
        kamea_encoding="latin_mod9_v1",
    )
    by_id = {c["id"]: c for c in packet["channels"]}
    assert by_id["planetary_seal"]["status"] == "applied"
    assert packet["methods"]["planetary_seal"]["artifact_class"] == "traditional_seal"
    svg = Path(packet["artifacts"]["svg"]).read_text(encoding="utf-8")
    assert 'id="planetary-seal"' in svg
    assert 'id="rose-start"' in svg or "rose-cross-path" in svg


def test_bind_runes_modern_derivation_label(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
    )
    br = packet["methods"]["bind_runes"]
    assert br["claimed_historical_status"] == "modern_derivation"
    assert br["intent_sigil_system"]["status"] == "modern_derivation"
    ont_bind = [
        m
        for m in packet["ontology"]["methods"]
        if m["method_id"].startswith("bind_rune")
    ][0]
    assert ont_bind["claimed_historical_status"] == "modern_derivation"


def test_refuse_goetic_entity_request():
    with pytest.raises(ValueError, match=r"AUTHORITY_SEAL_EXCLUDED|excluded"):
        assert_not_entity_seal_request("draw a goetic seal for me")
    with pytest.raises(ValueError, match=r"AUTHORITY_SEAL_EXCLUDED|excluded"):
        construct_run("I want a goetic seal of Asmodeus", out_root=Path("/tmp"))


def test_ontology_helper_shape():
    o = default_packet_ontology(kamea_encoding="hebrew_gematria", include_planetary_seal=True, planet="mars")
    assert any(m["family"] == "planetary_character" for m in o["methods"])
