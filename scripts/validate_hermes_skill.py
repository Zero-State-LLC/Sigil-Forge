#!/usr/bin/env python3
"""Validate SKILL.md frontmatter: thin shim for ``sigil_forge.validate_hermes_skill``.

Kept at this path because install.sh, CI and the install transaction run
``python3 scripts/validate_hermes_skill.py``. Output and exit codes are the
package module's. ``scripts/`` is dropped from ``sys.path`` so the
``scripts/sigil_forge.py`` shim cannot shadow the package.
"""

import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != _here]
sys.path.insert(0, str(_here.parent / "src"))

from sigil_forge.validate_hermes_skill import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
