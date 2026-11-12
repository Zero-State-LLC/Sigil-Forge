"""Load planetary intelligence/spirit character corpus (stdlib JSON)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from paths import skill_root

CORPUS_REL = Path("references") / "planetary-character-corpus.json"
KIND_TO_ROLE = {
    "intelligence_character": "intelligence",
    "spirit_character": "spirit",
    "traditional_seal": "traditional_seal",
}


@lru_cache(maxsize=1)
def load_corpus() -> dict[str, Any]:
    path = skill_root() / CORPUS_REL
    if not path.is_file():
        raise FileNotFoundError(f"planetary character corpus missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("planets"), dict):
        raise ValueError("corpus missing planets map")
    return data


def corpus_path() -> Path:
    return skill_root() / CORPUS_REL


def planet_entry(planet: str) -> dict[str, Any]:
    key = (planet or "").strip().lower()
    planets = load_corpus()["planets"]
    if key not in planets:
        raise ValueError(f"planet {planet!r} not in character corpus")
    return planets[key]


def role_entry(planet: str, kind: str) -> dict[str, Any]:
    role = KIND_TO_ROLE.get((kind or "").strip().lower())
    if role is None:
        raise ValueError(f"unknown character kind {kind!r}")
    entry = planet_entry(planet)
    if role not in entry:
        raise ValueError(f"corpus planet {planet!r} missing role {role!r}")
    return entry[role]


def entity_name_for_path(role: dict[str, Any]) -> tuple[str, str]:
    """Return (name_for_encoding, name_source_label). Prefer Hebrew when present."""
    he = (role.get("name_hebrew") or "").strip()
    la = (role.get("name_latin") or "").strip()
    if he:
        return he, "name_hebrew"
    if la:
        return la, "name_latin"
    raise ValueError("role missing name_hebrew and name_latin")


def list_corpus_summary() -> list[dict[str, Any]]:
    data = load_corpus()
    out: list[dict[str, Any]] = []
    for planet, entry in data["planets"].items():
        intel = entry.get("intelligence") or {}
        spirit = entry.get("spirit") or {}
        out.append(
            {
                "planet": planet,
                "order": entry.get("order"),
                "intelligence": intel.get("name_latin"),
                "intelligence_number": intel.get("number"),
                "spirit": spirit.get("name_latin"),
                "spirit_number": spirit.get("number"),
            }
        )
    return out
