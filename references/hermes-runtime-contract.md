# Hermes runtime contract

Version: **v4** (Sigil-Forge v0.13.1+, Hermes Agent v0.21 / tag v2026.8.31)

Sigil-Forge is a **standalone Hermes skill** (not a Hermes plugin).  
Default install path: `~/.hermes/skills/sigil-forge`. Skill name: `sigil-forge`.

**v0.21 index:** `SKILL.md` frontmatter starts at byte 0. Description is one
sentence, ≤60 characters, ending with a period (Hermes truncates the index at
57 characters + `...`). Invoke the CLI through the Hermes `terminal` tool with
`${HERMES_SKILL_DIR}`. When the agent shows a wallpaper, PNG, or SVG, emit
`[[as_document]]` so the gateway attaches the file instead of a crushed
preview. Do not add a blueprint or cron.

**Skill vs plugin:** A skill teaches when/how to forge via `SKILL.md` + offline
CLI. A plugin would inject always-on tools/hooks — not the product shape here.
Optional thin plugin adapters later must wrap this skill, not replace it.

## Two layers

| Layer | Owns | Does **not** own |
|-------|------|------------------|
| **Agent contract** (`SKILL.md`, `references/`) | Intake, wizard interview, mode, safety judgment, packet narrative, when to invoke scripts / host image tools | Inventing glyph geometry or fake stego success |
| **Construction engine** (`scripts/`) | Normalize, digest, optional encrypt, Spare, kamea, fusion, SVG/PNG, stego, wallpaper composite, verify, PoI surfaces | Mystical guarantees, external image APIs, mutating skill `references/` |

## Skill root resolution

1. `HERMES_SKILL_DIR` if set  
2. Else install/clone directory containing this skill  

Default out: `out/sigil-forge/<run-id>/` or `--out`.  
Wizard sessions: `out/wizard-sessions/<id>.json`.  
`run-id` = timestamp + short digest prefix.

## Artifact rule

- Write under user-chosen directory or skill `out/`.  
- **Never mutate `references/`** during ordinary runs.  
- Prefer hash-based run paths so listings do not leak full intent text.

## CLI surface

| Command | Role |
|---------|------|
| `wizard` | Guided interview: `--script`, `--next`, `--session-new`, `--apply`; full path includes `proof`/`kdf` |
| `construct` | Full forge (expert / non-wizard); optional `--proof` / `--kdf` / `--seal-packet` |
| `verify` | Recover digest / integrity from SVG or PNG |
| `verify-proof` | Check local/Noir/risc0 proof manifests for a run |
| `inspect` | Public PoI/SF11 surfaces without disclosing intent |
| `wallpaper` | Device composites from a forge run |
| `open` | Decrypt sealed packet; `--capsule` for intent-capsule.json |
| `learn` / `ledger` | PROPOSED learning observations; human `ledger promote` only |
| `policy check` | Efficacy + authority-seal request lint (preflight) |
| `doctor` / `eval` / `check` | Health, packaging gates, offline evals |
| `help` | Command overview |

Entry: `python3 scripts/sigil_forge.py …`

## Install / packaging gates

```bash
bash install.sh --dry-run
bash install.sh              # → ~/.hermes/skills/sigil-forge
# post-install sets HERMES_SKILL_DIR for check
python3 scripts/validate_hermes_skill.py
python3 scripts/sigil_forge.py check    # files + modules + hermes + dry construct/PoI
python3 scripts/sigil_forge.py doctor   # env + proof providers + packaging: hermes-skill
```

Install excludes: `.git`, `out/`, `.venv`, caches, `.worktrees`, `docs/superpowers`
(implementation plans are not runtime surface).

## Wizard (Hermes default for new users)

1. Prefer `wizard --path quick` + **`--next` step runner** (one question per turn).  
2. Load `references/wizard.md` only when guiding (progressive disclosure).  
3. On `done`, `wizard --apply` then `verify`.  
4. Expert operators may skip to `construct`.  
5. PoI depth: load `references/proof-of-intent.md` only when commitments/proofs are in play.  
6. Full-path wizard may set `proof` / `kdf`; apply returns capsule paths + next-hints when sealed.

See `references/wizard.md` · `references/proof-of-intent.md`.

## Schemas

Under `schemas/` (validate when `jsonschema` available; structural checks always):

- `forge-packet.schema.json`  
- `channel-manifest.schema.json`  
- `construction-result.schema.json`  
- `wallpaper-spec.schema.json` / `wallpaper-receipt.schema.json`  
- `intent-capsule.schema.json` / `artifact-root.schema.json` / `forge-manifest.schema.json`  
- `proof-manifest.schema.json`  

## Agent obligations

1. Safety before construct; refuse with no artifacts.  
2. Follow wizard step runner when guiding; one question per turn.  
3. Point to `references/` for method depth; do not invent cipher tables.  
4. Report channels honestly (`applied` / `skipped`).  
5. Never claim efficacy or stego success without verify.  
6. Standalone: no hard dependency on Kubrick, Orchestra, or ComfyUI.  
7. Wallpapers: atmosphere only — never AI-redraw canonical glyph.  
8. PoI: never put commitment nonce in public media; never claim ZK without dual pass.  
9. When delivering wallpaper/PNG/SVG the user should see, include the absolute
   path and the literal `[[as_document]]` directive (commonly last line).

## Host tools

- Image polish / wallpaper AI background is **optional** and post-master only.  
- Offline success is first-class: procedural glyph + packet without any image API.  
- Optional Noir/risc0 tooling never required for construct/verify/open.

## Progressive disclosure

Keep agent context lean:

1. Skill index (name/description) at session start  
2. `SKILL.md` when skill triggers  
3. `references/wizard.md` when guiding  
4. `references/proof-of-intent.md` when commitments / capsules / proofs arise  
5. Method refs only when explaining that channel  

## Related

- Expansion: `expansion-spine.md`  
- PoI: `proof-of-intent.md`  
- Safety: `safety-and-framing.md`  
- Design: `docs/superpowers/specs/2026-08-07-sigil-forge-design.md` (clone only; not installed)
