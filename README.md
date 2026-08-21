# Sigil-Forge

<p align="center">
  <img src="docs/assets/sigil-forge-hero.png" alt="Sigil-Forge — multi-channel intent sigils" width="100%" />
</p>

<p align="center">
  <strong>v0.13.0</strong> · Hermes skill · offline-first · wallpaper product · MIT
</p>

<p align="center">
  <a href="https://scrimshawlife-ctrl.github.io/Sigil-Forge/"><strong>Project site →</strong></a>
  ·
  <a href="https://scrimshawlife-ctrl.github.io/Sigil-Forge/">scrimshawlife-ctrl.github.io/Sigil-Forge</a>
</p>

**Sigil-Forge** encodes a statement of intent into a **layered sigil image**.  
Corpus methods (Spare, kamea, Rose Cross, bind-runes, planetary plates) forge
**immutable glyph geometry**. The **end product is the wallpaper**: atmosphere +
glyph composite with intent, methods, digests, and Proof-of-Intent surfaces
**encrypted into the PNG** (SF12 LSB vault). Packets and capsules remain operator
workspace — not the handoff object.

Default framing is a **creative / focus tool**. Optional **`practice`** mode
changes tone only. Construction is **offline-first** — no image API required.

> Methods are craft history, symbolic compression, and steganographic layering —
> not proof of metaphysics. Never claims the sigil “works” or replaces professional help.

**Packaging:** Hermes **skill** (`SKILL.md` + CLI → `~/.hermes/skills/sigil-forge`), not a plugin.

---

## Features

| Area | What ships |
|------|------------|
| **Wizard** | Step runner (`--next`), quick/full paths, sessions, PoI `proof`/`kdf` on full path (v2.1) |
| **Craft** | Spare monogram, kamea paths, Hebrew Rose Cross, bind-runes (`modern_derivation`) |
| **Encodings** | `hebrew_gematria` (default), `latin_extended`, `latin_mod9_v1` |
| **Planetary** | Traditional seal + intelligence/spirit; plate → name_on_kamea → reconstruct |
| **Stego** | SVG multi-channel + PNG LSB (digest-only; SF1 + SF11 dual verify) |
| **Product** | **Wallpaper PNG** — composite + SF12 sealed vault (intent + methods in-image) |
| **Wallpapers** | Immutable glyph + atmosphere; procedural / operator / host AI |
| **Ops** | construct, wallpaper, verify, inspect, open (`--wallpaper` / `--capsule`), policy, ledger, doctor, eval, check |
| **Privacy** | Public digests only; private vault needs passphrase; no plaintext in visible media |
| **Proof of Intent** | Commitment + `sigil_root` in vault; SF11/SF12 stego; optional Noir/risc0 |
| **Hermes packaging** | Skill (not plugin); lean install; progressive refs |

**Not included (by design):** Goetic/Enochian authority seals in the default forge (hard refuse via construct/wizard + `policy check`), efficacy claims, auto-canon learning, cloud image APIs inside the skill.

---

## Install

```bash
# Preview
bash install.sh --dry-run

# Default → ~/.hermes/skills/sigil-forge
bash install.sh

# Custom location
bash install.sh --target /path/to/skills/sigil-forge

# Version
bash install.sh --version
```

Post-install runs `validate_hermes_skill` + `check` (with `HERMES_SKILL_DIR` set to the target).  
Install is a **lean skill tree**: excludes `.git`, `out/`, `.venv`, caches, `.worktrees`, and `docs/superpowers` (implementation plans are clone-only).

**Requirements:** Python 3.10+ (stdlib). No pip packages for the core path. Optional: `jsonschema` for stricter packet validation; optional `argon2-cffi` for Argon2id sealing.

From a clone without installing:

```bash
python3 scripts/sigil_forge.py check      # files, modules, Hermes frontmatter, dry PoI construct
python3 scripts/sigil_forge.py doctor     # env + proof providers + packaging: hermes-skill
python3 scripts/validate_hermes_skill.py  # SKILL.md frontmatter hygiene
```

