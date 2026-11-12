# Assessment: the five optional extensions from v0.14.0

Date: 2026-11-12. Scope: `plate-import`, `storyboard`, `adapters`, `steganalysis`, `comfyui` from tag
`personal-archive-v0.14.0`, judged for a port to main (0e0de17). Labels: OBSERVED means I ran it from an extracted copy of the tag, or read the object in git.
INFERRED means read from code only. The archive copy ran with `HOME` and `TMPDIR` set to
scratch dirs. The CLI handlers hardcode `/tmp`, so they wrote there anyway (see below).

## Summary

| Extension | Claim | Reality | Verdict | Effort |
|---|---|---|---|---|
| plate-import | Import scanned MS plates, normalize to stroke format | Truncates path text to 100 chars, no geometry; default source yields an error record | REWRITE | about 150 lines plus tests |
| storyboard | Multi-frame carriers, per-frame artifacts | Writes intents as plaintext JSON to `/tmp`; no forge, no safety check | REWRITE | about 90 lines plus tests |
| adapters | Interop with Orchestra, Kubrick, ComfyUI | Three dict labels; returns `exported: True` and `bound: True` unconditionally | DROP | 0 |
| steganalysis | Deeper geometric multi-channel analysis | Returns constants (`present: True`, `density: 0.12`) and reads no file | REWRITE | about 120 lines plus tests |
| comfyui | Bundled local ComfyUI workflow templates | Three dicts of node names; not runnable workflows | DROP | 0 |

Common facts (OBSERVED): all five modules are stdlib only, with no `subprocess`, network
or `shell`. None touches `safety.py`, `policy_lint.py` or the authority-seal gate. The
`/tmp` writes are in the CLI handlers in `scripts/sigil_forge.py`.

## plate-import

Claim (release notes): "Scanned unique MS plate import pipeline". Module docstring:
"Normalizes external SVG/JSON into plate stroke format using reference corpus."

CLI (OBSERVED, lines 1675-1676): `plate-import [--source SOURCE]`, default
`references/planetary-plate-strokes.json`.

Inputs: a user-chosen file (untrusted). `.json` is read whole with `json.loads`; `.svg`
is read whole and parsed with `xml.etree`. No size bound. Outputs: the CLI handler writes
the fixed path `/tmp/plate_import_cli.json` for any input (OBSERVED). Deterministic.
It keeps, per `path`, `polyline` or `polygon`, the tag name, the first 100 characters of
the `d` text and `len(d)`. It parses no coordinates. `matches_reference_structure` is
`len(ref_strokes) > 0`, so it says nothing about the input.

Runs (OBSERVED):

| Input | Result (trimmed) |
|---|---|
| default corpus JSON | `[{"error": "no element found: line 1, column 0"}]`, count 1 |
| `a.svg` (path plus polyline), `b.svg` (one path) | two records, then one, text copied |
| `c.svg` (a circle only) | `[{"type": "empty", ...}]` |
| entity-expansion SVG | `[{"error": "limit on input amplification factor ..."}]` |

The default run is the finding. The corpus is `{"entries": {planet: ...}}`; the importer
looks for `"strokes"`, finds none, parses `""` as SVG and stores the parse error as a
stroke. It still prints `imported:` and exits 0. SVG outputs differ only by copied text.

Dependencies: `xml.etree`, which main removed elsewhere (semgrep `use-defused-xml`). The
expat amplification limit stopped the entity bomb here (OBSERVED), but main should not rely
on that.

Tests: `test_plate_import` asserts `count >= 0` and `out.exists()`. A constant-returning
`import_and_save` that writes any JSON passes. The CLI test only checks exit code 0 and
the word `plate-import` in stdout.

Safety and framing: no efficacy claims. "Unique MS plate" overstates; the bundled corpus
says it is "Not a unique manuscript plate scan". Nothing checks whether an imported plate
is a Goetic or Enochian figure.

Verdict: REWRITE. Spec:

1. `plate_import.py` reads an SVG or JSON file, size cap 1 MiB (read `cap + 1`, refuse over).
2. No XML parser. Scan for `<path d=` and `<polyline points=` with a bounded regex.
3. Tokenize `M L H V Z` (absolute and relative) and point lists into float pairs; refuse
   curves (`C S Q T A`) with a named error rather than approximating.
4. Normalize to the 0..1 unit square, same shape as `plate_strokes.traditional_plate_strokes`.
5. Cap strokes (for example 256) and points per stroke (for example 4096).
6. Write the result under `default_state_root() / "plates"` with `write_private_text`.
7. A nonzero exit and no file when zero strokes parse.
8. Nothing on main consumes an imported plate, so it is a converter with no caller.

## storyboard

Claim: "Multi-frame storyboard carriers ... storyboard.json + per-frame artifacts."

CLI (OBSERVED, lines 1678-1679): `storyboard [--intent INTENT]`, repeatable; default is
two demo intents.

