"""First-class sigil method ontology for forge packets.

Distinguishes intent compression, name paths, planetary characters, ligatures,
and encoded carriers so these never silently substitute for one another.
"""

from __future__ import annotations

from typing import Any

# Families that may appear on a default forge packet
FAMILY_INTENT_COMPRESSION = "intent_compression"
FAMILY_NAME_PATH = "name_path"
FAMILY_PLANETARY_CHARACTER = "planetary_character"
FAMILY_ALPHABETIC_LIGATURE = "alphabetic_ligature"
FAMILY_ENCODED_CARRIER = "encoded_carrier"
FAMILY_INTUITIVE_SYMBOL = "intuitive_symbol"

# Explicitly excluded from default forge (namespace only)
EXCLUDED_DEFAULT_FAMILIES = frozenset(
    {
        "entity_identifier",  # Goetic, etc.
        "enochian_seal",
        "goetic_seal",
        "authority_seal",
    }
)

SPARE_MODES = {
    "letter_monogram": {
        "determinism": "deterministic",
        "status": "shipped",
        "description": "Letter simplification → combined monogram (default)",
    },
    "pictorial": {
        "determinism": "assisted",
        "status": "registered_deferred",
        "description": "Pictorial/automatic drawing; semantic verify NOT_COMPUTABLE",
    },
    "automatic_form": {
        "determinism": "assisted",
        "status": "registered_deferred",
        "description": "Automatic form generation from digest seed constraints",
    },
    "alphabet_of_desire": {
        "determinism": "corpus_backed",
        "status": "registered_deferred",
        "description": "Alphabet of Desire treatment (later corpus)",
    },
    "phonetic_mantric": {
        "determinism": "assisted",
        "status": "registered_deferred",
        "description": "Phonetic/mantric compression (non-visual channel)",
    },
    "hybrid": {
        "determinism": "assisted",
        "status": "registered_deferred",
        "description": "Hybrid Spare modes",
    },
}


