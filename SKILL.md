---
name: sigil-forge
description: Forge offline intent glyphs into encrypted wallpapers.
version: 0.13.1
author: Daniel Meyer (scrimshawlife-ctrl), Hermes Agent
license: LicenseRef-Zero-State-Proprietary-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags:
      - Creative
      - Sigil
      - Intent
      - Steganography
      - SymbolicDesign
    category: creative
    related_skills: []
---

# Sigil-Forge Skill

Standalone Hermes skill (not a plugin). Hermes loads this directory;
`SKILL.md` is the behavior contract. Deterministic construction lives under
`scripts/`; the agent owns intake, mode framing, and presentation.

**Product:** the **wallpaper PNG** is the deliverable. Corpus methods forge
immutable glyph geometry; intent and method provenance are **encrypted into
the image** (SF12 vault). Packets are workspace. Install:
`bash install.sh` → `${HERMES_HOME:-$HOME/.hermes}/skills/sigil-forge`.

Default framing is a creative / focus tool. Optional `practice` mode changes
tone only. Methods are craft and encoding — never proof of metaphysics. Never
claim the sigil works, causes events, or replaces professional help.

## When to Use

- User wants a **sigil**, **intent glyph**, **forge packet**, or wallpaper from
  a statement of intent
- User mentions Spare, kamea / magic squares, or steganography of intent
- User wants offline, verifiable construction (no image API required)
- User asks to be guided (`wizard`, “guide me”, “walk me through”)

### Don't use for

- General image gen, cinema, or Kubrick-style production
- **Enochian / Goetic / authority seals** — hard-excluded from default
  `construct` / wizard (see `references/distinction-enochian.md`,
  `references/authority-seal-namespace.md`). Never rebrand a Spare monogram
  as one.
- Full ritual liturgy, banishing systems, or results-magic engines
- Harmful intents — refuse before any encode
- Efficacy claims (“works,” “manifests,” “guarantees results”) — refuse or
  rewrite; lint with `policy check`

## Prerequisites

- Python 3.10+ stdlib. No required pip packages. Optional: `jsonschema`,
  external SVG raster, `argon2-cffi`
- Honor `HERMES_SKILL_DIR` when set; write under `--out` or
  the active profile’s `state/sigil-forge/products/<run-id>/` (see state overrides below).
- Optional `SIGIL_FORGE_PASSPHRASE` for sealed vault / packet (prefer env
  over `--passphrase`; argv is visible in process lists)
- Optional `SIGIL_FORGE_BG_COMMAND` host-AI background template
  (`{prompt_path} {out_path} {width} {height} {seed}`) — not a secret
- **Never mutate `references/` during ordinary runs**

## How to Run

Invoke the CLI through the Hermes `terminal` tool. `${HERMES_SKILL_DIR}` is
substituted with the absolute skill directory.

Prefer the wizard for new users:

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py wizard --session-new --path quick", timeout=60)
```

Each later turn, ask only the current step, then:

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py wizard --next --session <id> --answers-json '{\"intent\":\"I maintain calm focus\"}'", timeout=60)
```

When `next.done` is true:

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py wizard --session <id> --path quick --out out/sigil-forge", timeout=120)
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py verify out/sigil-forge/<run-id>/glyph.svg", timeout=60)
```

Expert path (skip wizard only when the operator already has construct args):

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py construct --intent \"I maintain calm focus\" --mode creative --wallpaper --surface phone_lock --out out/sigil-forge", timeout=120)
```

**Delivering the product:** when you produce a wallpaper, PNG, or SVG the
user should see, put the absolute path in the response and emit the literal
directive `[[as_document]]` (commonly the last line). The gateway strips it
and attaches the file instead of a crushed preview. Example:

```text
Wallpaper: /abs/path/to/wallpaper/phone-lock.png
[[as_document]]
```

Load [references/wizard.md](references/wizard.md) only while guiding; load
[references/proof-of-intent.md](references/proof-of-intent.md) only for PoI.

## Quick Reference

```
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py help
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py doctor
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py check
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py construct --intent "…" --out out/sigil-forge
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py construct --intent "…" --wallpaper --surface phone_lock --out out/sigil-forge
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py wizard --session-new --path quick
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py wizard --next --session <id> --answers-json '{…}'
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py wizard --session <id> --path quick --out out/sigil-forge
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py verify out/sigil-forge/<run-id>/glyph.svg
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py wallpaper --run out/sigil-forge/<run-id> --surface phone_lock --mode focus
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py open --wallpaper out/sigil-forge/<run-id>/wallpaper/phone-lock.png --json
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py inspect out/sigil-forge/<run-id>/glyph.svg
python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py policy check --text "I maintain calm focus"
python3 ${HERMES_SKILL_DIR}/scripts/validate_hermes_skill.py
```

Optional construct flags: `--kamea-encoding hebrew_gematria|latin_mod9_v1|latin_extended`,
`--spare-mode letter_monogram|pictorial|…`, `--planetary-seal`, `--seal-packet`,
`--polish`, `--square venus`, `--phonetic`. Wallpaper AI atmosphere (never
redraw the glyph): `--background-method ai_generated --background /path/ai-bg.png`.
Full path wizard adds `proof` / `kdf` (capsule needs `SIGIL_FORGE_PASSPHRASE`).
Channel IDs and capacity: `references/channels-and-steganography.md`.

## Procedure

Each step ends with a checkable completion criterion.

