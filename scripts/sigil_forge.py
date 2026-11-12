#!/usr/bin/env python3
"""Run the Sigil-Forge CLI from a checkout or a Hermes skill tree.

The engine lives in the ``sigil_forge`` package under ``<root>/src``. This
file keeps ``python3 scripts/sigil_forge.py <args>`` working. Run as a script,
``sys.path[0]`` is ``scripts/``, where this file would shadow the package, so
that entry is removed and ``<root>/src`` goes first.
"""

import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != _here]
sys.path.insert(0, str(_here.parent / "src"))

from sigil_forge.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
