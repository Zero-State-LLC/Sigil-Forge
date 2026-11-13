# Intent

## Problem

The Noir `zk-knowledge` proof path could not work with any current toolchain
(issue #15). The provider called `nargo prove` and `nargo verify`, which Noir
removed, and the circuit used `std::hash::sha256`, which Noir 1.0 removed too.
`verify` ran in the shared skill directory and could not check a given proof
against given public inputs.

## Proposed outcome

`--proof zk-knowledge` generates a real proof with nargo 1.0.0 and bb 6.0.0,
and `verify-proof` checks that exact proof against the run's commitment. Both
steps run in a private temporary copy of the circuit. CI exercises the real
toolchain in one leg.

Out of scope: the risc0 path, on-chain verification, and any change to the
commitment scheme.

## Affected users / systems

Operators who use `--proof zk-knowledge`. Nobody else: the toolchain stays
optional and the stdlib-only CI leg still runs without it. `SKILL.md` and
`AGENTS.md` are not changed.

## Constraints / non-goals

No new required dependency. Offline-first: the only network use is bb fetching
its reference string on first proof, and the optional installer script. The
witness never touches the skill tree. No efficacy claim attaches to a proof.

## Open questions

- Proofs made with circuit version 1 do not verify. None can exist from a
  current toolchain, so no migration is offered.
- `verify-proof` now requires the manifest's commitment and length to equal the
  packet's (added after independent review). It does not prove the packet
  itself is untouched; that is what `sigil_root` and the capsule are for.
- Without a passphrase the local attestation check is structural only
  (issue #37). Not changed here.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Prove and verify work end to end on macOS arm64 | `OBSERVED` | `tests/test_proofs_zk.py` real-toolchain tests, nargo 1.0.0 and bb 6.0.0 |
| The circuit's SHA-256 equals Python's for the 288-byte preimage | `OBSERVED` | `nargo execute` satisfies the constraint against `hashlib` output; a wrong length fails |
| bb 6.0.0 is the version paired with Noir 1.0.0 | `OBSERVED` | `barretenberg/bbup/bb-versions.json` in AztecProtocol/aztec-packages |
| Pinned archive hashes match the published release assets | `OBSERVED` | GitHub release asset digests, read 2026-11-12 |
| It works on Linux x86_64 | `INFERRED` until CI runs | CI optional leg installs the toolchain |
| Other nargo/bb versions work | `NOT_COMPUTABLE` | Untested |

## Author / date

- Author: Claude (review session for the repository owner)
- Date: 2026-11-12
- Status: ACCEPTED. The owner approved installing the toolchain and doing the port in chat on 2026-11-12.
