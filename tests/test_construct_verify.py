"""Integration: construct pipeline + verify recover digest."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sigil_forge.construct import run as construct_run
from sigil_forge.verify import run as verify_run


def test_construct_and_verify(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        mode="creative",
        out_root=tmp_path,
        square="saturn",
    )
    svg = Path(packet["artifacts"]["svg"])
    assert svg.is_file()
    assert packet["intent_digest"]
    text = svg.read_text(encoding="utf-8")
    assert "i maintain calm" not in text.lower()
    v = verify_run(svg)
    assert v["ok"] is True
    assert v["intent_digest"] == packet["intent_digest"]


def test_construct_refuses_harm(tmp_path: Path):
    with pytest.raises(ValueError):
        construct_run("I will murder my neighbor tomorrow", out_root=tmp_path)


def test_construct_packet_fields_and_channels(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        mode="creative",
        out_root=tmp_path,
        square="saturn",
    )
    assert packet["schema_version"]
    assert packet["mode"] == "creative"
    assert packet["normalized_intent"]
    assert packet["intent_digest"]
    assert isinstance(packet["channels"], list)
    ids = {c["id"] for c in packet["channels"]}
    required = {
        "spare_monogram",
        "kamea_path",
        "kamea_square_choice",
        "bind_runes",
        "rose_cross_path",
        "intent_digest",
        "optional_ciphertext",
        "svg_metadata",
        "path_epsilon",
        "path_order",
        "metric_quantize",
        "png_lsb",
        "gen_seed",
    }
    assert required <= ids
    for c in packet["channels"]:
        assert c["status"] in ("applied", "skipped")
        assert "detail" in c
    assert Path(packet["artifacts"]["svg"]).is_file()
    assert Path(packet["artifacts"]["packet_json"]).is_file()
    assert "crypto" in packet
    assert packet["crypto"]["key_policy"] == "none"
    assert packet["crypto"]["ciphertext_present"] is False
    # forge-packet files written
    run_root = Path(packet["artifacts"]["svg"]).parent
    assert (run_root / "forge-packet.json").is_file()
    assert (run_root / "forge-packet.md").is_file()
    # craft channels applied for this intent
    by_id = {c["id"]: c for c in packet["channels"]}
    assert by_id["spare_monogram"]["status"] == "applied"
    assert by_id["kamea_path"]["status"] == "applied"
    assert by_id["kamea_square_choice"]["status"] == "applied"
    assert by_id["intent_digest"]["status"] == "applied"
    assert by_id["optional_ciphertext"]["status"] == "skipped"
    # gen_seed skipped unless construct(..., write_polish=True)
    assert by_id["gen_seed"]["status"] == "skipped"
    assert "polish" in by_id["gen_seed"]["detail"]


def test_construct_with_passphrase_seals(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        mode="practice",
        out_root=tmp_path,
        passphrase="test-passphrase-not-secret",
        square="saturn",
        seal_packet=True,
    )
    assert packet["mode"] == "practice"
    assert packet["crypto"]["key_policy"] == "passphrase"
    assert packet["crypto"]["ciphertext_present"] is True
    assert "normalized_intent" not in packet or packet.get("normalized_intent") is None
    by_id = {c["id"]: c for c in packet["channels"]}
    assert by_id["optional_ciphertext"]["status"] == "applied"
    v = verify_run(Path(packet["artifacts"]["svg"]))
    assert v["ok"] is True
    assert v["intent_digest"] == packet["intent_digest"]


def test_all_vowel_intent_not_computable(tmp_path: Path):
    """All-vowel + latin_mod9 → empty monogram and empty kamea → NOT_COMPUTABLE.

    With hebrew_gematria, vowels still transliterate; use latin_mod9_v1 to
    assert dual-craft emptiness for letter_monogram.
    """
    with pytest.raises(ValueError, match=r"^NOT_COMPUTABLE:") as ei:
        construct_run(
            "aeiou you",
            out_root=tmp_path,
            kamea_encoding="latin_mod9_v1",
            spare_mode="letter_monogram",
        )
    assert "rewrite" in str(ei.value).lower()


def test_verify_expected_digest_and_format(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        mode="creative",
        out_root=tmp_path,
        square="saturn",
    )
    svg = Path(packet["artifacts"]["svg"])
    digest = packet["intent_digest"]
    assert re.fullmatch(r"[0-9a-f]{64}", digest)

    ok = verify_run(svg, expected_digest=digest)
    assert ok["ok"] is True
    assert ok["intent_digest"] == digest

    bad = verify_run(svg, expected_digest="0" * 64)
    assert bad["ok"] is False
    assert "mismatch" in (bad.get("detail") or "").lower()

    invalid = verify_run(svg, expected_digest="not-a-digest")
    assert invalid["ok"] is False
    assert "expected-digest" in (invalid.get("detail") or "").lower() or "invalid" in (
        invalid.get("detail") or ""
    ).lower()

    # Metric cross-check: data-sf-metric values are digest nibble prefixes
    text = svg.read_text(encoding="utf-8")
    assert digest[:8] in text
    assert digest[8:16] in text
    v = verify_run(svg)
    assert v["ok"] is True
    assert v["metrics"], "verify must report the metric values it read"
    assert digest[:8] in v["metrics"]
