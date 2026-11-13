# Forge wizard (Hermes)

Guided **step-by-step** interview so operators never memorize CLI flags.
The engine owns geometry; the agent owns conversation and safety judgment.

Hermes has no native multi-page UI — the wizard is a **step runner** the agent
loops with `wizard --next`.

## Paths

| Path | Who | Steps |
|------|-----|--------|
| **quick** (recommended for new users) | Casual | intent → mode → wallpaper (+ surface/mode/theme if yes) |
| **full** | Craft options | + encoding, square, planetary seal/geometry, spare, phonetic, polish, seal_packet, **proof**, **kdf** (when seal/proof needs passphrase) |

Unanswered optional steps fill from defaults on apply.

Proof-of-Intent (`proof`): `none` | `commitment` | `zk-knowledge` | `zk-forge`.  
`commitment` / `zk-knowledge` need `SIGIL_FORGE_PASSPHRASE` (capsule).  
Load [proof-of-intent.md](proof-of-intent.md) only when guiding those steps.

## Hermes agent loop (required)

```bash
# 1) Optional: read contract once
python3 scripts/sigil_forge.py wizard --script --path quick

# 2) Create resume session (or track answers JSON yourself)
python3 scripts/sigil_forge.py wizard --session-new --path quick
# → { session_id, next: { step, help, agent_instruction } }

# 3) Each user turn: merge answer → next
python3 scripts/sigil_forge.py wizard --next --session <id> \
  --answers-json '{"intent":"I maintain calm focus"}'

# 4) When next.done == true → apply
python3 scripts/sigil_forge.py wizard --apply answers.json --path quick --out out/sigil-forge

# 5) Verify
python3 scripts/sigil_forge.py verify <run>/glyph.svg
```

Without sessions (stateless):

```bash
python3 scripts/sigil_forge.py wizard --next --path quick
python3 scripts/sigil_forge.py wizard --next --path quick \
  --answers-json '{"intent":"I maintain calm focus"}'
# …accumulate answers…
python3 scripts/sigil_forge.py wizard --apply answers.json --path quick --out out/sigil-forge
```

### Agent rules

1. Ask **only** the current `step` (one question per turn).  
2. Use `step.help` / `step.why` if the user is confused.  
3. Prefer **quick** path unless they ask for craft options.  
4. On `refused: true` (safety), stop — no artifacts.  
5. On `done: true`, apply then offer verify (+ inspect; open capsule / verify-proof if PoI).  
6. Never invent monogram/kamea geometry.  
7. No efficacy claims.  
8. Progressive disclosure: load this file when guiding; don’t dump all method refs on turn 1.  
9. If `proof` is `commitment` or `zk-knowledge`, ensure `SIGIL_FORGE_PASSPHRASE` is set before apply.

## Per-step fields

Each step may include: `id`, `prompt`, `type`, `choices`, `default`, `example`,
`help`, `why`, `skip_ok`, `required`, `when` (conditional).

Conditional examples:

- Wallpaper surface/mode/theme only if `wallpaper: true`  
- `planetary_geometry` only if `planetary_seal != none`  
- `kdf` only if `seal_packet: true` **or** `proof` in `commitment` / `zk-knowledge`

## Answers shape

```json
{
  "intent": "I maintain calm focus",
  "mode": "creative",
  "wallpaper": false
}
```

Full path may add: `kamea_encoding`, `square`, `planetary_seal`, `proof`, `kdf`,
`planetary_geometry`, `spare_mode`, `phonetic`, `polish`, `seal_packet`, …

## Sessions

Stored under `<state root>/wizard-sessions/<id>.json`, owner-only, never under `references/` (state root: see `hermes-runtime-contract.md`). An older `out/wizard-sessions/` in the skill tree is still read.

```bash
python3 scripts/sigil_forge.py wizard --session-new --path quick
python3 scripts/sigil_forge.py wizard --next --session <id> --answers-json '{...}'
```

## Human TTY

```bash
python3 scripts/sigil_forge.py wizard --interactive --path quick --out out/sigil-forge
```

Type `done` after intent to accept remaining defaults.

## Related

- CLI: `python3 scripts/sigil_forge.py wizard --help`  
- Planetary options: `methods-planetary-characters.md`  
- Runtime: `hermes-runtime-contract.md`  
- Proof of Intent: `proof-of-intent.md`
