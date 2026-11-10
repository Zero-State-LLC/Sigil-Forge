"""Planetary kamea squares and pluggable name-path encodings.

Squares are classic Agrippa / Western occult planetary tables (orders 3–9).
Name-path encodings are explicit — see ``KAMEA_ENCODINGS`` and methods-kamea.md.

Encodings:
  - ``hebrew_gematria`` — historically aligned default for name-derived paths
  - ``latin_extended`` — modern latin 1..26 with reduction into square range
  - ``latin_mod9_v1`` — legacy 1–9 mapping (compatibility; NOT full Agrippan fidelity)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Stable Chaldean order: Saturn 3 … Luna 9
PLANET_ORDER: tuple[str, ...] = (
    "saturn",
    "jupiter",
    "mars",
    "sol",
    "venus",
    "mercury",
    "luna",
)

KAMEA_SQUARES: dict[str, list[list[int]]] = {
    "saturn": [
        [4, 9, 2],
        [3, 5, 7],
        [8, 1, 6],
    ],
    "jupiter": [
        [4, 14, 15, 1],
        [9, 7, 6, 12],
        [5, 11, 10, 8],
        [16, 2, 3, 13],
    ],
    "mars": [
        [11, 24, 7, 20, 3],
        [4, 12, 25, 8, 16],
        [17, 5, 13, 21, 9],
        [10, 18, 1, 14, 22],
        [23, 6, 19, 2, 15],
    ],
    "sol": [
        [6, 32, 3, 34, 35, 1],
        [7, 11, 27, 28, 8, 30],
        [19, 14, 16, 15, 23, 24],
        [18, 20, 22, 21, 17, 13],
        [25, 29, 10, 9, 26, 12],
        [36, 5, 33, 4, 2, 31],
    ],
    "venus": [
        [22, 47, 16, 41, 10, 35, 4],
        [5, 23, 48, 17, 42, 11, 29],
        [30, 6, 24, 49, 18, 36, 12],
        [13, 31, 7, 25, 43, 19, 37],
        [38, 14, 32, 1, 26, 44, 20],
        [21, 39, 8, 33, 2, 27, 45],
        [46, 15, 40, 9, 34, 3, 28],
    ],
    "mercury": [
        [8, 58, 59, 5, 4, 62, 63, 1],
        [49, 15, 14, 52, 53, 11, 10, 56],
        [41, 23, 22, 44, 45, 19, 18, 48],
        [32, 34, 35, 29, 28, 38, 39, 25],
        [40, 26, 27, 37, 36, 30, 31, 33],
        [17, 47, 46, 20, 21, 43, 42, 24],
        [9, 55, 54, 12, 13, 51, 50, 16],
        [64, 2, 3, 61, 60, 6, 7, 57],
    ],
    "luna": [
        [37, 78, 29, 70, 21, 62, 13, 54, 5],
        [6, 38, 79, 30, 71, 22, 63, 14, 46],
        [47, 7, 39, 80, 31, 72, 23, 55, 15],
        [16, 48, 8, 40, 81, 32, 64, 24, 56],
        [57, 17, 49, 9, 41, 73, 33, 65, 25],
        [26, 58, 18, 50, 1, 42, 74, 34, 66],
        [67, 27, 59, 10, 51, 2, 43, 75, 35],
        [36, 68, 19, 60, 11, 52, 3, 44, 76],
        [77, 28, 69, 20, 61, 12, 53, 4, 45],
    ],
}

# Default for *name-derived* historically-aligned paths
DEFAULT_KAMEA_ENCODING = "hebrew_gematria"
# Legacy default behavior used by older spare-letter paths
LEGACY_KAMEA_ENCODING = "latin_mod9_v1"

# Minimal latin → Hebrew letter transliteration for gematria (public mapping).
# Multi-letter digraphs first. Ambiguous / unmapped latin fails closed unless
# force_latin_skip=True (then letter is skipped with reduction note).
# Longest digraphs first. Policy: unmapped latin letters are skipped with a
# note (not invented). Empty result after transliteration is NOT_COMPUTABLE.
_LATIN_HEBREW: list[tuple[str, str]] = [
    ("sch", "ש"),
    ("tch", "צ"),
    ("tsh", "צ"),
    ("dsh", "דש"),  # rare; handled as two letters via digraph+letter if split fails
    ("sh", "ש"),
    ("ch", "ח"),
    ("th", "ת"),
    ("ts", "צ"),
    ("tz", "צ"),
    ("kh", "כ"),
    ("ph", "פ"),
    ("gh", "ג"),
    ("ng", "נג"),
    ("qu", "ק"),
    ("a", "א"),
    ("b", "ב"),
    ("c", "כ"),
    ("d", "ד"),
    ("e", "ה"),
    ("f", "פ"),
    ("g", "ג"),
    ("h", "ה"),
    ("i", "י"),
    ("j", "י"),
    ("k", "כ"),
    ("l", "ל"),
    ("m", "מ"),
    ("n", "נ"),
    ("o", "ו"),
    ("p", "פ"),
    ("q", "ק"),
    ("r", "ר"),
    ("s", "ס"),
    ("t", "ט"),
    ("u", "ו"),
    ("v", "ו"),
    ("w", "ו"),
    ("x", "קס"),  # expand to two letters in transliterate
    ("y", "י"),
    ("z", "ז"),
]

# Hebrew letter → absolute gematria value
HEBREW_VALUES: dict[str, int] = {
    "א": 1,
    "ב": 2,
    "ג": 3,
    "ד": 4,
    "ה": 5,
    "ו": 6,
    "ז": 7,
    "ח": 8,
    "ט": 9,
    "י": 10,
    "כ": 20,
    "ך": 20,
    "ל": 30,
    "מ": 40,
    "ם": 40,
    "נ": 50,
    "ן": 50,
    "ס": 60,
    "ע": 70,
    "פ": 80,
    "ף": 80,
    "צ": 90,
    "ץ": 90,
    "ק": 100,
    "ר": 200,
    "ש": 300,
    "ת": 400,
}


@dataclass
class ReductionOp:
    kind: str
    input: int
    output: int
    detail: str


@dataclass
class KameaPathProvenance:
    encoding_system: str
    transliteration_system: str
    original_numeric_sequence: list[int]
    reduced_numeric_sequence: list[int]
    reduction_operations: list[dict[str, Any]] = field(default_factory=list)
    square: str = ""
    path: list[list[float]] = field(default_factory=list)  # [[x,y], ...]
    claimed_historical_status: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def letter_to_number(ch: str) -> int:
    """Compatibility alias: latin_mod9_v1 single letter → 1–9."""
    return _latin_mod9_value(ch)


def _latin_mod9_value(ch: str) -> int:
    if not ch:
        raise ValueError("empty character")
    c = ch[0].lower()
    if c < "a" or c > "z":
        raise ValueError(f"not a letter: {ch!r}")
    return (ord(c) - ord("a")) % 9 + 1


def select_square(digest_hex: str, override: str | None = None) -> str:
    """Choose a planetary square: operator override, else digest mod 7."""
    if override is not None:
        key = override.strip().lower()
        if key not in KAMEA_SQUARES:
            allowed = ", ".join(PLANET_ORDER)
            raise ValueError(f"unknown square {override!r}; allowed: {allowed}")
        return key
    raw = (digest_hex or "").strip().lower()
    if not raw:
        raw = "0"
    try:
        n = int(raw, 16)
    except ValueError as e:
        raise ValueError(f"invalid digest_hex: {digest_hex!r}") from e
    return PLANET_ORDER[n % len(PLANET_ORDER)]


def square_order(square_name: str) -> int:
    key = square_name.strip().lower()
    if key not in KAMEA_SQUARES:
        raise ValueError(f"unknown square {square_name!r}")
    return len(KAMEA_SQUARES[key])


def square_max(square_name: str) -> int:
    n = square_order(square_name)
    return n * n


def _find_cell(square: list[list[int]], number: int) -> tuple[int, int] | None:
    for r, row in enumerate(square):
        for c, val in enumerate(row):
            if val == number:
                return r, c
    return None


def reduce_into_square(
    value: int,
    n_max: int,
    *,
    method: str = "digital_root_or_mod",
) -> tuple[int, list[ReductionOp]]:
    """Reduce a positive integer into 1..n_max inclusive.

    Primary: if value <= n_max, keep.
    Else digital root loop (sum of digits) while > n_max.
    If still > n_max (rare for n_max>=9), use ((value - 1) % n_max) + 1.
    """
    ops: list[ReductionOp] = []
    v = int(value)
    if v < 1:
        raise ValueError(f"value must be >= 1, got {v}")
    if v <= n_max:
        return v, ops
    # Aiq Beker / place-value style: repeatedly sum digits
    while v > n_max:
        digits = [int(d) for d in str(v)]
        nxt = sum(digits)
        ops.append(
            ReductionOp(
                kind="digit_sum",
                input=v,
                output=nxt,
                detail=f"sum({digits}) for square max {n_max}",
            )
        )
        if nxt == v:
            break
        v = nxt
    if v > n_max:
        nxt = ((v - 1) % n_max) + 1
        ops.append(
            ReductionOp(
                kind="mod_range",
                input=v,
                output=nxt,
                detail=f"(({v}-1) % {n_max}) + 1",
            )
        )
        v = nxt
    if v < 1 or v > n_max:
        raise ValueError(f"failed to reduce into 1..{n_max}: {value}")
    return v, ops


def transliterate_latin_to_hebrew(text: str) -> tuple[list[str], list[str]]:
    """Return (hebrew_letters, notes). Unmapped chars produce notes and are skipped.

    Digraphs are longest-first. Multi-letter Hebrew expansions (e.g. x→קס)
    append each letter. Empty output is allowed here; callers fail closed.
    """
    s = "".join(ch for ch in text.lower() if ch.isalpha() or ch.isspace())
    s = "".join(s.split())  # collapse spaces for sequential digraph scan
    hebrew: list[str] = []
    notes: list[str] = []
    i = 0
    while i < len(s):
        matched = False
        for lat, heb in _LATIN_HEBREW:
            if s.startswith(lat, i):
                # heb may be one or more Hebrew characters
                for hch in heb:
                    if hch in HEBREW_VALUES or hch in (
                        "ך",
                        "ם",
                        "ן",
                        "ף",
                        "ץ",
                    ):
                        hebrew.append(hch)
                    elif hch.strip():
                        notes.append(f"non_value_hebrew:{hch!r}")
                i += len(lat)
                matched = True
                break
        if not matched:
            notes.append(f"unmapped_latin:{s[i]!r}")
            i += 1
    return hebrew, notes


def encode_latin_mod9_v1(
    letters: list[str], square_name: str
) -> tuple[list[int], list[int], list[ReductionOp], list[str]]:
    """Legacy encoding: each latin letter → 1–9; no further reduction needed for n>=3."""
    original: list[int] = []
    reduced: list[int] = []
    ops: list[ReductionOp] = []
    notes: list[str] = []
    n_max = square_max(square_name)
    for ch in letters:
        if not ch or not ch[0].isalpha():
            continue
        try:
            num = _latin_mod9_value(ch)
        except ValueError:
            notes.append(f"skip:{ch!r}")
            continue
        original.append(num)
        # Still record explicit reduce if ever > n_max (won't for n>=3)
        r, rops = reduce_into_square(num, n_max)
        ops.extend(rops)
        reduced.append(r)
    return original, reduced, ops, notes


def encode_latin_extended(
    letters: list[str], square_name: str
) -> tuple[list[int], list[int], list[ReductionOp], list[str]]:
    """Modern: A=1..Z=26 then reduce into square range."""
    original: list[int] = []
    reduced: list[int] = []
    ops: list[ReductionOp] = []
    notes: list[str] = []
    n_max = square_max(square_name)
    for ch in letters:
        if not ch or not ch[0].isalpha():
            continue
        c = ch[0].lower()
        if c < "a" or c > "z":
            notes.append(f"skip:{ch!r}")
            continue
        num = ord(c) - ord("a") + 1  # 1..26
        original.append(num)
        r, rops = reduce_into_square(num, n_max)
        ops.extend(rops)
        reduced.append(r)
    return original, reduced, ops, notes


def _extract_hebrew_letters(text: str) -> list[str]:
    """Pull Hebrew letters (including final forms) from mixed text."""
    out: list[str] = []
    for ch in text:
        if ch in HEBREW_VALUES:
            out.append(ch)
        elif ch in ("ך", "ם", "ן", "ף", "ץ"):
            # finals map in HEBREW_VALUES if present; else skip with caller notes
            out.append(ch)
    return out


def encode_hebrew_gematria(
    text: str, square_name: str
) -> tuple[list[int], list[int], list[ReductionOp], list[str], str]:
    """Hebrew gematria values; reduce into square.

    Prefer native Hebrew letters when present in ``text``; otherwise latin→Hebrew
    transliteration. Returns original, reduced, ops, notes, transliteration_system id.
    """
    notes: list[str] = []
    native = _extract_hebrew_letters(text)
    if native:
        hebrew = native
        translit = "native_hebrew"
        notes.append("used_native_hebrew_letters")
    else:
        hebrew, notes = transliterate_latin_to_hebrew(text)
        translit = "latin_to_hebrew_minimal_v1"
    if not hebrew:
        raise ValueError(
            "NOT_COMPUTABLE: no hebrew letters after transliteration "
            "(cannot encode hebrew_gematria for this text)"
        )
    original: list[int] = []
    reduced: list[int] = []
    ops: list[ReductionOp] = []
    n_max = square_max(square_name)
    for h in hebrew:
        if h not in HEBREW_VALUES:
            notes.append(f"unknown_hebrew:{h!r}")
            continue
        val = HEBREW_VALUES[h]
        original.append(val)
        r, rops = reduce_into_square(val, n_max)
        for op in rops:
            ops.append(op)
        if val != r and not rops:
            ops.append(
                ReductionOp(
                    kind="identity",
                    input=val,
                    output=r,
                    detail="already in range",
                )
            )
        reduced.append(r)
    if not reduced:
        raise ValueError("NOT_COMPUTABLE: no numeric values after hebrew gematria")
    return original, reduced, ops, notes, translit


KAMEA_ENCODINGS: dict[str, str] = {
    "hebrew_gematria": "Hebrew letter gematria + reduction into square (historical default for name paths)",
    "latin_extended": "Latin A=1..Z=26 with reduction into square (modern adaptation)",
    "latin_mod9_v1": "Legacy 1–9 digital mapping (compatibility; not full Agrippan fidelity)",
}


def plot_path(letters: list[str], square_name: str) -> list[tuple[float, float]]:
    """Backward-compatible path using latin_mod9_v1 (legacy behavior)."""
    prov = build_kamea_path(
        letters="".join(letters),
        square_name=square_name,
        encoding="latin_mod9_v1",
        letter_list=letters,
    )
    return [(p[0], p[1]) for p in prov.path]


def build_kamea_path(
    *,
    letters: str,
    square_name: str,
    encoding: str = DEFAULT_KAMEA_ENCODING,
    letter_list: list[str] | None = None,
) -> KameaPathProvenance:
    """Build a kamea name/intent path with full encoding provenance.

    ``letters`` is free text used for hebrew transliteration.
    ``letter_list`` if provided is used for latin encodings (spare sequence).
    """
    key = square_name.strip().lower()
    if key not in KAMEA_SQUARES:
        allowed = ", ".join(PLANET_ORDER)
        raise ValueError(f"unknown square {square_name!r}; allowed: {allowed}")
    enc = (encoding or DEFAULT_KAMEA_ENCODING).strip().lower()
    if enc not in KAMEA_ENCODINGS:
        raise ValueError(
            f"unknown kamea encoding {encoding!r}; allowed: {', '.join(KAMEA_ENCODINGS)}"
        )

    latin_letters = letter_list if letter_list is not None else list(
        "".join(ch for ch in letters.lower() if ch.isalpha())
    )

    if enc == "latin_mod9_v1":
        original, reduced, ops, notes = encode_latin_mod9_v1(latin_letters, key)
        translit = "latin_identity"
        hist = "modern_compatibility_mod9"
    elif enc == "latin_extended":
        original, reduced, ops, notes = encode_latin_extended(latin_letters, key)
        translit = "latin_identity"
        hist = "modern_adaptation"
    else:  # hebrew_gematria
        original, reduced, ops, notes, translit = encode_hebrew_gematria(letters, key)
        hist = "historically_aligned_agrippan_style"

    square = KAMEA_SQUARES[key]
    path: list[list[float]] = []
    for num in reduced:
        cell = _find_cell(square, num)
        if cell is None:
            notes.append(f"missing_cell_for:{num}")
            continue
        r, c = cell
        path.append([float(c + 0.5), float(r + 0.5)])

    return KameaPathProvenance(
        encoding_system=enc,
        transliteration_system=translit,
        original_numeric_sequence=original,
        reduced_numeric_sequence=reduced,
        reduction_operations=[asdict(o) for o in ops],
        square=key,
        path=path,
        claimed_historical_status=hist,
        notes=notes,
    )
