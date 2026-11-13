# Intent

## Problem

`forge-manifest.json` was designed and documented as public, but it copied the
packet's `methods` block: reduced letters, the Hebrew transliteration, kamea
and rose-cross sequences, and per-channel counts. The intent can largely be
read back from that (issue #45, the same finding as #31 for receipts). The two
manifest leaves in the root were also the same digest, and nothing in the
engine let anyone check a manifest against the root.

## Proposed outcome

- `forge-manifest.json` (schema 2.0.0) holds method identifiers and digests
  only, so it can be shared.
- The detail moves to a private `method-manifest.json` with its own leaf.
- `verify-root` recomputes the root and checks both manifests against their
  leaves, with no passphrase, from the public files alone.

Out of scope: salting `intent_digest`, changing the packet or the receipt,
recomputing the glyph leaf, and signing.

## Affected users / systems

Anyone reading `forge-manifest.json` for method detail must read
`method-manifest.json` or the packet now. Nothing in this repository did. The
Abraxas adapter reads only `artifact-root.json` and receipts and is unaffected:
leaf names are unchanged. `sigil_root` for new runs is computed over a changed
leaf; it was already different on every run.

## Constraints / non-goals

Stdlib only. Runs made before the split must keep verifying, and their old
manifest must be reported as not public. No plaintext intent or nonce in
either manifest. No efficacy or authority-seal change.

## Open questions

- The public manifest keeps `planet` for the kamea method. It is chosen from
  the public digest or named by the operator, and is visible in the glyph.
- `intent_digest` is still an unsalted hash in public files (#31).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The public manifest holds no letters, sequences, counts, plaintext or nonce | `OBSERVED` | `tests/test_manifest_split.py` walks every value |
| Both leaves match their files and differ from each other | `OBSERVED` | same file |
| `verify-root` passes with only the two public files | `OBSERVED` | same file |
| A run shaped like the old format still checks and is reported private | `OBSERVED` | same file, old shape rebuilt in the test |
| The glyph leaf cannot be recomputed from the finished glyph | `OBSERVED` | same file; the root is written into the glyph after the leaf is taken |
| No reader outside this repository depends on method detail in the manifest | `INFERRED` | Searched this repository and the Abraxas adapter only |

## Author / date

- Author: Claude (review session for the repository owner)
- Date: 2026-11-13
- Status: ACCEPTED. The owner chose "split it" on issue #45 in chat on 2026-11-13.
