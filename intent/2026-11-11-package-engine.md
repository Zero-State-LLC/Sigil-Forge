# Intent: package the engine as `sigil_forge`

Status: DRAFT, awaiting owner acceptance. No implementation has started.

## Problem

The engine lives as 40 loose files directly in `scripts/` (39 modules plus
`__init__.py`). Tests and the CLI put that directory on `sys.path` and import
modules by bare name, for example `import paths` and
`from construct import run`.

Bare names such as `paths`, `verify`, `safety`, `normalize`, `construct` and
`receipt` are global to the interpreter. Any other code in the same
interpreter that uses one of these names collides with Sigil-Forge. The owner
wants to use Sigil-Forge from the Abraxas project, which is the case this
blocks.

Observed: 26 files under `tests/` and `tests_audit/` import one of twelve
collision-prone names at the start of a line. The most common bare-name
imports are `construct` (17 lines), `normalize` (8), `crypto_payload` (8),
`verify` (5) and `stego_png` (5).

## Proposed outcome

Package the engine as one importable package named `sigil_forge`:

- Add `pyproject.toml` with project metadata and a console script named
  `sigil-forge`. No runtime dependencies are added.
- Engine code is importable as `sigil_forge.<module>`. Where the files sit is
  an open question below.
- `scripts/sigil_forge.py` stays as a thin shim that calls the package, so
  `~/.hermes/skills/sigil-forge` and `bash install.sh` keep working unchanged.
- Tests import `sigil_forge.<module>` instead of bare names.
- CI stays green on Python 3.10 (stdlib only) and on Python 3.13.

Out of scope:

- The Abraxas adapter. It is a later change in the Abraxas repository.
- Any CLI flag, JSON output or JSON schema change.
- Any change to `SKILL.md`.
- Any licence change, including the `LICENSE` file.

## Affected users / systems

- Hermes operators who install with `install.sh` into
  `~/.hermes/skills/sigil-forge`.
- Anyone who runs `scripts/sigil_forge.py` directly.
- The test suites in `tests/` and `tests_audit/`, and `tests/conftest.py`,
  which puts `scripts/` and the repo root on `sys.path`.
- `install.sh`, which inserts a path into `sys.path` at line 73.
- `.github/workflows/ci.yml`.
- Abraxas, as the future consumer that needs a non-colliding import name.

## Constraints / non-goals

- The core stays stdlib-only. `pyproject.toml` adds no required dependency.
- Sigil-Forge remains a Hermes skill, not a plugin. No new bots.
- `install.sh` behaviour is unchanged.
- `HERMES_SKILL_DIR` behaviour is unchanged. It is read by
  `skill_root()` in `scripts/paths.py`.
- No `SKILL.md` rewrite. `references/` is not touched.
- Existing sealed images, state directories and receipts must still open.
- No change to the authority-seal or efficacy policy.
- This intent does not decide the licence.

## Open questions

Owner decides. The drafter's recommendation is in brackets.

1. Layout. Move the files into `src/sigil_forge/`, which is a larger diff, or
   keep them in `scripts/` and add a `sigil_forge` package that re-exports
   them. [Re-export first. It keeps the install tree and paths the same, and
   the move can follow in a later change.]
2. Distribution. Install from git only, or publish to a package index.
   [Git only for now. No index is needed for Hermes or Abraxas.]
3. Licence first? `pyproject.toml` needs a licence value. `LICENSE` is
   ZSPL-1.0 and draft PR #5 proposes MIT. [Decide the licence first. Until
   then the licence field can be left out.]
4. How long bare-name imports keep working, such as `import paths`.
   [Keep them for one release with a deprecation note, then remove them.]

## Verified / assumed claims

- **Verified:** facts checked in this repo or on a green run.
- **Assumed:** beliefs not yet checked. Do not upgrade Assumed to Verified.

| Claim | Label | Basis |
|---|---|---|
| 40 `.py` files sit directly in `scripts/`, 39 modules plus `__init__.py` | `OBSERVED` | `ls scripts/*.py \| wc -l` printed 40 |
| `paths`, `verify`, `safety`, `normalize`, `construct`, `receipt`, `packet`, `fuse`, `spare`, `ontology`, `derivation` and `commitment` are all present in `scripts/` | `OBSERVED` | `ls scripts/*.py` |
| None of those twelve names is a Python standard library module | `OBSERVED` | `sys.stdlib_module_names` check run with `python3` |
| Names such as `safety` and `fuse` also exist on PyPI | `INFERRED` | General knowledge. Not checked against an index in this run |
| Most common bare-name imports in tests: `construct` 17, `normalize` 8, `crypto_payload` 8, `verify` 5, `stego_png` 5 | `OBSERVED` | `grep -rhoE "^(from\|import) [a-z_]+" tests tests_audit \| sort \| uniq -c`. Counts lines, not files |
| 26 files in `tests/` and `tests_audit/` import one of the twelve names | `OBSERVED` | `grep -rl` over both trees, matching the twelve names at the start of a line |
| `scripts/sigil_forge.py` and `install.sh` (line 73) insert a path into `sys.path` at runtime | `OBSERVED` | `grep -rn "sys.path"` |
| `tests/conftest.py` puts `scripts/` and the repo root on `sys.path` | `OBSERVED` | `grep -rn "sys.path"` |
| `skill_root()` reads `HERMES_SKILL_DIR` and otherwise uses the parent of `scripts/` | `OBSERVED` | `sed -n 8,12p scripts/paths.py` |
| No `pyproject.toml`, `setup.py` or `setup.cfg` exists | `OBSERVED` | `ls` returned "No such file" for each |
| `LICENSE` and `LICENSE_POLICY.md` exist | `OBSERVED` | `ls LICENSE*` |
| `LICENSE` is ZSPL-1.0 and draft PR #5 proposes MIT | `OBSERVED` | `head LICENSE`; `gh pr list --state all` shows #5 as a draft titled "relicense original Zero State materials to MIT" |
| CI runs two legs: Python 3.10 with pytest only, and Python 3.13 with the optional extras | `OBSERVED` | `.github/workflows/ci.yml` matrix; both legs passed on #14 |
| Abraxas currently fails when it imports a bare name from this repo | `NOT_COMPUTABLE` | Abraxas was not inspected here. The collision claim comes from review section 5 |

## Author / date

- Author: Claude (drafted for the repository owner; not yet accepted)
- Date: 2026-11-11
