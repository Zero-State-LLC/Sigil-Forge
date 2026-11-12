# Authority-seal namespace (not default forge)

This document defines the **product boundary** between Sigil-Forge’s default
intent-compression forge and **authority-seal** artifact families (Goetic,
Enochian, and related spirit-authority / placement seals). It does **not**
implement geometry, stroke corpora, or ritual construction for those families.

## Default forge = intent compression only

Sigil-Forge’s shipped `construct` and `wizard` paths produce **intent sigils**:

- A statement of desire or focus, normalized and multi-encoded
- Spare monogram (+ optional kamea path, Rose Cross, bind-runes, planetary
  character geometry when opted in)
- Forge packet, digests, stego carriers, optional wallpapers

That is **intent compression and craft encoding**. It is not name-of-spirit
authority work, watchtower / tablet placement, or Goetic seal construction.

Ontology families on a successful default packet are limited to intent
compression, name paths, planetary characters (opt-in Agrippan plate/name
geometry), alphabetic ligatures, and encoded carriers. Families such as
`entity_identifier`, `enochian_seal`, `goetic_seal`, and `authority_seal` are
listed under `excluded_from_default_forge` and are never applied as construct
channels.

## Different artifact families

| Family (examples) | Job | Default Sigil-Forge |
|-------------------|-----|---------------------|
| Intent sigil (Spare / kamea fusion) | Compress a present-tense intent | **Yes** — core product |
| Planetary characters (Agrippa plates / names) | Traditional planetary seal geometry | Opt-in craft channel only; not Goetic/Enochian |
| Goetic / Solomonic spirit seals | Entity identifiers, hierarchical spirit work | **Excluded** |
| Enochian seals / watchtowers | Tablet authority, placement, letter systems | **Excluded** |
| Generic “authority seal” / binding spirit seal | Spirit-authority tokens | **Excluded** |

These are **not interchangeable**. A Spare monogram is not an Enochian seal. A
kamea path is not a Goetic spirit seal. Planetary plate strokes in this skill
are scholarly vectorizations of Western ceremonial **planetary** vocabulary —
not manuscript Goetia seals and not Enochian tables.

See also: `distinction-enochian.md` (intent vs Enochian **and** Goetic tables).

## This skill refuses emission via construct / wizard

Hard gate (shared classifier in `src/sigil_forge/policy_lint.py`):

- `detect_authority_seal_request(text)` → `(hit, family_hint)`
- `ontology.assert_not_entity_seal_request(intent)` raises
  `AUTHORITY_SEAL_EXCLUDED` when hit
- `construct` fails closed **before** normalize / encode (no partial run dir)
- `wizard` refuses with `refused: true`, phase `authority_policy`, and agent
  instruction to explain the distinction and offer a present-tense **intent**
  rewrite — never a silent Spare/kamea substitute labeled as authority

Detected language families include (non-exhaustive patterns): `enochian`,
`watchtower`, `goetic` / `goetia` / `ars goetia`, `solomonic … seal`,
`authority seal`, `spirit seal of binding`. Prefer multi-word anchors to limit
false positives; the agent still applies judgment for edge cases the gate
misses.

**Rule for agents:** if the operator asks for an Enochian, Goetic, or authority
seal, **refuse**. Do not rename a monogram. Point here and to
`distinction-enochian.md`. Offer to forge an **intent** sigil if that is what
they actually want.

Lint CI / agents without constructing:

```bash
python3 scripts/sigil_forge.py policy check --text "please forge an Enochian seal"
python3 scripts/sigil_forge.py policy check --file path/to/intent.txt
```

Exit `0` only when both efficacy lint and authority-seal detection are clean.
JSON reports `authority_seal_request`, `authority_family`, and `efficacy_hits`.

## Future option A — separate Hermes skill

A full authority-seal product (corpus-backed Goetic/Enochian geometry, tablet
logic, hierarchical naming) should live as a **separate Hermes skill** with its
own `SKILL.md`, corpora under its own `references/`, safety framing, and
operator consent model. Sigil-Forge remains the intent-compression skill.
Cross-skill discovery can be documented; doctrines must not merge in one
construct pipeline.

## Future option B — opt-in module (namespace only here)

An optional in-repo module might later require **both**:

1. Environment gate: `SIGIL_FORGE_ALLOW_AUTHORITY_NAMESPACE=1`
2. Explicit CLI surface that is **not** default `construct` / wizard

Even then, the module must **not invent manuscript seals** without a verified
corpus and construction method. Geometry, stroke import, and ritual completeness
are **out of scope** for this policy track. This file is the namespace and
refusal contract only — not a promise of implementation.

## Interop: `intent_token` only; no doctrine merge

Thin interop export (`construct --interop` and related packet fields) may carry
identifiers such as `intent_token` / glyph handles so other tools can **name** a
related intent artifact. Interop must not:

- Merge Enochian or Goetic doctrine into the forge packet ontology as applied
  methods
- Claim the glyph is an authority seal
- Smuggle entity-seal geometry through stego or wallpaper layers

Packet notes already frame interop as thin export — not Enochian/Goetic
authority seals.

## Agent rule: never rebrand

**Never** emit a Spare monogram (or any default-forge glyph) and call it:

- Enochian
- Goetic / Goetia / Ars Goetia
- Solomonic spirit seal
- Watchtower / tablet seal
- Authority seal / spirit seal of binding

That collapse is a product defect and a cultural/safety failure. Refuse or
redirect; do not soft-build a “safe fake.”

## Related machinery (shipped)

| Concern | Mechanism |
|---------|-----------|
| Authority request gate | `policy_lint.detect_authority_seal_request` + construct/wizard |
| Efficacy language | `lint_efficacy_text` / `assert_no_efficacy` on framing & polish |
| Agent / CI lint | `python3 scripts/sigil_forge.py policy check` |
| Learning | Ledger stays `PROPOSED`; `ledger promote --i-confirm PROMOTE` → local proposals only |
| Safety harm gate | `src/sigil_forge/safety.py` (violence, self-harm, non-consensual control, exploitation) |

Details: `safety-and-framing.md`, `receipts-and-ledger.md`, `expansion-spine.md`.

## Related

- Distinction tables: `distinction-enochian.md`
- Ontology families: `sigil-ontology.md`
- Safety / framing: `safety-and-framing.md`
- Skill contract: `../SKILL.md`