1. **Intake / wizard** — Prefer `--path quick` and the `--next` step runner
   (one question per turn). Use `step.help` if needed. Expert operators may
   skip to construct.
   **Done when:** `next.done` true or expert construct args complete; safety ok.
2. **Safety / align** — Refuse violence, self-harm, non-consensual control,
   exploitation (`scripts/safety.py` + agent judgment). Refuse authority-seal
   requests (engine raises `AUTHORITY_SEAL_EXCLUDED` / wizard `refused: true`).
   Empty noise → rewrite. Optional preflight:
   `policy check --text "…"`.
   **Done when:** `check_intent` ok **or** clear refusal with no artifacts.
3. **Construct via engine** — Do not hand-draw paths. Run `construct` (or
   wizard `--apply`) through `terminal`.
   **Done when:** run dir contains `glyph.svg`, `forge-packet.json` with
   `ontology` + kamea `encoding_system` provenance, and every channel
   `applied` or `skipped(reason)`.
4. **Dual-mode notes** — Apply profile tone only to narrative /
   `framing_notes`. Construction is identical across modes.
   **Done when:** framing matches mode; no efficacy language.
5. **Deliver wallpaper** — Prefer the wallpaper path as the product handoff.
   Public pixels must not contain plaintext intent; sealed vault needs
   passphrase. After the PNG exists, show the absolute path and emit
   `[[as_document]]`.
   **Done when:** wallpaper exists with vault embedded (or honest public-only
   digests) and `geometry_preserved`; user received the file, not a preview.
6. **Optional polish** — Geometry-locked host image tools only after master
   exists. Prefer construct `--polish` or `prompt_polish.build_prompt`.
   **Done when:** if polish used, `polish_prompt.json` exists and `gen_seed`
   is `applied`.
7. **Verify** — Before claiming integrity, run `verify` on `glyph.svg` and
   on `glyph.png` when `png_lsb` applied.
   **Done when:** `ok: true` and digest matches packet (or honest failure).
8. **Optional extra surfaces** — After master verify (or via
   `construct --wallpaper`): `wallpaper --run <run-id> --surface phone_lock`.
   **Done when:** `wallpaper/` + `receipts/wallpaper-receipt-*.json` exist;
   receipt `geometry_preserved: true`; `glyph.svg` digest unchanged.
9. **Open sealed intent** (if sealed) — `open` on the packet, or
   `open --wallpaper` on the PNG, or `open --capsule` for the capsule.
   **Done when:** plaintext recovered or auth failure reported.
10. **Proof of Intent (optional)** — Load
    [references/proof-of-intent.md](references/proof-of-intent.md) only when
    the operator asks. Geometry still uses `intent_digest`; never put the
    commitment nonce in public media.

## Pitfalls

1. **Inventing geometry** — monogram/kamea points come only from `scripts/`.
2. **Claiming stego success** when `verify` fails or a channel is `skipped`.
3. **Leaking plaintext intent** into public SVG/PNG/wallpapers.
4. **Treating PNG LSB as full ciphertext** — public LSB is digest-only; the
   sealed vault is passphrase-gated.
5. **All-vowel intents** — raise `NOT_COMPUTABLE:`; rewrite with consonants.
6. **`--passphrase` on argv** — prefer `SIGIL_FORGE_PASSPHRASE`.
7. **Collapsing Enochian/Goetic/authority seals** into Spare glyphs (refuse;
   never rebrand).
8. **Mutating `references/`** or auto-promoting ledger lines (human
   `ledger promote --i-confirm PROMOTE` only).
9. **Premature completion** — deliver without verify when integrity was claimed.
10. **AI-redrawing the sigil for wallpaper** — generate atmosphere only;
    composite the master SVG.
11. **Efficacy language** in framing, polish, or delivery — use `policy check`.
12. **Crushed wallpaper preview** — omit `[[as_document]]` and messaging
    platforms recompress the PNG. Always emit it with the file path.

## Verification

- [ ] Safety gate passed (or refusal with no artifacts)
- [ ] Authority-seal request excluded (or clear refusal; no silent substitute)
- [ ] Framing / narrative pass efficacy policy (`policy check` clean or honest hits)
- [ ] `forge-packet.json` has `schema_version`, `mode`, `intent_digest`,
      `channels[]`, `methods`, `artifacts`, `crypto`, `verify`, `framing_notes`
- [ ] Every fixed channel is `applied` or `skipped` with reason
- [ ] `glyph.svg` present; `glyph.png` when `png_lsb` applied
- [ ] `verify` recovers matching digest (SVG and PNG when present)
- [ ] Public media has no default plaintext intent
- [ ] Framing matches mode; **no efficacy claims**
- [ ] If wallpaper: receipts `geometry_preserved: true`; vault honest; glyph
      digest unchanged; response includes absolute path + `[[as_document]]`
- [ ] If AI wallpaper: prompt package present; method/provider honest
- [ ] Learning entries remain `PROPOSED` unless human ran `ledger promote`
- [ ] Packet has `intent_commitment` + `sigil_root` when construct succeeds
- [ ] `python3 ${HERMES_SKILL_DIR}/scripts/sigil_forge.py check` → `ok: true`
- [ ] `python3 ${HERMES_SKILL_DIR}/scripts/validate_hermes_skill.py` → `ok: true`

Method depth lives in `references/` (Spare, kamea, bind-runes, Rose Cross,
wallpaper, wizard, PoI, safety). Do not invent cipher tables.

Source, profile, and migration rules: `references/source-and-upgrades.md`.