```bash
export HERMES_SKILL_DIR="$HOME/.hermes/skills/sigil-forge"
# Reload Hermes skills if the agent is already running
```

---

## Quick start — wizard (recommended for Hermes)

Hermes has no multi-page UI. The wizard is a **step runner**: one question per turn, then apply.

```bash
# 1) Start a session (quick path: intent → mode → wallpaper)
python3 scripts/sigil_forge.py wizard --session-new --path quick

# 2) Each user answer — ask ONLY next.step, then merge
python3 scripts/sigil_forge.py wizard --next --session <id> \
  --answers-json '{"intent":"I maintain calm focus"}'

# 3) When next.done is true → forge
python3 scripts/sigil_forge.py wizard --apply answers.json \
  --path quick --out out/sigil-forge

# 4) Verify
python3 scripts/sigil_forge.py verify out/sigil-forge/*/glyph.svg
python3 scripts/sigil_forge.py inspect out/sigil-forge/*/glyph.svg
```

| Path | Audience | Steps |
|------|----------|--------|
| **`quick`** | Most users | intent, mode, wallpaper (+ surface/mode/theme if yes) |
| **`full`** | Craft + privacy | + encoding, square, planetary seal/geometry, spare, phonetic, polish, seal_packet, **proof**, **kdf** (when seal/proof needs passphrase) |

Unanswered optional fields use defaults on apply. Bad intents return `refused: true` early (no artifacts).

**Full path + Proof of Intent** (capsule requires env passphrase):

```bash
export SIGIL_FORGE_PASSPHRASE='operator-secret'
# answers JSON includes "proof": "commitment", "kdf": "auto"
python3 scripts/sigil_forge.py wizard --apply answers.json \
  --path full --out out/sigil-forge
# apply result includes intent_capsule, sigil_root, next-hints for open/verify-proof
```

```bash
python3 scripts/sigil_forge.py wizard --script --path quick   # full contract JSON
python3 scripts/sigil_forge.py wizard --list-corpus           # planetary names/numbers
python3 scripts/sigil_forge.py wizard --interactive --path quick  # human TTY
```

Details: [references/wizard.md](references/wizard.md) · agent contract: [SKILL.md](SKILL.md)

---

## Product path — wallpaper as deliverable

```bash
export SIGIL_FORGE_PASSPHRASE='operator-secret'

# One-shot: forge corpus geometry → wallpaper with sealed vault
python3 scripts/sigil_forge.py construct \
  --intent "I maintain calm focus" \
  --wallpaper --surface phone_lock --wp-mode focus \
  --embed vault \
  --out out/sigil-forge

# Handoff object = wallpaper PNG (not the packet)
python3 scripts/sigil_forge.py open --wallpaper \
  out/sigil-forge/*/wallpaper/phone-lock.png --json
```

Without a passphrase, wallpaper still composites and may embed public digests
(`sf11`); the **encrypted vault** requires a passphrase.

---

## Expert construct (workspace)

```bash
python3 scripts/sigil_forge.py construct \
  --intent "I maintain calm focus" \
  --mode creative \
  --kamea-encoding hebrew_gematria \
  --out out/sigil-forge

python3 scripts/sigil_forge.py verify out/sigil-forge/*/glyph.svg
python3 scripts/sigil_forge.py wallpaper --run out/sigil-forge/<run-id> \
  --surface phone_lock --embed vault
```

### Useful flags

```bash
# Kamea encoding + square
--kamea-encoding hebrew_gematria|latin_extended|latin_mod9_v1
--square saturn|jupiter|mars|sol|venus|mercury|luna   # or omit for auto

# Planetary character (opt-in; ≠ intent kamea path)
--planetary-seal
--planetary-seal-kind traditional_seal|intelligence_character|spirit_character
--planetary-geometry auto|plate|name_on_kamea|reconstruction

# Spare family
--spare-mode letter_monogram|pictorial|automatic_drawing|mantric_alphabet|phonetic_mantric
--phonetic

# Privacy + Proof of Intent (prefer env over --passphrase — argv is visible in ps)
export SIGIL_FORGE_PASSPHRASE='operator-secret'
--seal-packet
--kdf auto|argon2id|pbkdf2-sha256   # auto → Argon2id if installed, else PBKDF2
--proof none|commitment|zk-knowledge|zk-forge

# Polish prompt package only (no image API)
--polish --polish-style "ink on parchment"

# One-shot wallpaper after construct
--wallpaper --surface phone_lock --wp-mode focus --theme mercurial

# Thin interop fields
--interop
```

