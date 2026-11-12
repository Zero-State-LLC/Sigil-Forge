"""Agrippan planetary seals/characters — distinct from kamea name paths.

Geometry preference (``geometry`` / auto):
  1. **plate** — stroke-faithful multi-stroke plate digitizations
  2. **name_on_kamea** — corpus intelligence/spirit names on the square
  3. **reconstruction** — successive / odds-evens / reverse fallbacks

Traditional seals: plate = successive path + kamea frame + ticks.
Intelligence/spirit: plate strokes from references/planetary-plate-strokes.json.

Not Goetic/Enochian authority seals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from kamea import KAMEA_SQUARES, PLANET_ORDER, build_kamea_path, select_square
from planetary_corpus import entity_name_for_path, load_corpus, role_entry
from plate_strokes import flatten_primary, resolve_plate_entry


GEOMETRY_MODES = ("auto", "plate", "name_on_kamea", "reconstruction")


@dataclass
class PlanetarySealArtifact:
    planet: str
    artifact_class: str  # traditional_seal | intelligence_character | spirit_character
    path: list[list[float]]
    successive_values: list[int]
    claimed_historical_status: str
    notes: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    entity_name: str | None = None
    entity_number: int | None = None
    strokes: list[list[list[float]]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _find_cell(square: list[list[int]], number: int) -> tuple[int, int] | None:
    for r, row in enumerate(square):
        for c, val in enumerate(row):
            if val == number:
                return r, c
    return None


def _path_for_values(square: list[list[int]], values: list[int]) -> list[list[float]]:
    path: list[list[float]] = []
    for v in values:
        cell = _find_cell(square, v)
        if cell is None:
            raise ValueError(f"kamea missing value {v}")
        r, c = cell
        path.append([float(c + 0.5), float(r + 0.5)])
    return path


def _from_plate(planet: str, kind: str) -> PlanetarySealArtifact | None:
    plate = resolve_plate_entry(planet, kind)
    if not plate:
        return None
    strokes = plate.get("strokes") or []
    primary = plate.get("primary_path") or flatten_primary(strokes)
    if not primary and not strokes:
        return None
    entity_name = plate.get("entity_name_latin")
    entity_number = plate.get("entity_number")
    if entity_name is None or entity_number is None:
        try:
            role = role_entry(planet, kind)
            entity_name = entity_name or role.get("name_latin")
            entity_number = entity_number if entity_number is not None else role.get("number")
        except ValueError:
            pass
    notes = [
        f"Plate geometry ({plate.get('construction')})",
        f"fidelity={plate.get('fidelity')}",
        "Distinct from kamea_path(intent)",
    ]
    notes.extend(str(n) for n in (plate.get("notes") or []))
    return PlanetarySealArtifact(
        planet=planet.strip().lower(),
        artifact_class=kind,
        path=[[float(p[0]), float(p[1])] for p in primary],
        successive_values=[int(v) for v in (plate.get("successive_values") or [])],
        claimed_historical_status=str(
            plate.get("claimed_historical_status") or "stroke_digitization_plate_v1"
        ),
        notes=notes,
        entity_name=str(entity_name) if entity_name else None,
        entity_number=int(entity_number) if entity_number is not None else None,
        strokes=[[[float(x), float(y)] for x, y in poly] for poly in strokes],
        provenance={
            "method_id": f"planetary.{kind}.{planet.strip().lower()}",
            "status": "plate_stroke_digitization",
            "family": "planetary_character",
            "determinism": "deterministic",
            "not_kamea_name_path": True,
            "not_traditional_seal": kind != "traditional_seal",
            "construction": plate.get("construction"),
            "coordinate_space": plate.get("coordinate_space"),
            "source_coordinate_space": plate.get("source_coordinate_space"),
            "fidelity": plate.get("fidelity"),
            "source": plate.get("source"),
            "plate_corpus_id": plate.get("plate_corpus_id"),
            "stroke_count": len(strokes),
            "generated": bool(plate.get("generated")),
            "entity_name_latin": entity_name,
            "entity_number": entity_number,
        },
    )


def traditional_seal_path(
    planet: str,
    *,
    geometry: str = "auto",
) -> PlanetarySealArtifact:
    """Traditional planetary seal (plate-first by default)."""
    key = planet.strip().lower()
    if key not in KAMEA_SQUARES:
        raise ValueError(f"unknown planet {planet!r}; allowed: {', '.join(PLANET_ORDER)}")
    mode = (geometry or "auto").strip().lower()
    if mode not in GEOMETRY_MODES:
        raise ValueError(f"unknown geometry {geometry!r}; allowed: {', '.join(GEOMETRY_MODES)}")

    if mode in ("auto", "plate"):
        plate = _from_plate(key, "traditional_seal")
        if plate is not None:
            return plate
        if mode == "plate":
            raise ValueError(f"plate geometry unavailable for traditional_seal/{key}")

    # Bare successive reconstruction
    square = KAMEA_SQUARES[key]
    n = len(square)
    n_max = n * n
    values = list(range(1, n_max + 1))
    path = _path_for_values(square, values)
    return PlanetarySealArtifact(
        planet=key,
        artifact_class="traditional_seal",
        path=path,
        successive_values=values,
        claimed_historical_status="historically_aligned_agrippan_character",
        notes=[
            "Path follows successive integers 1..n² on the planetary kamea",
            "Distinct artifact class from kamea_path(intent/name)",
        ],
        strokes=[path],
        provenance={
            "source": "Agrippa Book II planetary tables → seal reconstruction",
            "method_id": f"planetary.traditional_seal.{key}",
            "family": "planetary_character",
            "determinism": "deterministic",
            "not_kamea_name_path": True,
            "construction": "successive_1_to_n2",
            "status": "shipped",
            "corpus_id": load_corpus().get("corpus_id"),
        },
    )


def _reconstruction_intelligence(planet: str) -> PlanetarySealArtifact:
    key = planet.strip().lower()
    square = KAMEA_SQUARES[key]
    n_max = len(square) ** 2
    odds = [v for v in range(1, n_max + 1) if v % 2 == 1]
    evens = [v for v in range(1, n_max + 1) if v % 2 == 0]
    values = odds + evens
    path = _path_for_values(square, values)
    return PlanetarySealArtifact(
        planet=key,
        artifact_class="intelligence_character",
        path=path,
        successive_values=values,
        claimed_historical_status="engine_reconstruction_documented",
        notes=[
            "Fallback reconstruction: odd cells then even cells on the kamea",
            "Not a unique manuscript seal claim",
        ],
        strokes=[path],
        provenance={
            "method_id": f"planetary.intelligence_character.{key}",
            "status": "fallback_reconstruction",
            "family": "planetary_character",
            "determinism": "deterministic",
            "not_kamea_name_path": True,
            "not_traditional_seal": True,
            "construction": "odds_then_evens",
        },
    )


def _reconstruction_spirit(planet: str) -> PlanetarySealArtifact:
    key = planet.strip().lower()
    square = KAMEA_SQUARES[key]
    n_max = len(square) ** 2
    values = list(range(n_max, 0, -1))
    path = _path_for_values(square, values)
    return PlanetarySealArtifact(
        planet=key,
        artifact_class="spirit_character",
        path=path,
        successive_values=values,
        claimed_historical_status="engine_reconstruction_documented",
        notes=[
            "Fallback reconstruction: reverse successive path n²→1 on the kamea",
            "Not a unique manuscript seal claim",
        ],
        strokes=[path],
        provenance={
            "method_id": f"planetary.spirit_character.{key}",
            "status": "fallback_reconstruction",
            "family": "planetary_character",
            "determinism": "deterministic",
            "not_kamea_name_path": True,
            "not_traditional_seal": True,
            "construction": "reverse_successive",
        },
    )


def _name_on_kamea_character(
    planet: str,
    *,
    kind: str,
) -> PlanetarySealArtifact | None:
    """Build intelligence/spirit path from corpus name on planetary kamea."""
    key = planet.strip().lower()
    try:
        role = role_entry(key, kind)
    except ValueError:
        return None
    try:
        name, name_src = entity_name_for_path(role)
    except ValueError:
        return None

    try:
        prov = build_kamea_path(
            letters=name,
            square_name=key,
            encoding="hebrew_gematria",
        )
    except ValueError:
        return None

    if not prov.path or not prov.reduced_numeric_sequence:
        return None

    corpus = load_corpus()
    entity_number = role.get("number")
    try:
        entity_number_i = int(entity_number) if entity_number is not None else None
    except (TypeError, ValueError):
        entity_number_i = None

    path = [[float(p[0]), float(p[1])] for p in prov.path]
    notes = [
        f"Corpus {kind} via name_on_kamea ({name_src}={name!r})",
        "Distinct from kamea_path(intent) and traditional planetary seal",
    ]
    for n in role.get("notes") or []:
        notes.append(str(n))
    if name_src == "name_hebrew":
        notes.append(f"latin label: {role.get('name_latin')}")

    return PlanetarySealArtifact(
        planet=key,
        artifact_class=kind,
        path=path,
        successive_values=list(prov.reduced_numeric_sequence),
        claimed_historical_status="corpus_name_path_agrippan",
        notes=notes,
        entity_name=str(role.get("name_latin") or name),
        entity_number=entity_number_i,
        strokes=[path],
        provenance={
            "method_id": f"planetary.{kind}.{key}",
            "status": "corpus_name_on_kamea",
            "family": "planetary_character",
            "determinism": "deterministic",
            "not_kamea_name_path": True,
            "not_traditional_seal": True,
            "construction": "name_on_kamea",
            "corpus_id": corpus.get("corpus_id"),
            "entity_name_latin": role.get("name_latin"),
            "entity_name_hebrew": role.get("name_hebrew"),
            "entity_number": entity_number_i,
            "name_source": name_src,
            "encoding_system": prov.encoding_system,
            "original_numeric_sequence": list(prov.original_numeric_sequence),
            "reduced_numeric_sequence": list(prov.reduced_numeric_sequence),
            "source_tradition": corpus.get("source_tradition"),
        },
    )


def _entity_character(
    planet: str,
    *,
    kind: str,
    geometry: str = "auto",
) -> PlanetarySealArtifact:
    key = planet.strip().lower()
    if key not in KAMEA_SQUARES:
        raise ValueError(f"unknown planet {planet!r}")
    mode = (geometry or "auto").strip().lower()
    if mode not in GEOMETRY_MODES:
        raise ValueError(f"unknown geometry {geometry!r}")

    order: list[str]
    if mode == "auto":
        order = ["plate", "name_on_kamea", "reconstruction"]
    else:
        order = [mode]

    last_err: str | None = None
    for step in order:
        if step == "plate":
            art = _from_plate(key, kind)
            if art is not None:
                return art
            last_err = "plate unavailable"
        elif step == "name_on_kamea":
            art = _name_on_kamea_character(key, kind=kind)
            if art is not None:
                return art
            last_err = "name_on_kamea unavailable"
        elif step == "reconstruction":
            fb = (
                _reconstruction_intelligence(key)
                if kind == "intelligence_character"
                else _reconstruction_spirit(key)
            )
            fb.notes.insert(0, f"geometry fallback after: {last_err or 'prior modes'}")
            fb.provenance["corpus_id"] = load_corpus().get("corpus_id")
            try:
                role = role_entry(key, kind)
                fb.entity_name = role.get("name_latin")
                fb.entity_number = role.get("number")
                fb.provenance["entity_name_latin"] = role.get("name_latin")
                fb.provenance["entity_number"] = role.get("number")
            except ValueError:
                pass
            return fb

    raise ValueError(f"no geometry for {kind}/{key} (mode={mode})")


def intelligence_character(
    planet: str, *, geometry: str = "auto"
) -> PlanetarySealArtifact:
    return _entity_character(
        planet, kind="intelligence_character", geometry=geometry
    )


def spirit_character(planet: str, *, geometry: str = "auto") -> PlanetarySealArtifact:
    return _entity_character(planet, kind="spirit_character", geometry=geometry)


# Back-compat aliases
def intelligence_character_stub(planet: str) -> PlanetarySealArtifact:
    return intelligence_character(planet)


def spirit_character_stub(planet: str) -> PlanetarySealArtifact:
    return spirit_character(planet)


def seal_for(
    planet: str,
    *,
    kind: str = "traditional_seal",
    digest_hex: str | None = None,
    geometry: str = "auto",
) -> PlanetarySealArtifact:
    """Factory with geometry preference (auto|plate|name_on_kamea|reconstruction)."""
    if planet in (None, "", "auto") and digest_hex:
        planet = select_square(digest_hex)
    kind = (kind or "traditional_seal").strip().lower()
    if kind == "traditional_seal":
        return traditional_seal_path(planet, geometry=geometry)
    if kind == "intelligence_character":
        return intelligence_character(planet, geometry=geometry)
    if kind == "spirit_character":
        return spirit_character(planet, geometry=geometry)
    raise ValueError(f"unknown planetary seal kind {kind!r}")
