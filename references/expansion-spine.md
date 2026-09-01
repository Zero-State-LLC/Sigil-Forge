# Expansion spine

**Current release: v0.13.1** (this file tracks shipped vs remaining).

Sigil-Forge is a standalone Hermes skill with a lean install tree, additive
channels, and an explicit method ontology so “sigil” never collapses intent
compression, name paths, planetary characters, and entity seals.

## Shipped

| Version | Highlights |
|---------|------------|
| v0.1–0.2 | Construct/verify/check, Spare monogram, kamea, stego, offline PNG, polish prompt, open |
| v0.3 | `bind_runes`, `rose_cross_path`, run receipts, learning ledger |
| v0.4 | Kamea multi-encoding + provenance, ontology, Spare family, Hebrew Rose Cross, planetary traditional seals |
| v0.5 | Transliteration upgrade, kamea goldens, intelligence/spirit reconstructions, phonetic channel, doctor/eval, optional Argon2id, interop fields, source manifest |
| v0.6 | Wallpaper framework: immutable glyph + atmosphere composite, device profiles, wallpaper-spec/receipt, CLI `wallpaper` |
| v0.7 | Host AI background provider (file + shell command), enriched prompt packages, `construct --wallpaper` one-shot |
| v0.8 | Planetary character corpus (name_on_kamea intel/spirit) + Hermes `wizard` guided interview |
| v0.9 | Stroke-faithful plate digitizations (multi-stroke); geometry auto plate→name→reconstruct |
| v0.10 | Wizard step runner (`--next`), quick/full paths, sessions, per-step help |
| v0.11 | Policy track: authority-seal exclusion, efficacy lint, human-gated canon proposals |
| v0.12.0 | Proof of Intent: salted commitment, capsule, Argon2 auto, Merkle sigil_root, forge-manifest |
| v0.12.1 | SF11 stego (digest+root), dual verify, wallpaper root binding, `inspect` CLI |
| v0.12.2 | ProofProvider, zk companion commit, local knowledge attestation, Noir circuit (optional), `verify-proof` |
| v0.12.3 | `forge_core` pure boundary, dual-commit bind tests, `open --capsule`, risc0/zkVM skip-path adapter |
| v0.12.4 | Hermes skill packaging: install/check/doctor gates, lean install, progressive PoI ref |
| v0.12.5 | Hermes runtime polish: check/eval no skill-out pollution, PoI+hermes eval cases, lean help refs |
| v0.12.6 | Wizard PoI steps (proof/kdf), apply capsule surfaces, Hermes agent next-hints |
| v0.13.0 | **Wallpaper product:** SF12 sealed vault (intent+methods in PNG); open --wallpaper |
| v0.13.1 | Hermes Agent v0.21 skill index: ≤60-char description, `[[as_document]]` wallpaper delivery |

### Craft / methods
- Encodings: `hebrew_gematria` (default; native Hebrew + latin translit), `latin_extended`, `latin_mod9_v1` (compat)
- Rose Cross: 22 Hebrew petals + markers
- Planetary geometry: **plate** (multi-stroke) → name_on_kamea → reconstruction (`--planetary-geometry`)
- Plate corpus: `references/planetary-plate-strokes.json`
- Name corpus: `references/planetary-character-corpus.json`
- Bind-runes: **modern_derivation**
- Spare family modes + phonetic JSON carrier
- Ontology + `references/source-manifest.yaml`
- Hermes **wizard** v2.1: `--next` step runner, `--path quick|full`, sessions, `--apply`; full path `proof`/`kdf` (see `references/wizard.md`)
- Pure **forge_core** compute boundary (`scripts/forge_core.py`); construct is I/O shell

### Proof of Intent (v0.12+)
- Salted `intent_commitment` + Merkle `sigil_root` + `forge-manifest` on every run
- Optional `intent-capsule.json` (passphrase); SF11 stego; `inspect` / `verify-proof`
- Proof modes: `none` | `commitment` | `zk-knowledge` | `zk-forge` (Noir/risc0 skip if unavailable)
- Agent ref: `references/proof-of-intent.md`

### Wallpapers (v0.6–0.7)
- Surfaces: `phone_lock`, `phone_home`, `tablet`, `desktop`, `desktop_ultrawide`
- Modes: stealth / ambient / focus / ritual / immersive
- Canonical glyph immutable; background = procedural (offline), operator PNG, or host AI
- Host AI: `--background` (host_file), `--provider-command` / `SIGIL_FORGE_BG_COMMAND` (host_command)
- Enriched `background-prompt-*.json` (canvas, seed, output_hint, contract)
- Spec + receipt under `wallpaper/` and `receipts/`; optional LSB digest binding
- One-shot: `construct --wallpaper` (presentation via `--wp-mode`)

### Ops
- CLI: construct, verify, verify-proof, inspect, wallpaper, wizard, open (`--capsule`), learn, ledger, doctor, eval, check
- Receipts + PROPOSED ledger
- Hermes skill install: lean tree (excludes `docs/superpowers`), post-install `validate_hermes_skill` + `check`
- Progressive refs: `hermes-runtime-contract.md`, `proof-of-intent.md`
- `validate_hermes_skill.py`

### Policy machinery (shipped)

Product policy track (code + docs; release version/tag owned separately):

- **Efficacy lint** — `scripts/policy_lint.py` (`lint_efficacy_text`, `assert_no_efficacy`) on framing notes and polish prompts
- **Policy check CLI** — `python3 scripts/sigil_forge.py policy check --text|…|--file …` (exit 0 clean / 1 hits)
- **Authority-seal request exclusion** — construct + wizard fail closed on Goetic/Enochian/authority language; no silent Spare substitute (`AUTHORITY_SEAL_EXCLUDED`)
- **Human-gated canon proposals** — learning ledger stays `PROPOSED`; `ledger promote --index N --i-confirm PROMOTE` → `canon-proposals.jsonl` only; **no** auto-canon, **no** `references/` mutation
- Namespace doc: `references/authority-seal-namespace.md`

## Remaining / optional later
- Scanned unique MS plate import pipeline (external SVG/JSON; plate v1 is scholarly vectorization)
- Audio/MIDI for mantric carriers
- Multi-frame storyboard carriers
- Rich Orchestra/Kubrick/ComfyUI adapters beyond thin interop fields
- Deeper geometric multi-channel steganalysis
- Optional bundled ComfyUI workflow templates (skill still does not call cloud image APIs)
- Full Goetic/Enochian geometry (separate skill or opt-in namespace module + corpus — not default forge)

## Explicit non-goals
- Goetic / Enochian / authority seals in the **default** forge
- Deterministic freehand automatic drawing claimed as pure geometry
- Auto-promoting learning ledger to canon
- Soft-building a “safe fake” authority seal when refused

## Compatibility rules
1. Do not break forge-packet required keys without `schema_version` bump.  
2. New channels append; unknown IDs report applied/skipped honestly.  
3. Offline path works without optional pip packages.  
4. Never mutate `references/` at run time.