| `--proof` | Needs passphrase | Behavior |
|-----------|------------------|----------|
| `none` | No | Still emits commitment + `sigil_root` (no capsule) |
| `commitment` | Yes | Intent capsule + local knowledge attestation |
| `zk-knowledge` | Yes | Local attestation + optional Noir (skips if no `nargo`) |
| `zk-forge` | No | Optional risc0/zkVM path (skips if guest unavailable) |

Open sealed product / workspace:

```bash
export SIGIL_FORGE_PASSPHRASE='operator-secret'
# Product carrier (preferred)
python3 scripts/sigil_forge.py open --wallpaper out/sigil-forge/*/wallpaper/phone-lock.png --json
# Workspace packet / capsule
python3 scripts/sigil_forge.py open out/sigil-forge/*/forge-packet.json
python3 scripts/sigil_forge.py open --capsule out/sigil-forge/*/intent-capsule.json --json
```

Artifacts land under `out/sigil-forge/<run-id>/`. Run ids use timestamp + digest prefix so paths avoid full intent text.

---

## Proof of Intent

Public artifacts can bind to a privacy-preserving **intent commitment** without putting plaintext intent (or the commitment nonce) in public media. Geometry still uses `intent_digest = SHA-256(normalized intent)` for deterministic craft.

| Surface | Role |
|---------|------|
| `intent_digest` | Forge geometry + legacy SF1 stego |
| `intent_commitment` | Salted per-run commitment (value public; **nonce private**) |
| `intent_commitment_zk` | Fixed-width companion for optional circuits |
| `sigil_root` | Merkle root over public leaves (no self-reference) |
| `forge-manifest.json` | Public config/outputs hashed into root |
| `intent-capsule.json` | Sealed witness (intent + nonce) behind passphrase |
| SF11 stego | Digest + root carrier; dual-verify with SF1 |
| `inspect` / `verify-proof` | Public inspection / proof status (no default plaintext dump) |

Proofs are **provenance only** — never efficacy. Missing Noir/risc0 → status `skipped`, forge still succeeds.

Progressive agent ref: [references/proof-of-intent.md](references/proof-of-intent.md)

---

## Planetary characters

Opt-in geometry **separate** from the intent kamea path.

| Kind | Default geometry (`auto`) |
|------|---------------------------|
| `traditional_seal` | Successive 1→n² path + kamea frame + ticks (plate) |
| `intelligence_character` | Multi-stroke plate digitization (e.g. Iophiel) |
| `spirit_character` | Multi-stroke plate digitization (e.g. Hismael) |

Preference order: **plate → name_on_kamea → reconstruction**.

```bash
python3 scripts/sigil_forge.py construct \
  --intent "I maintain calm focus" \
  --square jupiter \
  --planetary-seal \
  --planetary-seal-kind intelligence_character \
  --planetary-geometry plate \
  --out out/sigil-forge
```

- Names/numbers: [references/planetary-character-corpus.json](references/planetary-character-corpus.json)  
- Plate strokes: [references/planetary-plate-strokes.json](references/planetary-plate-strokes.json)  
- Notes: [references/methods-planetary-characters.md](references/methods-planetary-characters.md)  

Plate geometry is a **scholarly vectorization** of Western ceremonial plate vocabulary — not a unique manuscript scan, and not Goetic/Enochian authority seals.

---

## Wallpapers

Canonical `glyph.svg` is **immutable**. Atmosphere is procedural (offline), operator-supplied, or host AI; then composited deterministically. Wallpaper receipts may bind `intent_commitment` / `sigil_root` when present.

