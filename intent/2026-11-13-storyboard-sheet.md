# Intent

## Problem

The roadmap lists "storyboard carriers beyond the digest-only index" as
remaining, and issue #11 asks for the next validation slice. Today the only
thing linking a storyboard's frames is the index JSON. A frame's own files
say nothing about the board, the board cannot be checked after the fact, and
there is no single artefact that carries it.

## Proposed outcome

- A **sheet**: one SVG per board that embeds every frame's `glyph.svg` byte
  for byte, in order. Each embedded glyph keeps its own digest and root, so
  the board can be checked from the sheet alone.
- A **`board_root`** in the index and the sheet that commits to the ordered
  frames: intent digest, sigil root and glyph bytes.
- **`storyboard-verify PATH`** for an index or a sheet.

Out of scope: a raster (PNG) sheet, per-frame wallpapers, a wizard step, any
change to how a single frame is forged, and any claim about who made a board.

## Affected users / systems

People who use `storyboard`. The index gains fields and keeps its schema name,
so a reader that ignores unknown keys (the Abraxas adapter does) is unaffected.
Indexes written before this change still verify. `construct` is untouched.

## Constraints / non-goals

Stdlib only. The sheet and index hold public data only: no intent text, no
nonce, no passphrase. Sheets and indexes may come from someone else, so
reading them is bounded (size, frame count) and an index may only name plain
run-folder names, never paths. No efficacy or authority-seal change.

## Open questions

- A board proves internal consistency, not authorship. `--expect-root` lets a
  verifier tie a board to a root they got through a trusted channel. Signing a
  board is a separate decision.
- Independent review of the first version found that a failed rebuild deleted
  the earlier board, that verify could raise or block on hostile input, and
  that a sheet could show a viewer something other than what was checked. All
  fixed before merge: a sheet must now equal the engine's own output exactly.
- The sheet is SVG only. Whether a raster sheet is wanted is left open on the
  roadmap.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| A board verifies from its index and from its sheet alone | `OBSERVED` | `tests/test_storyboard.py` |
| Reordering, swapping, editing or removing a frame fails verification | `OBSERVED` | tamper tests in the same file |
| The sheet and index hold no intent text, nonce or passphrase | `OBSERVED` | test decodes every embedded payload and searches it |
| An older index still verifies and is reported as such | `OBSERVED` | same file |
| The sheet renders in an SVG viewer | `OBSERVED` | rendered once with macOS Quick Look on 2026-11-13 |
| Every SVG viewer renders nested `data:` SVG images | `INFERRED` | Browsers do; some minimal renderers may not |

## Author / date

- Author: Claude (review session for the repository owner)
- Date: 2026-11-13
- Status: ACCEPTED. The owner said to build this slice in chat on 2026-11-13.
