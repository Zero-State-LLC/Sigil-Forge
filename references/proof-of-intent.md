# Proof of Intent (agent reference)

**Skill version:** v0.12.6+ · Load this when the operator asks about commitments,
capsules, `sigil_root`, SF11 stego, `inspect`, `verify-proof`, or ZK/knowledge proofs.

**Not metaphysics.** PoI surfaces bind **provenance** of a forge run to a
privacy-preserving commitment. They never claim the sigil “works.”

## Surfaces (v0.12+)

| Surface | Public? | Role |
|---------|---------|------|
| `intent_digest` | Yes | SHA-256 of normalized intent — forge geometry + legacy stego |
| `intent_commitment` | Yes (value only) | Salted per-run commitment; **nonce stays private** |
| `intent_commitment_zk` | Yes (value only) | Fixed-width companion for optional circuits |
| `sigil_root` | Yes | Merkle root over public leaves (no self-reference) |
| `forge-manifest.json` | Yes | Public config/outputs; hashed into root; **no** `sigil_root` field |
| `intent-capsule.json` | Shell public | Sealed witness (intent + nonce) behind passphrase |
| SF11 stego | Public media | Digest + root carrier (dual-verify with SF1) |

## Hermes packaging note

Sigil-Forge is a **Hermes skill** (`SKILL.md` + offline CLI), not a plugin.
Install: `bash install.sh` → `~/.hermes/skills/sigil-forge`.
Agents invoke scripts; they do not invent geometry or claim proof efficacy.

## Agent procedures

### Wizard (Hermes full path)

```bash
# answers JSON may include "proof": "commitment", "kdf": "auto"
export SIGIL_FORGE_PASSPHRASE='…'
python3 scripts/sigil_forge.py wizard --apply answers.json --path full --out out/sigil-forge
```

Apply result includes `intent_capsule`, `sigil_root`, and next-hints for
`open --capsule` / `verify-proof` / `inspect`.

### Construct with commitment capsule

```bash
export SIGIL_FORGE_PASSPHRASE='…'
python3 scripts/sigil_forge.py construct \
  --intent "I maintain calm focus" \
  --proof commitment \
  --kdf auto \
  --out out/sigil-forge
```

**Done when:** run dir has `forge-manifest.json`, `artifact-root.json`,
`intent-capsule.json`; packet has `intent_commitment` + `sigil_root`;
public SVG has no plaintext intent.

### Open capsule (authorized disclosure only)

```bash
python3 scripts/sigil_forge.py open --capsule \
  out/sigil-forge/<run-id>/intent-capsule.json --json
```

Prefer env passphrase. Never paste recovered intent into public media.

### Inspect / verify-proof

```bash
python3 scripts/sigil_forge.py inspect out/sigil-forge/<run-id>/glyph.svg
python3 scripts/sigil_forge.py verify-proof out/sigil-forge/<run-id> \
  --passphrase '…'
```

`verify-proof` reports provider status. Missing Noir/risc0 → **skipped**, not
a forge failure. Only claim functional ZK when generate **and** independent
verify both pass.

### Proof modes

| Mode | Needs passphrase | Behavior |
|------|------------------|----------|
| `none` | No | Commitment + root still emitted; no capsule |
| `commitment` | Yes | Capsule + local knowledge attestation |
| `zk-knowledge` | Yes | Local attestation + optional Noir (skip if no nargo) |
| `zk-forge` | No | Optional risc0/zkVM path (skip if guest unavailable) |

## Fail closed

- Never put commitment **nonce** in SVG/PNG/wallpaper/public packet fields.
- Never auto-promote learning ledger to canon.
- Never claim efficacy from a proof status of `generated`.

## Related

- Runtime: `hermes-runtime-contract.md`
- Policy: `safety-and-framing.md`, `authority-seal-namespace.md`
- Engine: `src/sigil_forge/forge_core.py`, `src/sigil_forge/commitment.py`, `src/sigil_forge/proofs/`