```bash
# From an existing run
python3 scripts/sigil_forge.py wallpaper \
  --run out/sigil-forge/<run-id> \
  --surface phone_lock \
  --mode focus \
  --theme mercurial \
  --style "dark architectural minimalism"

# Multi-surface defaults
python3 scripts/sigil_forge.py wallpaper --run out/sigil-forge/<run-id>

# Host AI background (pre-rendered file)
python3 scripts/sigil_forge.py wallpaper \
  --run out/sigil-forge/<run-id> \
  --surface phone_lock \
  --background-method ai_generated \
  --background /path/to/ai-bg.png \
  --provider host_file

# Or shell host (placeholders: prompt_path out_path width height seed surface)
export SIGIL_FORGE_BG_COMMAND='my-gen --prompt {prompt_path} --out {out_path} ...'
python3 scripts/sigil_forge.py wallpaper --run ... --background-method ai_generated --require-ai
```

| Axis | Values |
|------|--------|
| surface | phone_lock, phone_home, tablet, desktop, desktop_ultrawide |
| mode | stealth, ambient, focus, ritual, immersive |
| intensity | subtle, balanced, strong |
| background | procedural, operator_supplied, ai_generated |

Outputs: `wallpaper/`, `receipts/wallpaper-receipt-*.json`, prompt packages with canvas/seed/contract.

See [references/wallpaper-framework.md](references/wallpaper-framework.md) · [references/wallpaper-prompt-contract.md](references/wallpaper-prompt-contract.md)

---

## What you get

| Output | Role |
|--------|------|
| `glyph.svg` / `glyph.png` | Master geometry; offline PNG + LSB (SF1 / SF11) |
| `forge-packet.json` (+ `.md`) | Channels, methods, ontology, digests, commitment, `sigil_root` |
| `forge-manifest.json` | Public forge config/outputs (hashed into root; no self-root) |
| `artifact-root.json` | Merkle leaves + `sigil_root` |
| `intent-capsule.json` | Sealed witness when passphrase + proof/seal path |
| `run-receipt.json` | Run integrity receipt |
| `proofs/` | Optional proof-manifest + local/Noir/risc0 outputs |
| Stego carriers | SVG metadata / path / metric channels + PNG LSB |
| `polish_prompt.json` | Geometry-locked host polish package (optional) |
| `wallpaper/` | Device composites + background prompts |
| `receipts/` | Wallpaper receipts |
| Learning ledger | PROPOSED only via `learn` / `ledger` (never auto-canon) |

Public media must not contain plaintext intent by default. Packet may seal intent with a passphrase.

Channels: [references/channels-and-steganography.md](references/channels-and-steganography.md)

---

## CLI overview

```text
construct     Forge multi-channel sigil + packet (+ optional --proof)
verify        Recover intent digest (+ sigil_root when SF11)
inspect       Public carrier inspection (digest/root; no plaintext)
verify-proof  Proof-of-intent check for a run (optional passphrase)
wizard        Guided interview (--next / --apply / sessions / --path quick|full)
wallpaper     Immutable glyph + atmosphere composite
open          Decrypt sealed_intent; --capsule for intent-capsule.json
policy check  Efficacy + authority-seal request preflight lint
learn         Append PROPOSED ledger observation
ledger        List / export / promote (human --i-confirm PROMOTE only)
doctor        Environment / skill health (packaging: hermes-skill)
eval          Offline behavioral + PoI + Hermes packaging evals
check         Smoke-check tree, schemas, Hermes, dry construct/PoI
help          Command overview
```

```bash
python3 scripts/sigil_forge.py help
python3 scripts/sigil_forge.py doctor
python3 scripts/sigil_forge.py eval
```

Env: `HERMES_SKILL_DIR`, `SIGIL_FORGE_PASSPHRASE`, optional `SIGIL_FORGE_BG_COMMAND`.

---

## Safety & framing

