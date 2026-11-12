# Noir circuit: intent_commitment (knowledge of intent)

## Statement

Private inputs: padded intent bytes + 32-byte nonce  
Public input: `SHA-256(nonce || intent_bytes[256])`

Matches `src/sigil_forge/proofs/zk_commit.py` (`sha256-nonce-pad256-v1`).

## Status: experimental

This path targets the older `nargo prove` / `nargo verify` commands. Current
Noir releases moved proving and verification out of nargo into a separate
backend (`nargo execute` for the witness, then `bb prove` / `bb verify`), so
with a current toolchain `--proof zk-knowledge` records `status: failed` for
the Noir step and falls back to the local capsule attestation. `verify` only
accepts a proof that is byte-identical to the one in this directory, because
`nargo verify` checks the directory, not a file you pass it. Treat a Noir
result as provenance only until the provider is ported.

## Requirements

- [nargo](https://noir-lang.org/) installed
- Core Sigil-Forge Python path works **without** nargo

## Build / prove / verify

```bash
cd zk/noir/intent_commitment
nargo compile
# Prover.toml is written by src/sigil_forge/proofs/noir_provider.py
nargo prove
nargo verify
```

## Integration

```bash
python3 scripts/sigil_forge.py construct \
  --intent "…" --proof zk-knowledge --passphrase via env
python3 scripts/sigil_forge.py verify-proof out/sigil-forge/<run-id>
```

If nargo is missing, construct still succeeds and the proof-manifest records
`status: skipped` / `detail: noir_unavailable`. A local capsule knowledge
attestation may still be generated for offline operator verification (not ZK).
