from sigil_forge.normalize import normalize_intent
import pytest


def test_normalize_lower_strip_collapse_space():
    assert normalize_intent("  I Maintain Calm  Focus  ") == "i maintain calm focus"


def test_normalize_empty_raises():
    with pytest.raises(ValueError):
        normalize_intent("   ")


def test_normalize_keeps_letters_for_reduction():
    assert "sigil" in normalize_intent("Sigil-Forge ships.")