Inputs: intents from argv, or two demo strings. Outputs: `/tmp/storyboard_cli/` with
`frame_00.json` and so on plus `storyboard.json` (OBSERVED), plaintext intents, empty
`geometry`, absolute paths. With no flags it wrote the demo text; with three `--intent`
flags it wrote those three. It is a faithful JSON writer and no more. The word "carrier"
is not earned: no digest, glyph, stego or run directory.

Privacy: `safety-and-framing.md` says intent text is sensitive: hash in run paths, no
plaintext in public media. Writing raw intents to a world-readable `/tmp` path breaks
that rule. No call to `check_intent`, so a harmful intent or an authority-seal request
is written without refusal.

Tests: `test_storyboard` asserts `count == 2` and that the index exists. Weak, not inert.
`add_frame` is never used by the CLI.

Verdict: REWRITE (small). Spec:

1. `storyboard.py` takes 1 to 12 intents (bound the count and each length).
2. For each, call main's `construct.run(intent, out_root=<state>/storyboards/<id>)`,
   which already does safety, digest, glyph and packet. Refusals abort the whole board
   with no partial output.
3. The index records frame number, run id, `sigil_root` and digest prefix only. No
   plaintext intent, no absolute paths.
4. Board id is a hash of the ordered digests. Write the index with `write_private_text`.
5. CLI `storyboard --intent X --intent Y [--out DIR]`; no demo defaults (error on zero).

This is the most useful of the five because it reuses the real engine.
## adapters

Claim: "Rich Orchestra/Kubrick/ComfyUI adapters", "exports geometry/prompts/receipts in
compatible formats".

CLI (OBSERVED, line 1681): `adapters` with no flags. The handler prints the three names
and `example: ComfyUI`. It reads and writes nothing.

What it does (OBSERVED, read in full): `export_geometry_for_adapter({"sigil_root": "x"})`
returns `{"geometry": {}, "exported": True}`. `bind_receipt_to_adapter` returns
`"bound": True` for any input. `render_adapter_prompt("focus", "kubrick")` returns
`"[Kubrick] focus\n\n[geometry and channels ready for export]"`. No Orchestra or Kubrick
file format is specified anywhere on the tag (INFERRED from `git ls-tree`: a plan stub only).

Dependencies: none. Tests assert the module's own dict keys, so they pass for a no-op.
`exported: True` and `bound: True` are fabricated success flags, the "green-but-inert"
pattern AGENTS.md forbids.

Verdict: DROP. The target formats are undefined, and the engine already writes
`forge-packet.json` and a manifest a host can read. If a concrete consumer is named later,
write that one exporter against its real format.

## steganalysis

Claim: "Deeper geometric multi-channel steganalysis ... capacity, correlation".

CLI (OBSERVED, line 1682): `steganalysis`, no flags, no path argument. The handler analyses
the literal `{"sigil_root": "demo"}` and `"<svg demo>"` and prints `correlation: 0.003`.

Runs (OBSERVED):

| Call | Result |
|---|---|
| `analyze_channels` with root `AAA`, channel `svg` | `present: True, capacity_bits: 2048, density: 0.12` |
| same with root `BBB` | identical, only `artifact_id` differs |
| channel `fake_channel_that_does_not_exist` | `present: True, capacity_bits: 2048, density: 0.12` |
| `geometric_correlation` on `x*100` with `y*50` or `z*50` | both `0.03` |
| `estimate_capacity(["png_lsb","svg"])` | `1536`, safe `768` |
| `generate_report` | `NameError: name 'json' is not defined` |

Every number is a constant or a function of string length. `correlation_score` is
`(len(svg)+len(png))/5000`. A nonexistent channel is reported present. The CLI never reads
an artifact.

Dependencies: it imports `stego_png` and never calls it. Tests assert
`"analysis" in rep`, `"correlation_score" in corr` and `safe_capacity_bits > 0`; a constant
return passes all three. This is the clearest green-but-inert case of the five.

Safety and framing: invented figures are presented as analysis, and the name implies a
detector that does not exist. That is an accuracy claim the code cannot back.

Verdict: REWRITE, renamed so it does not imply detection, for example `png-stats`. Spec:

1. Input: a PNG path, size cap 64 MiB, read with `stego_png.read_rgb_png` (bounded inflate,
   100 megapixel cap). It reads only 8-bit non-interlaced RGB with filter 0, so it covers
   this tool's own PNGs and refuses others with a clear error.
2. Compute from the pixel bytes: capacity in bits, ones in the LSB plane, ones ratio, and
   a chi-square over (2k, 2k+1) value pairs.
3. Optionally try `unpack_payload(extract_lsb(...))` and report `header_found`. Report
   counts, never payload bytes.
4. Print the definition and state: "not a detector; a value does not show that data is
   hidden or absent".
5. JSON to stdout; `--out` writes under `default_state_root()`.
6. Drop `geometric_correlation` and the SVG side; they have no honest definition.

## comfyui

Claim: "Optional bundled ComfyUI workflow templates (local only, no cloud)".

