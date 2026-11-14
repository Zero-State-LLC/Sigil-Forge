import pytest

from sigil_forge.policy_lint import (
    detect_authority_seal_request,
    lint_efficacy_text,
    assert_no_efficacy,
)


def test_efficacy_flags_works_and_manifests():
    hits = lint_efficacy_text("This sigil works and manifests wealth")
    assert hits
    assert any("efficacy" in h.lower() or "works" in h.lower() for h in hits)


def test_efficacy_allows_craft_language():
    hits = lint_efficacy_text(
        "Methods are craft history and symbolic compression; verify recovers digest."
    )
    assert hits == []


def test_authority_detects_enochian_and_goetic():
    ok, fam = detect_authority_seal_request("please forge an Enochian seal for the tablet")
    assert ok is True
    assert fam in ("enochian_seal", "authority_seal", "goetic_seal") or fam
    ok2, fam2 = detect_authority_seal_request("make a goetic seal of a spirit")
    assert ok2 is True


def test_authority_allows_intent_language():
    ok, _ = detect_authority_seal_request("I maintain calm focus while shipping")
    assert ok is False


def test_assert_no_efficacy_raises():
    with pytest.raises(ValueError) as caught:
        assert_no_efficacy("guarantees results every time", field="framing_notes")
    message = str(caught.value)
    assert "framing_notes" in message or "efficacy" in message.lower()
