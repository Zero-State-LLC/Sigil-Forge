"""The suite runs against a throwaway state root, never the operator's (#33)."""

from __future__ import annotations

import os
from pathlib import Path

from sigil_forge import receipt
from sigil_forge.paths import default_state_root


def test_session_state_root_is_a_temp_dir_outside_home_state():
    root = default_state_root()
    assert root == Path(os.environ["SIGIL_FORGE_STATE_DIR"]).resolve()
    real = (Path.home() / ".hermes" / "state" / "sigil-forge").resolve()
    assert real != root and real not in root.parents


def test_default_receipt_log_is_under_the_session_state_root():
    assert default_state_root() in receipt.default_receipts_path().resolve().parents
