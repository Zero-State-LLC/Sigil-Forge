# Packaging research: the `sigil_forge` import package

Date: 2026-11-11. Research only; the only file written in the repo. Experiments
ran in a throwaway copy outside the repository on Python 3.11.15, setuptools
79.0.1, pip 24.0 (3.10 was not installed, so nothing ran on 3.10). OBSERVED
means I ran or read it this session; UNVERIFIED means I did not check it.

## Recommendation in brief

Do option A: a real `src/sigil_forge/` package, imports rewritten
mechanically, `scripts/sigil_forge.py` kept as a thin shim. Option B fails on
the first sibling import. A costs 294 import edits; a quick prototype passed
284 of 318 tests, and the 34 failures were subprocess or install-layout tests.
Use setuptools, install from a git tag for now, and add licence metadata only
once the licence is decided.

| Question | Recommendation | Main reason |
|---|---|---|
| 1 Layout | A: `src/sigil_forge/`, absolute imports, one mechanical commit | B fails with `ModuleNotFoundError`; A is 294 import lines |
| 2 Data files | `skill_root()`: env var, then marker walk-up, no package data yet | A wheel has no `schemas/`; `skill_root()` points at site-packages |
| 3 Distribution | Git tag, setuptools backend, `LicenseRef-` only after the licence call | No index needed; setuptools 77+ builds `LicenseRef-` expressions |
| 4 Compatibility | Shim forever; bare names removed in the move, opt-in alias if needed | 173 references to `scripts/sigil_forge.py`, some printed at run time |

## 1. Layout

### Option B experiment (OBSERVED)

Minimal `pyproject.toml` in a repo copy:

```toml
[tool.setuptools]
packages = ["sigil_forge", "sigil_forge.wallpaper", "sigil_forge.proofs"]
[tool.setuptools.package-dir]
sigil_forge = "scripts"
"sigil_forge.wallpaper" = "scripts/wallpaper"
"sigil_forge.proofs" = "scripts/proofs"
```

After `python3.11 -m venv` and `pip install .`, from a clean directory:

```
$ python -c "import sigil_forge.paths"        -> ok (site-packages/sigil_forge/paths.py)
$ python -c "from sigil_forge import construct"
  File ".../sigil_forge/construct.py", line 11, in <module>
    from artifact_root import build_sigil_root
ModuleNotFoundError: No module named 'artifact_root'
```

Build and install work and leaf modules load; any module importing a sibling
fails. `pip install -e .` gave the same error. Findings:

- `scripts/sigil_forge.py` becomes `sigil_forge.sigil_forge` and inserts its own
  directory into `sys.path` at import. After that, `from sigil_forge import
  construct` works, but modules load twice (`sigil_forge.construct is
  construct` printed `False`). An alias shim keeps the collision.
- Shadowing: with `scripts/` first on `sys.path` (what `python3
  scripts/sigil_forge.py` does), `import sigil_forge` returns the script:
  `ModuleNotFoundError: No module named 'sigil_forge.cli'; 'sigil_forge' is not
  a package`. The shim must put the package directory ahead of `scripts/`.

### Option A size (OBSERVED)

Level-0 imports of sibling modules, counted with `ast` (indented ones included):
`scripts/` 163 statements in 43 of 62 files (94 top-level, 69 in functions);
`tests/` 131 in 33 of 37 files (107 top-level, 24 in functions);
`tests_audit/` 0. Total 294 statements in 76 files.

`tests_audit/` uses `spec_from_file_location`, so it needs path edits. Hand
edits: the `importlib.import_module` loops in `scripts/sigil_forge.py` (lines
170, 737), `tests/test_paths.py` (`import scripts.paths`; asserts
`scripts/paths.py` exists), and `sys.path.insert` in generated code strings
(`tests/test_wallpaper_providers.py:131`, `tests_audit/test_state.py:25`).

### Option A prototype (OBSERVED)

In `A2`: modules moved to `src/sigil_forge/`, 294 imports rewritten by an AST
script, `skill_root()` set to `parents[2]`, 5-line shim, `conftest.py` on `src/`.
Installer and required-file lists were not updated.

- Baseline copy: `319 passed, 12 skipped` in 194 s.
- Prototype: `34 failed, 284 passed, 12 skipped, 1 deselected` in 104 s.
- The 34 failures are in `test_check`, `test_hermes_packaging`, the wallpaper,
  proof and SF11 CLI tests, and two `tests_audit` files. Log causes: child
  processes running `from stego_png import ...` (`ModuleNotFoundError`), tests
  that copy or install `scripts/`, and required-file lists. None is an
  in-process rewritten import.
