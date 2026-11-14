import os
import tempfile

# These tests compare paths the installer reports (always resolved) with paths
# built from the temp dir. On macOS the default temp dir sits behind the
# /var -> /private/var system link, so hand out the resolved location.
tempfile.tempdir = os.path.realpath(tempfile.gettempdir())


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
# A passphrase or command left in the developer's shell would change what
# construct does (sealing, proofs, backgrounds) and fail unrelated tests.
for _name in (
    "SIGIL_FORGE_RECEIPTS",
    "SIGIL_FORGE_LEDGER",
    "SIGIL_FORGE_CANON_PROPOSALS",
    "SIGIL_FORGE_PASSPHRASE",
    "SIGIL_FORGE_BG_COMMAND",
    "SIGIL_FORGE_AES_BACKEND",
):
    _os.environ.pop(_name, None)