def method_record(
    *,
    family: str,
    method_id: str,
    construction_type: str,
    determinism: str,
    alphabet: str | None = None,
    numeric_system: str | None = None,
    claimed_historical_status: str,
    verification_method: str,
    source_tradition: str | None = None,
    historical_period: str | None = None,
    artifact_role: str | None = None,
    geometry: str | None = None,
    source_refs: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if family in EXCLUDED_DEFAULT_FAMILIES:
        raise ValueError(
            f"family {family!r} is excluded from the default forge namespace"
        )
    rec: dict[str, Any] = {
        "family": family,
        "method_id": method_id,
        "construction_type": construction_type,
        "determinism": determinism,
        "alphabet": alphabet,
        "numeric_system": numeric_system,
        "claimed_historical_status": claimed_historical_status,
        "verification_method": verification_method,
        "source_tradition": source_tradition,
        "historical_period": historical_period,
        "artifact_role": artifact_role,
        "geometry": geometry,
        "source_refs": source_refs or [],
    }
    if extra:
        rec["extra"] = extra
    return rec


def default_packet_ontology(
    *,
    spare_mode: str = "letter_monogram",
    kamea_encoding: str = "hebrew_gematria",
    include_bind: bool = True,
    include_rose: bool = True,
    include_planetary_seal: bool = False,
    planet: str | None = None,
    planetary_seal_kind: str = "traditional_seal",
) -> dict[str, Any]:
    """Ontology block embedded in forge packets."""
    methods: list[dict[str, Any]] = []

    spare_meta = SPARE_MODES.get(spare_mode, SPARE_MODES["letter_monogram"])
    methods.append(
        method_record(
            family=FAMILY_INTENT_COMPRESSION,
            method_id=f"spare.{spare_mode}",
            construction_type="letter_ligature_monogram"
            if spare_mode == "letter_monogram"
            else spare_mode,
            determinism=spare_meta["determinism"],
            alphabet="latin",
            numeric_system=None,
            claimed_historical_status="modern_chaos_magic_corpus",
            verification_method="geometry_reproducible"
            if spare_mode == "letter_monogram"
            else "provenance_only_semantic_not_computable",
            source_tradition="Austin Osman Spare / chaos magic",
            historical_period="20th_century+",
            artifact_role="intent_compression",
            geometry="polyline_monogram" if spare_mode == "letter_monogram" else None,
            source_refs=["The Book of Pleasure (self-love) — method family"],
            extra={"spare_family_modes": list(SPARE_MODES.keys()), "mode_status": spare_meta["status"]},
        )
    )

    methods.append(
        method_record(
            family=FAMILY_NAME_PATH,
            method_id="kamea.name_path",
            construction_type="magic_square_path",
            determinism="deterministic",
            alphabet="hebrew_or_latin_per_encoding",
            numeric_system=kamea_encoding,
            claimed_historical_status=(
                "historically_aligned"
                if kamea_encoding == "hebrew_gematria"
                else "modern_or_compatibility"
            ),
            verification_method="path_cells_match_reduced_sequence",
            source_tradition="Agrippa planetary tables / Western ceremonial",
            historical_period="renaissance+",
            artifact_role="name_or_intent_path",
            geometry="kamea_polyline",
            source_refs=["Agrippa Three Books of Occult Philosophy, Book II"],
        )
    )

    if include_rose:
        methods.append(
            method_record(
                family=FAMILY_NAME_PATH,
                method_id="rose_cross.hebrew_petal_path",
                construction_type="rose_petal_trace",
                determinism="deterministic",
                alphabet="hebrew",
                numeric_system=None,
                claimed_historical_status="historically_aligned_gd_style",
                verification_method="petal_sequence_reproducible",
                source_tradition="Golden Dawn Rose Cross",
                historical_period="19th_century+",
                artifact_role="name_path",
                geometry="22_petal_rose",
                source_refs=["Golden Dawn Rose Cross Lamen letter arrangement"],
            )
        )

    if include_bind:
        methods.append(
            method_record(
                family=FAMILY_ALPHABETIC_LIGATURE,
                method_id="bind_rune.elder_futhark_modern",
                construction_type="runic_ligature_bind",
                determinism="deterministic",
                alphabet="elder_futhark",
                numeric_system=None,
                claimed_historical_status="modern_derivation",
                verification_method="geometry_reproducible",
                source_tradition="runic ligature (historical writing) + modern magical use",
                historical_period="historical_ligature; intent_system_modern",
                artifact_role="alphabetic_ligature",
                geometry="stick_bind",
                source_refs=["Historical bind-runes as writing ligatures; modern magical bind construction"],
                extra={
                    "historical_basis": "runic_ligature",
                    "intent_sigil_system": {"status": "modern_derivation"},
                },
            )
        )

    if include_planetary_seal and planet:
        kind = (planetary_seal_kind or "traditional_seal").strip().lower()
        if kind == "intelligence_character":
            mid = f"planetary.intelligence_character.{planet}"
            ctype = "agrippan_intelligence_character"
            hist = "corpus_name_path_agrippan"
            refs = [
                "Agrippa Book II planetary intelligences",
                "references/planetary-character-corpus.json",
            ]
        elif kind == "spirit_character":
            mid = f"planetary.spirit_character.{planet}"
            ctype = "agrippan_spirit_character"
            hist = "corpus_name_path_agrippan"
            refs = [
                "Agrippa Book II planetary spirits",
                "references/planetary-character-corpus.json",
            ]
        else:
            mid = f"planetary.traditional_seal.{planet}"
            ctype = "agrippan_planetary_seal"
            hist = "historically_aligned_agrippan_character"
            refs = ["Agrippa Book II planetary seals"]
        methods.append(
            method_record(
                family=FAMILY_PLANETARY_CHARACTER,
                method_id=mid,
                construction_type=ctype,
                determinism="deterministic",
                alphabet="hebrew" if kind != "traditional_seal" else None,
                numeric_system="hebrew_gematria" if kind != "traditional_seal" else None,
                claimed_historical_status=hist,
                verification_method="seal_geometry_reproducible",
                source_tradition="Agrippa planetary seals/characters",
                historical_period="renaissance+",
                artifact_role="planetary_character",
                geometry="seal_polyline_set",
                source_refs=refs,
                extra={"planetary_seal_kind": kind},
            )
        )

    methods.append(
        method_record(
            family=FAMILY_ENCODED_CARRIER,
            method_id="stego.multi_channel",
            construction_type="steganographic_carrier",
            determinism="deterministic",
            alphabet=None,
            numeric_system="sha256",
            claimed_historical_status="modern_engineered",
            verification_method="digest_extract_verify",
            source_tradition="Sigil-Forge",
            artifact_role="encoded_carrier",
            geometry="svg_png_stego",
        )
    )

    return {
        "schema": "sigil-method-ontology/v1",
        "primary_family": FAMILY_INTENT_COMPRESSION,
        "methods": methods,
        "excluded_from_default_forge": sorted(EXCLUDED_DEFAULT_FAMILIES),
        "spare_family": SPARE_MODES,
    }


def assert_not_entity_seal_request(intent: str) -> None:
    """Fail closed if operator language clearly requests excluded entity seals.

    Uses policy_lint.detect_authority_seal_request so construct and wizard share
    one authority-seal classifier (no silent Spare/kamea substitution).
    """
    from policy_lint import detect_authority_seal_request

    hit, fam = detect_authority_seal_request(intent)
    if hit:
        raise ValueError(
            "AUTHORITY_SEAL_EXCLUDED: "
            f"family={fam or 'authority_seal'} is not part of the default forge. "
            "Sigil-Forge builds intent-compression sigils only. "
            "See references/distinction-enochian.md and "
            "references/authority-seal-namespace.md. "
            "Do not silently substitute a Spare/kamea glyph."
        )
