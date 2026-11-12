import sys
from pathlib import Path

# The engine is the sigil_forge package under src/ (import sigil_forge.<module>).
_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root / "src"))
