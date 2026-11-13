import sys
from pathlib import Path

# The engine is the sigil_forge package under src/ (import sigil_forge.<module>).
_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root / "src"))


# Tests must never write to the operator's real state (issue #33). Every
# construct call appends a receipt to the default log, so give the whole
# session a throwaway state root. A test that needs a different one sets or
# removes SIGIL_FORGE_STATE_DIR itself (monkeypatch restores this value).
import atexit as _atexit
import os as _os
import shutil as _shutil
import tempfile as _tempfile

_state = _tempfile.mkdtemp(prefix="sigil-forge-test-state-")
_atexit.register(_shutil.rmtree, _state, ignore_errors=True)
_os.environ["SIGIL_FORGE_STATE_DIR"] = _state
for _name in ("SIGIL_FORGE_RECEIPTS", "SIGIL_FORGE_LEDGER", "SIGIL_FORGE_CANON_PROPOSALS"):
    _os.environ.pop(_name, None)
