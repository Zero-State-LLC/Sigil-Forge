from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import tempfile


_ROOT_ENV = ("SIGIL_FORGE_HOME", "SIGIL_FORGE_ROOT", "SIGIL_FORGE_DIR", "SIGIL_FORGE_SKILL_DIR")


def _first_set(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def configured_root() -> Path | None:
    """Install root named by the environment, or None to use this checkout.

    First set of ``_ROOT_ENV`` wins, then the Hermes ``HERMES_SKILL_DIR``.
    """
    value = _first_set(_ROOT_ENV) or os.environ.get("HERMES_SKILL_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return None


def skill_root() -> Path:
    return configured_root() or Path(__file__).resolve().parent.parent


def default_state_root() -> Path:
    """Where private state (products, wizard sessions) lives.

    Order: ``SIGIL_FORGE_STATE_DIR``; then ``<root>/state`` when one of the
    ``SIGIL_FORGE_*`` root variables is set (``HERMES_SKILL_DIR`` alone does
    not count); otherwise the long-standing default
    ``(HERMES_HOME or ~/.hermes)/state/sigil-forge``. With none of the new
    variables set, behaviour is identical to earlier releases.
    """
    state = os.environ.get("SIGIL_FORGE_STATE_DIR")
    if state:
        return Path(state).expanduser().resolve()
    root = _first_set(_ROOT_ENV)
    if root:
        return Path(root).expanduser().resolve() / "state"
    home = Path(os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes"))
    return home.expanduser().resolve() / "state" / "sigil-forge"


def default_session_dir() -> Path:
    return default_state_root() / "wizard-sessions"


def default_out_dir() -> Path:
    return default_state_root() / "products"


def make_run_id(digest_hex: str, when: datetime | None = None) -> str:
    ts = (when or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    prefix = (digest_hex or "0" * 8)[:8].lower()
    return f"{ts}-{prefix}"


def run_dir(out_root: Path, run_id: str) -> Path:
    return Path(out_root) / run_id


def ensure_private_dir(path: Path) -> Path:
    """Create ``path`` for private state; directories this call creates are 0700.

    Existing directories keep their mode: an operator-chosen location is theirs.
    """
    path = Path(path)
    for p in reversed((path, *path.parents)):
        if p.is_dir():
            continue
        try:
            os.mkdir(p, 0o700)
        except FileExistsError:
            continue  # existing or concurrently created: leave its mode alone
        try:
            os.chmod(p, 0o700)
        except OSError:
            pass
    if not path.is_dir():
        raise NotADirectoryError(str(path))
    return path


def write_private_text(path: Path, text: str) -> None:
    """Atomically write ``text`` to a file only the owner can read (0600)."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