- `python3 scripts/sigil_forge.py help` worked through the shim; `check` with
  `HERMES_SKILL_DIR` set ended `"schemas_ok": true`.

The packaging guide supports A: src layout stops a root directory shadowing the
installed copy; its cost (no running the CLI from the tree without a
workaround) is what the shim covers
(https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/).
Option C (flat `sigil_forge/` at the root) loses that protection.

## 2. Locating data files

### What breaks (OBSERVED)

`skill_root()` returns `HERMES_SKILL_DIR`, else `Path(__file__).parent.parent`.
In the non-editable option B install that is `site-packages`, and
`sigil-forge check` printed, trimmed:
`"schemas/intent-capsule.schema.json: missing", ... "schemas_ok": false`.
With `pip install -e .` it returned the checkout, so editable installs hide the
bug. In layout A the depth changes too (`parents[2]`).

Callers (grep): `VERSION` (`construct.py:642,904`, `wallpaper/pipeline.py:172`),
`schemas/` (`construct.py:883`), `references/*.json`, `zk/noir`
(`proofs/noir_provider.py:33`), `check`, `doctor`. Two write state:
`receipt.py` lines 37, 44, 51 use `skill_root()/"out"/"sigil-forge"` and
`wizard.py:891` reads `skill_root()/"out"/"wizard-sessions"`. In a wheel that
points into site-packages.

### Options

