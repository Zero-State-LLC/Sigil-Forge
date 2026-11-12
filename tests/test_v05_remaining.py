"""v0.5 remaining-work coverage."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sigil_forge.construct import run as construct_run
from sigil_forge.kamea import build_kamea_path, transliterate_latin_to_hebrew
from sigil_forge.phonetic import build_phonetic_artifact, compress_phonetic
from sigil_forge.planetary_seals import intelligence_character, spirit_character, traditional_seal_path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"


def test_transliteration_known_names():
    m, notes = transliterate_latin_to_hebrew("Michael")
    assert m
    assert "מ" in m or "י" in m
    r, _ = transliterate_latin_to_hebrew("Raphael")
    assert r
    # unmapped still notes rather than inventing exotic chars
    _, n2 = transliterate_latin_to_hebrew("xyz")
    assert isinstance(n2, list)


def test_kamea_goldens_match_engine():
    gold_dir = ROOT / "examples" / "kamea"
    files = list(gold_dir.glob("*.json"))
    assert len(files) >= 6
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        enc = data["encoding"]
        text = data["text"]
        square = data["square"]
        if enc.startswith("latin"):
            from sigil_forge.normalize import normalize_intent
            from sigil_forge.spare import letter_sequence

            if enc == "latin_mod9_v1":
                ll = letter_sequence(normalize_intent(text))
                if not ll:
                    ll = list("".join(c for c in text.lower() if c.isalpha()))
            else:
                ll = list("".join(c for c in text.lower() if c.isalpha()))
            prov = build_kamea_path(
                letters=text, square_name=square, encoding=enc, letter_list=ll
            )
        else:
            prov = build_kamea_path(letters=text, square_name=square, encoding=enc)
        assert prov.original_numeric_sequence == data["original_numeric_sequence"]
        assert prov.reduced_numeric_sequence == data["reduced_numeric_sequence"]
        assert prov.path == data["path"]
        for cell in data["cell_check"]:
            assert cell["value"] == cell["expected"]


def test_intelligence_and_spirit_have_geometry():
    intel = intelligence_character("jupiter")
    spirit = spirit_character("jupiter")
    trad = traditional_seal_path("jupiter")
    # v0.9+: plate strokes default; traditional plate primary still 1..n² cells
    assert len(trad.path) == 16
    assert len(trad.strokes) >= 2
    assert len(intel.path) >= 2
    assert len(spirit.path) >= 2
    assert intel.path != trad.path
    assert spirit.path != trad.path
    assert intel.provenance.get("not_traditional_seal") is True
    assert intel.claimed_historical_status in (
        "stroke_digitization_plate_v1",
        "corpus_name_path_agrippan",
        "engine_reconstruction_documented",
    )


def test_source_manifest_exists():
    p = ROOT / "references" / "source-manifest.yaml"
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "hebrew_gematria" in text
    assert "modern_derivation" in text


def test_phonetic_and_construct(tmp_path: Path):
    seq = compress_phonetic("i maintain calm focus")
    assert seq
    art = build_phonetic_artifact("i maintain calm focus", intent_digest="ab" * 32)
    assert art["semantic_verification"] == "NOT_COMPUTABLE"
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        phonetic=True,
        kamea_encoding="latin_mod9_v1",
    )
    by = {c["id"]: c for c in packet["channels"]}
    assert by["phonetic_sigil"]["status"] == "applied"
    path = packet["artifacts"].get("phoneme_sequence_path")
    assert path and Path(path).is_file()


def test_pictorial_writes_seed(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        spare_mode="pictorial",
        kamea_encoding="latin_mod9_v1",
    )
    assert packet["artifacts"].get("spare_seed_path")
    assert Path(packet["artifacts"]["spare_seed_path"]).is_file()


def test_interop_fields(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        interop=True,
        kamea_encoding="latin_mod9_v1",
    )
    assert packet["interop"].get("intent_token")
    assert packet["interop"].get("sigil_glyph")


def test_doctor_and_eval_cli():
    r = subprocess.run(
        [sys.executable, str(CLI), "doctor"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    doc = json.loads(r.stdout)
    assert doc["ok"] is True
    assert doc["version"]

    r2 = subprocess.run(
        [sys.executable, str(CLI), "eval"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r2.returncode == 0, r2.stderr + r2.stdout
    ev = json.loads(r2.stdout)
    assert ev["ok"] is True


def test_negative_check_missing_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Structural: doctor reports missing required files when skill root incomplete."""
    # Build a fake empty skill root
    fake = tmp_path / "empty-skill"
    fake.mkdir()
    monkeypatch.setenv("HERMES_SKILL_DIR", str(fake))
    r = subprocess.run(
        [sys.executable, str(CLI), "doctor"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env={**dict(__import__("os").environ), "HERMES_SKILL_DIR": str(fake)},
    )
    assert r.returncode != 0
    doc = json.loads(r.stdout)
    assert doc["ok"] is False
    assert doc["missing"]