- Refuse harm, self-harm, non-consensual control before any encode  
- Dual mode: `creative` (default) / `practice` (tone only)  
- No efficacy language; methods ≠ metaphysics — shared lint on framing/polish  
- Enochian / Goetic / authority seals **hard-excluded** from default `construct` / wizard  
  (no silent Spare substitute; see namespace doc)  
- Learning ledger stays **PROPOSED**; human-only `ledger promote --i-confirm PROMOTE`  
  writes local proposals — never mutates `references/`  
- PoI: never put commitment **nonce** in public media; never claim ZK without generate + verify  

```bash
# Preflight: efficacy phrases + authority-seal request language
python3 scripts/sigil_forge.py policy check --text "I maintain calm focus"
python3 scripts/sigil_forge.py policy check --file path/to/text.txt

# Human-gated canon proposal (operator confirm string required)
python3 scripts/sigil_forge.py ledger promote --index 0 --i-confirm PROMOTE
```

See [references/safety-and-framing.md](references/safety-and-framing.md) ·
[references/distinction-enochian.md](references/distinction-enochian.md) ·
[references/authority-seal-namespace.md](references/authority-seal-namespace.md) ·
[references/receipts-and-ledger.md](references/receipts-and-ledger.md)

---

## Development

```bash
# Tests (pytest; project may use .venv)
python3 -m pytest -q

# Hermes skill hygiene
python3 scripts/validate_hermes_skill.py

# Smoke (includes hermes_ok + poi_ok)
python3 scripts/sigil_forge.py check
python3 scripts/sigil_forge.py eval
```

Version: [`VERSION`](VERSION) · roadmap: [references/expansion-spine.md](references/expansion-spine.md)

---

## Documentation

| Doc | Topic |
|-----|--------|
| [QUICKSTART.md](QUICKSTART.md) | Short command sequence |
| [SKILL.md](SKILL.md) | Hermes behavior contract |
| [references/wizard.md](references/wizard.md) | Step runner, paths, sessions, PoI steps |
| [references/proof-of-intent.md](references/proof-of-intent.md) | Commitments, capsule, proofs (load on demand) |
| [references/hermes-runtime-contract.md](references/hermes-runtime-contract.md) | Agent vs engine; skill packaging |
| [references/wallpaper-framework.md](references/wallpaper-framework.md) | Wallpaper pipeline |
| [references/methods-planetary-characters.md](references/methods-planetary-characters.md) | Seals / intelligence / spirit |
| [references/methods-spare.md](references/methods-spare.md) · [methods-kamea.md](references/methods-kamea.md) | Craft methods |
| [references/channels-and-steganography.md](references/channels-and-steganography.md) | Channel IDs / privacy |
| [references/expansion-spine.md](references/expansion-spine.md) | Shipped vs remaining |
| [references/authority-seal-namespace.md](references/authority-seal-namespace.md) | Authority-seal boundary (no geometry) |
| [references/safety-and-framing.md](references/safety-and-framing.md) | Refusals, efficacy lint, policy check |
| [docs/superpowers/specs/2026-08-07-sigil-forge-design.md](docs/superpowers/specs/2026-08-07-sigil-forge-design.md) | Product design *(clone only; not in Hermes install)* |

Social / OG crop (for GitHub Settings → Social preview):  
[`docs/assets/sigil-forge-social.jpg`](docs/assets/sigil-forge-social.jpg) (1280×640)

### GitHub Pages

Landing site lives under [`docs/`](docs/) (Hallmark atmospheric marquee):

| File | Role |
|------|------|
| [`docs/index.html`](docs/index.html) | Landing page |
| [`docs/tokens.css`](docs/tokens.css) · [`docs/site.css`](docs/site.css) | Design tokens + layout |
| [`docs/assets/`](docs/assets/) | Hero + social images |

Enable in the repo: **Settings → Pages → Deploy from branch → `/docs`**.  
Local preview: open `docs/index.html` or serve `docs/` with any static server.

---

## License

This repository now uses the MIT License for original Zero State materials going forward. See [LICENSE](LICENSE). Earlier grants in repository history are not rewritten.

Third-party components remain subject to their respective licenses.