CLI (OBSERVED, line 1683): `comfyui`, no flags. It prints
`['minimal_background', 'atmospheric', 'sigil_influenced']` and `loaded: Minimal Background`.

What it holds (OBSERVED, read in full): three dicts whose `workflow` is a list of node
name strings such as `["latent", "controlnet", "prompt"]`. A ComfyUI API workflow is a graph
of numbered nodes with `class_type` and `inputs` (INFERRED, not checked against its docs).
These dicts cannot be loaded into ComfyUI. `docs/comfyui/example_background.json` on the
tag is likewise a sketch (INFERRED). `render_template_for_wallpaper` returns 16 hex
characters of the hash and a fixed hint; no workflow changes with the hash. The docstring
says `sigil_influenced` "respects immutable glyph hash"; nothing in the code does.

Dependencies: none. Tests: `"minimal_background" in temps` and `"glyph_hash" in r` pass for
any dict with those keys. Main's `ai_generated` background path already accepts a
host-supplied image file, so the real integration point exists without this module.

Verdict: DROP. A real template needs a workflow validated in a real ComfyUI install. If
wanted later, ship one JSON export from the owner's ComfyUI under `docs/`, with no Python.

## Tests in `tests/test_extensions.py`

OBSERVED: 7 tests, all pass on the archive copy. None compares two different inputs to two
different outputs. The CLI test checks exit code 0 and keywords from the help text, and
skips `storyboard`. The last test covers existing construct code, not an extension.

## Wizard steps

Diff `8b6b981..personal-archive-v0.14.0 -- scripts/wizard.py` (OBSERVED): version 2.1.0 to
2.2.0; five bool steps added to the `full` path only (`skip_ok`, default `False`); an
`extensions` dict in `answers_to_construct_kwargs`; a post-construct block in
`apply_answers`; and the session dir change (path-layer work, already on main).

| Step id | Depends on | Apply behavior | Port alone? |
|---|---|---|---|
| `use_plate_import` | plate-import | imports the corpus by a relative path and gets the error stroke | Only after the rewrite, and only with a caller |
| `use_storyboard` | storyboard | writes the real intent plus the literal "follow up frame" into the run dir, a second plaintext copy | After the rewrite; the fixed frame must go |
| `use_adapters` | adapters | returns the adapter names | Drop |
| `run_steganalysis` | steganalysis | stores constants in the result | Drop; call the new stats on `glyph.png` if wanted |
| `use_comfyui_templates` | comfyui | returns template names | Drop |

Each block sits in `try/except Exception` and stores `<name>_error`, so a failure hides
behind a successful apply (OBSERVED). The steps are independent. Add a wizard step only
when its extension has landed, with a step-order test. The version bump is the owner's call.

## Port plan

One extension per PR, safest first. Each must pass `python3 -m pytest -q` and ruff and add
no dependency.

PR 1: `png-stats` (from steganalysis), effort about half a day.
- Add `src/sigil_forge/png_stats.py`. Wire `png-stats PATH [--out FILE]` in `cli.py`.
- Tests that fail against constants: build two PNGs with `write_rgb_png` (all-even pixels
  vs random pixels) and assert the ones ratio and chi-square differ and match hand
  computed values; embed a payload with `embed_lsb` and assert `header_found` flips;
  oversize and non-PNG inputs return nonzero; no file written on error.
- Docs: a short README section only.

PR 2: `storyboard`, effort about half a day.
- Add `src/sigil_forge/storyboard.py`; `cli.py` gets `storyboard --intent ... [--out]`.
- Tests: two intents give two run dirs and different `sigil_root` values; the same intents
  give the same board id; the index file contains no intent text (grep for it); a harmful
  intent as frame 2 produces no output at all; an authority-seal request is refused;
  zero intents exits nonzero; 13 intents exits nonzero.
- Docs: README paragraph.

PR 3 (optional, lower value): `plate-import`, effort about one day.
- Add `src/sigil_forge/plate_import.py`; `cli.py` gets `plate-import --source FILE`.
- Tests: a triangle path normalizes to known unit coordinates; a curve command is refused;
  a file over the cap is refused; an SVG with a DOCTYPE entity is not expanded; a circle-only
  SVG exits nonzero; the output differs for two different shapes.
- Do this only if the owner has plates to import, because nothing consumes the result.

PR 4 (optional): one wizard step for storyboard, after PR 2, about 40 lines plus a test.

Do NOT port now: `adapters` and `comfyui` (no honest minimal version), the five wizard
steps as they stand, the release notes and the plan stubs.

## Not determined

- Whether Orchestra or Kubrick have a public interchange format (not searched outside the repo).
- The exact ComfyUI API workflow schema (stated from memory).
- Whether `construct.run` handles many calls in one process (read the signature, did not
  run it). Check run-id collisions within the same second.
- The wizard `apply_answers` path was read, not run end to end.
- Side effect: the archive CLI wrote `/tmp/plate_import_cli.json` and `/tmp/storyboard_cli/`
  on this machine (the first file pre-existed from an earlier run). I removed both.
