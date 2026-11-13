# Noir circuit: intent_commitment (knowledge of intent)

## Statement

Private inputs: padded intent bytes + 32-byte nonce  
Public inputs: the intent's byte length, and `SHA-256(nonce || intent_bytes[256])`

The length is bound exactly: bytes before it must be non-zero and bytes from it
on must be zero. An intent containing a NUL byte is therefore not provable, and
the provider refuses it.

Matches `src/sigil_forge/proofs/zk_commit.py` (`sha256-nonce-pad256-v1`).

A proof shows that whoever made it knew an intent and nonce behind the public
commitment. It is provenance only: it says nothing about what a sigil does.

## Requirements

Optional. Core Sigil-Forge works **without** any of this.

- `nargo` 1.0.0 (Noir compiler; solves the witness)
- `bb` 6.0.0 (Barretenberg; proves and verifies)

Both are needed: Noir moved proving and verification out of `nargo`. Other
versions are untested, and `nargo` and `bb` must be a matching pair.

```bash
bash scripts/install-noir-toolchain.sh
```

That script downloads the official release archives, checks pinned SHA-256
hashes, and installs to `~/.nargo/bin` and `~/.bb`. The engine looks there as
well as on `PATH`. The first proof on a machine makes `bb` download its
reference string to `~/.bb-crs`; nothing else uses the network.

## How the provider runs it

`src/sigil_forge/proofs/noir_provider.py` copies `Nargo.toml` and `src/` to a
private temporary directory for every call and deletes it afterwards. This
directory is never written, so there is no `target/` or `Prover.toml` here.

Prove:

```bash
nargo execute                      # Prover.toml -> target/intent_commitment.gz
bb prove -b target/intent_commitment.json -w target/intent_commitment.gz \
  -o out -t evm --write_vk
```

The run keeps `proofs/intent-proof.bin` and `proofs/intent-proof.vk`. The
witness (`Prover.toml`, plaintext intent and nonce) is created `0600` and
removed with the temporary directory, on success and on failure.

Verify:

```bash
nargo compile
bb write_vk -b target/intent_commitment.json -o vk -t evm
bb verify -k vk/vk -p <the proof file> -i <public inputs> -t evm
```

`verify` rebuilds the verification key from this circuit instead of trusting
the `.vk` stored with a run, and builds the public inputs from the commitment
and length it is asked about. A proof for another commitment or length, an
altered proof, or a proof from a different circuit fails.

`verify-proof` credits a Noir proof to a run only when the commitment and
length in the proof manifest equal the ones in the run's `forge-packet.json`.
Tool output is never copied into a result, because `nargo` can print witness
values.

## Circuit versions

- **2** (current): SHA-256 built from `std::hash::sha256_compression`, because
  Noir 1.0 removed `std::hash::sha256`. No external dependency. The intent
  length is a public input and is bound to the bytes.
- **1**: used `std::hash::sha256` and the removed `nargo prove` / `nargo verify`.
  Its proofs do not verify with this provider.

## Integration

```bash
python3 scripts/sigil_forge.py construct \
  --intent "…" --proof zk-knowledge --passphrase via env
python3 scripts/sigil_forge.py verify-proof <run directory>
```

If either tool is missing, construct still succeeds and the proof-manifest
records `status: skipped` / `detail: noir_unavailable`. A local capsule
knowledge attestation is still generated for offline operator verification
(not ZK).
