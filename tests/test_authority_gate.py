"""Authority-seal exclusion gates: construct and wizard refuse Goetic/Enochian."""

import pytest
from sigil_forge.construct import run as construct_run
from sigil_forge.wizard import next_step


def test_construct_refuses_enochian_request(tmp_path):
    with pytest.raises(ValueError) as ei:
        construct_run(
            "forge an Enochian seal for the air tablet",
            out_root=tmp_path,
        )
    assert "enochian" in str(ei.value).lower() or "authority" in str(ei.value).lower()


def test_construct_refuses_goetic_request(tmp_path):
    with pytest.raises(ValueError) as ei:
        construct_run("draw a goetic seal of binding", out_root=tmp_path)
    msg = str(ei.value).lower()
    assert "goetic" in msg or "authority" in msg or "excluded" in msg


def test_wizard_next_refuses_authority_intent():
    nxt = next_step({"intent": "I need an Enochian watchtower seal"}, path="quick")
    assert nxt.get("refused") is True
    assert nxt.get("done") is True