1. Package data read with `importlib.resources` (`files()`, 3.9+;
   https://docs.python.org/3/library/importlib.resources.html). Setuptools
   says files outside a package have no supported retrieval mechanism
   (https://setuptools.pypa.io/en/latest/userguide/datafiles.html). The data
   would move under `src/sigil_forge/`, but `SKILL.md` must stay at the skill
   root, so the Hermes tree changes. The intent forbids that.
2. Keep the skill-tree layout, find the root by marker: (a)
   `HERMES_SKILL_DIR` if set, unchanged; (b) walk up from `paths.py` to the
   first directory holding both `SKILL.md` and `VERSION` (at most 4 levels);
   (c) otherwise `check` reports "skill data not found" and code-only paths
   (digest, seal, verify, inspect) still work. The Hermes tree and a checkout
   both resolve at (b). This is the smallest change that leaves the install
   tree unchanged.
3. If Abraxas later needs schemas from a wheel, ship them as package data
   after (b). UNVERIFIED how to map directories outside `src/`.

Recommendation: option 2 now, option 3 on demand. Move the `out/` writes in
`receipt.py` and `wizard.py` to `default_out_dir()` before any wheel ships.

## 3. Distribution, licence, build backend

### Git tag or index

`pip install "sigil-forge @ git+https://<host>/<owner>/Sigil-Forge.git@v0.13.1"`
is the documented form for a tag (https://pip.pypa.io/en/stable/topics/vcs-support/).
It needs no account, index or upload decision. A private index adds hosting and
a credential for one consumer; PyPI makes a proprietary package public.
Recommendation: git tag now; revisit after the licence decision and a second
consumer. UNVERIFIED: whether PyPI accepts `LicenseRef-` on upload (PEP 639 says
indexes validate expressions).

### PEP 639 and the guides (OBSERVED reads)

- PEP 639 is Final (core metadata 2.4). `license` is an SPDX expression string;
  `license-files` is a list of globs; a glob matching nothing is an error. The
  `license = {text|file}` tables and `License ::` classifiers are deprecated
  (https://peps.python.org/pep-0639/).
- A custom licence is `LicenseRef-[idstring]`, letters, digits, `.` and `-` only
  (https://packaging.python.org/en/latest/guides/writing-pyproject-toml/).
- Backends: setuptools 77.0.0+
  (https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html);
  flit-core 3.11+ (https://flit.pypa.io/en/stable/pyproject_toml.html);
  hatchling accepts both fields (https://hatch.pypa.io/latest/config/metadata/),
  minimum version UNVERIFIED.

### My build test (OBSERVED)

With `license = "LicenseRef-Zero-State-Proprietary-1.0"` and
`license-files = ["LICENSE"]`, `pip wheel .` gave `Metadata-Version: 2.4`,
`License-Expression: LicenseRef-Zero-State-Proprietary-1.0` and
`dist-info/licenses/LICENSE`. `LicenseRef-Zero_State` failed the build. The
repo's `tests_audit/test_license_metadata.py` fails if `pyproject.toml` matches
`\bMIT\b`; the `LicenseRef-` form passes it.

### Backend

Recommend setuptools (`requires = ["setuptools>=77"]`). I built a wheel, an
editable install and a console script with it; it supports `src/` and
`package-data`; it can read the version from a file (`[tool.setuptools.dynamic]
version = {file = "VERSION"}`, UNVERIFIED by build); and it builds
`LicenseRef-` today. The backend is build-time only, so users still get a
stdlib-only package. Hatchling would also do; flit-core is untested here.
Console script: `sigil-forge = "sigil_forge.cli:main"`; `main(argv=None) -> int`
exists at `scripts/sigil_forge.py:1311`.

## 4. Compatibility window

### The real surface (OBSERVED grep counts of `scripts/sigil_forge.py`)

`SKILL.md` 19, `QUICKSTART.md` 15, `README.md` 32,
`references/hermes-runtime-contract.md` 3, code and tests 15; 146 across all
docs; 173 in the whole repo (minus `.git`, `evidence`, `research`,
`proposed-grants`, `out`).

Also printed at run time: `construct.py:626` and `wizard.py` lines 345 to 362
emit `python3 scripts/sigil_forge.py ...`, so receipts and transcripts carry
it. `install.sh` and `install_transaction.py:23` call `sigil_forge.py check`.
`SKILL.md` may not change under the intent.

### Recommendation

- Keep `scripts/sigil_forge.py` as a shim indefinitely. Five lines protect 173
  references and every Hermes install. It inserts `<root>/src` ahead of
  `scripts/` before importing `sigil_forge.cli`.
- Do not keep bare names importable. The move PR rewrites the tests, and the
  intent names no outside user of bare names (UNVERIFIED for unknown users).
  Thirty-nine stub files in `scripts/` would reintroduce the collision. Put a
  changelog note in the release.
- If a user appears, ship an opt-in `sigil_forge.compat.install_bare_names()`
  that registers `sys.modules` aliases. Never on by default.

## 5. Migration plan

Each PR keeps CI green (ruff, validator, pytest, `install.sh --dry-run`, 3.10 and 3.13).

1. Metadata only. `pyproject.toml` with build-system, name, dynamic version from
   `VERSION`, `requires-python = ">=3.10"`, no dependencies, no scripts. Add a
   test that `SKILL.md` version equals `VERSION`. Risk: low.
2. Marker-based `skill_root()`, plus moving `receipt.py` and `wizard.py` state
   writes to `default_out_dir()`. Add a test for a tree with no `SKILL.md`.
   Risk: low to medium (`out/` paths appear in receipts).
3. The move. `git mv` the modules to `src/sigil_forge/`, `sigil_forge.py` to
   `cli.py`, run the AST rewrite, write the shim, switch `conftest.py` to
   `src/`, add `[project.scripts]`, update the three required-file lists
   (`install.sh`, `cmd_check`, `install_transaction.py`), `tests_audit` paths
   and subprocess tests. `validate_hermes_skill.py` and `install_transaction.py`
   stay at their `scripts/` paths because CI and `install.sh` run them.
   Risk: high, the riskiest step. Mitigation: one commit, no logic edits.
4. CI install check: `pip install .`, then `import sigil_forge.construct` and
   `sigil-forge help` from a temp directory, on both legs.
5. Optional, on demand: schema package data, `importlib.metadata` fallback.

Order: 2 before 3; 4 right after 3.

## 6. Version single-sourcing

`VERSION` (0.13.1) is read by `install.sh`, `install_transaction.py`,
`construct.py` (twice) and `wallpaper/pipeline.py`; `SKILL.md` repeats it, and
`validate_hermes_skill.py` never compares them (by grep). Keep `VERSION` as the
source. `pyproject.toml`: `dynamic = ["version"]` with `{file = "VERSION"}`
(UNVERIFIED by build; test in PR 1). `sigil_forge.__version__` reads `VERSION`
via `skill_root()`, else `importlib.metadata`. `SKILL.md` keeps its literal
version (Hermes reads it); a PR 1 test fails if they differ.

## Risks

- The move (PR 3) touches 76 files and about 34 tests that spawn processes.
- A wheel writes state beside the code unless `receipt.py` and `wizard.py` use
  `default_out_dir()`. Fix before publishing.
- Licence metadata in `pyproject.toml` is reserved to the owner by the intent.
  An MIT relicense also changes `test_license_metadata.py`.
- Everything ran on 3.11; 3.10 is UNVERIFIED. The 34 failures skipped installer
  and required-file updates, so they are a floor for PR 3, not a forecast.

## Sources (all opened this session)

- https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- https://peps.python.org/pep-0639/
- https://setuptools.pypa.io/en/latest/userguide/datafiles.html
- https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html
- https://docs.python.org/3/library/importlib.resources.html
- https://hatch.pypa.io/latest/config/metadata/
- https://flit.pypa.io/en/stable/pyproject_toml.html
- https://pip.pypa.io/en/stable/topics/vcs-support/
