"""Fail-closed efficacy lint on forge packets and polish prompt packages."""

from __future__ import annotations

import pytest

from sigil_forge.packet import build_packet, framing_notes
from sigil_forge.policy_lint import assert_no_efficacy, lint_efficacy_text
from sigil_forge.prompt_polish import build_prompt


def test_builtin_framing_notes_clean():
    for mode in ("creative", "practice"):
        assert lint_efficacy_text(framing_notes(mode)) == []


def test_build_packet_lints_framing_notes():
    """Assembled packet framing_notes must pass efficacy policy."""
    packet = build_packet(
        mode="creative",
        intent_digest="a" * 64,
        channels=[],
        methods={},
        artifacts={},
        crypto={},
        verify_cmd="verify",
    )
    assert lint_efficacy_text(packet["framing_notes"]) == []
    assert_no_efficacy(packet["framing_notes"], field="framing_notes")


def test_polish_prompt_rejects_efficacy():
    """Bad free-style text that is concatenated into the package must fail closed."""
    bad = "a sigil that guarantees results and contacts spirits"
    hits = lint_efficacy_text(bad)
    assert hits

    with pytest.raises(ValueError, match="efficacy_policy_violation|polish"):
        build_prompt(
            {"intent_digest": "abcd" * 16, "stroke_count": 2},
            style=bad,
        )


def test_polish_prompt_package_strings_clean():
    """Default package string fields must not contain banned efficacy phrases."""
    package = build_prompt(
        {
            "intent_digest": "deadbeef" + "0" * 56,
            "stroke_count": 3,
            "bbox": {"x": 10.0, "y": 12.0, "width": 80.0, "height": 76.0},
        },
        style="ink on parchment",
    )
    for key in ("prompt", "negative", "geometry_lock", "style"):
        val = package.get(key)
        if isinstance(val, str):
            assert lint_efficacy_text(val) == [], f"{key}: {val!r}"
