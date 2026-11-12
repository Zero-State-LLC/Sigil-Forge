# Archive divergence: live main vs the personal v0.14.0 line

Date: 2026-11-12

Refs compared: `origin/main` (6185fd7, VERSION 0.13.1) and
`origin/personal-archive-2026-10-09` (b0fb11d, VERSION 0.14.0). Merge base 8b6b981.
Labels: OBSERVED means I ran it or read the object in git. INFERRED means read from
code or docs, not exercised.

## Summary

- If main stays as it is, you lose an agent-agnostic engine layer (`SIGIL_FORGE_HOME`, `~/.sigil-forge`, `--hermes`), five extension commands (mostly stubs) and the v0.14.0 notes.
- The archive lacks all 17 main commits: licence, Hermes description contract, org CI and all 17 hardening rows below.
- The lines conflict in 18 files (5 code, 4 tests, 6 docs, 3 config or metadata).
- Tests (OBSERVED): main 319 passed, 12 skipped; archive 268 passed, 0 failed.
- Recommendation: (b), narrowed. Declare main canonical, tag the archive, port the path layer first.
- Yours to decide: licence (archive MIT, main ZSPL-1.0) and the next version number.

## What the archive has that main lacks

44 commits, 47 files, +2531 -262 (OBSERVED, `git diff --stat 8b6b981 <tip>`). Authors:
Daniel Meyer plus one Hermes Agent co-author. Release notes are at
`docs/RELEASE_NOTES.md` on the archive, not at the repo root.

| Theme | Commits | What it does for a user | Main files | Size |
|---|---|---|---|---|
| Install safety (#24) | 9ed8caa | Staged, rollback-safe installer, state outside the skill tree | `install_transaction.py`, `tests_audit/*` | about +1100 |
| Agent-agnostic engine (#25) | 5c8f789, 251e69c, 1afc243 | Runs outside Hermes; `~/.sigil-forge` default; `--hermes` opt-in; `agent_contract_ok` replaces `hermes_ok` | `paths.py`, `install.sh`, `sigil_forge.py`, `SKILL.md` | about +250 code, +120 docs |
| Optional extensions | 2d0e210 to 9ba7abb (about 18 commits) | Five new subcommands plus wizard steps | five new modules, `wizard.py` +126, `tests/test_extensions.py` +133 | about +390 modules, +85 CLI |
| CI | 40dde2f, 0b65e16, 9a948bc | pytest 3.10 to 3.12, check, doctor, smoke | `.github/workflows/ci.yml` | +56 |
| Docs and release chores | about 20 commits | Release notes, plan stubs, README badge, v0.14.0 bump | `README.md`, `QUICKSTART.md`, `references/*-plan.md` | about +600 |

The commit log is noisy: about 20 commits on 2026-09-22 only add, remove and re-add
plan stubs (audio, plate, storyboard) and generated sample files.

CLI surface (OBSERVED, `add_parser` on both tips): main has `help check construct verify
list doctor eval`, same as the base. The archive adds `plate-import`, `storyboard`,
`adapters`, `steganalysis`, `comfyui`. `wizard`, `inspect`, `open` and the others are
not in this grep on either side, so they are registered another way; no change there.

Check of the authors' claims against code:

- "Agent-agnostic": TRUE. `paths.py` reads `SIGIL_FORGE_HOME`, `SIGIL_FORGE_ROOT`,
  `SIGIL_FORGE_DIR`, `SIGIL_FORGE_SKILL_DIR`, with `HERMES_SKILL_DIR` last. State goes to
  `~/.sigil-forge/state`, falling back to the old Hermes state dir if it exists.
  `install.sh` defaults to `~/.sigil-forge`; `--hermes` targets the Hermes skills dir.
  `check` and `doctor` report `"packaging": "standalone-engine"` and keep `hermes_ok`
  as an alias. SKILL.md is reworded as an "optional agent contract".
- "Plate import, storyboard, adapters, steganalysis, comfyui shipped, functional":
  OVERSTATED. These are small stubs (INFERRED from reading all of `adapters.py`,
  the head of `steganalysis.py` and `plate_import.py`, and the `cmd_*` handlers).
  `steganalysis.analyze_channels` returns hardcoded values (`present: True`,
  `capacity_bits: 1024`, `density: 0.12`) and does not read any artifact.
  `adapters.py` returns dicts and a formatted string. The CLI handlers write fixed
  paths in `/tmp` (`plate_import_cli.json`, `storyboard_cli`), run on demo data, and
  `steganalysis` and `comfyui` ignore arguments. `plate_import.py` imports
  `xml.etree`, which main removed elsewhere for semgrep `use-defused-xml`.
  Wizard integration (`use_plate_import` and similar steps) exists; its value depends
  on these stubs.
- "241 tests": TRUE for `tests/` only on the first claim. The whole archive suite
  is 268 passing (OBSERVED, below). CI runs `tests/` only, so the installer tests in
  `tests_audit/` never run in the archive's CI.
- SKILL.md frontmatter on the archive: version 0.14.0, `license: MIT`, a 275-character
  description, extra `triggers:` list and `dependencies: []`. Main's validator rejects it
  (OBSERVED, ran main's `validate()` on the archive SKILL.md): "description length 275 > 60"
  and "description must be one sentence".
- New top-level files: `.ignore`, `.github/workflows/ci.yml`; new dirs: `docs/comfyui/`.
  No `schemas/` changes (OBSERVED: none in the stat). No new runtime dependency.

## What main has that the archive lacks

17 commits (OBSERVED, `git log 8b6b981..origin/main`), 76 files, +4316 -519.

| Theme | Commits |
|---|---|
| Org chores: issue, PR and feature templates, CODEOWNERS, project automation, CodeQL baseline | d4c9da7, c7339f6, a6447fe, bfb505d, 4dffa43, d8a13f7, 3e70931 |
| Licence ZSPL-1.0 | a80628e |
| Hermes v0.21 contract: 54-char description, SKILL.md cut from 409 to 226 lines, validator gate | 2178042 |
| Org multi-agent SDLC pack (`AGENTS.md`, `CLAUDE.md`, `intent/`) | 26e72a0 |
| Install safety fix, same intent as the archive's #24 | e45228a |
| CI: free security scan replaces CodeQL, valid permission key, pin-currency workflow removed | 5d3b801, d7e9ff1, 9f9458b |
| Security fix: provider commands without `shell=True` | 45784f9 |
| Lint fix | aeb3289 |
| Hardening squash and November review (#14) | 6185fd7 |

Hardening items, checked on the archive ref (`b0fb11d`). All rows are OBSERVED by reading
the archive file at the line shown.

| # | Hardening item | On main | On archive tip |
|---|---|---|---|
| 1 | `.gitignore` for `.env*`, keys, `Prover.toml`, caches | yes | no (no such entries in `.gitignore`) |
| 2 | Noir `Prover.toml` created 0600, no-follow, deleted after proving | yes | no (`proofs/noir_provider.py:77-79` writes it in the skill tree, no cleanup) |
| 3 | Frontmatter validator works without PyYAML, fails closed | yes | no (scalar-only fallback, `validate_hermes_skill.py:42-52`) |
| 4 | `install.sh` passes paths as `argv`, not into `python3 -c` | yes | no (`install.sh:152` interpolates `${ROOT}` into `r'''...'''`) |
| 5 | PNG read inflates only what IHDR declares | yes | no (`stego_png.py:142` unbounded `zlib.decompress`) |
| 6 | SF12 vault inflate capped at 8 MiB | yes | no (`wallpaper/vault.py:193` unbounded) |
| 7 | PNG size cap, 100 megapixels | yes | no (`stego_png.py`, no limit) |
| 8 | Provider command: no `shell=True`, split before substitution | yes | no (`wallpaper/providers.py:74-75` substitutes into a string, then `shell=True` at about line 104) |
| 9 | PBKDF2 default 600,000 iterations | yes | no (`crypto_payload.py:11` is 200_000) |
| 10 | Argon2 parameters read from the blob, bounded | yes | no (`crypto_payload.py:54-56, 139` compiled-in constants) |
| 11 | Noir `verify` fails closed unless the proof is the one in hand | yes | no (`noir_provider.py:176-198` runs `nargo verify`, ignores `proof_path`) |
| 12 | Installer trusts system symlinks, refuses planted ones | yes | no (`install_transaction.py:50` refuses any symlink; the cause of the 34 macOS failures on the base) |
| 13 | Private state dirs 0700, session files 0600, atomic writes | yes | no (`paths.py` and `wizard.py` have no `chmod` or private writer) |
| 14 | CI: pinned action SHAs, no persisted credentials, Dependabot, pinned dev deps | yes | no (`ci.yml` uses `@v4`/`@v5`, `pip install ... \|\| true`) |
| 15 | `security-scan.sh` with pinned scanner checksums | yes | no (file absent) |
| 16 | `ruff` lint in CI, unused imports removed | yes | no (no `ruff.toml`) |
| 17 | Description length gate (60 chars) in `check` and `doctor` | yes | no (275-character description) |

Not applicable to the archive: the Noema deploy workflow and the duplicate PR template were
never on that line. Items 14 to 16 are CI and tooling rather than runtime code.

## Conflict surface

OBSERVED: `git merge-tree --write-tree --name-only origin/main origin/personal-archive-2026-10-09`
exits 1 with 18 conflicted paths.

| Group | Files |
|---|---|
| Code (5) | `install.sh`, `scripts/install_transaction.py` (add/add), `scripts/paths.py`, `scripts/sigil_forge.py`, `scripts/wizard.py` |
| Tests (4) | `tests_audit/test_install.py`, `test_output_help.py`, `test_state.py`, `test_transaction.py` (all add/add) |
| Docs (6) | `README.md`, `QUICKSTART.md`, `SKILL.md`, `references/expansion-spine.md`, `references/hermes-runtime-contract.md`, `references/source-and-upgrades.md` (add/add) |
| CI, config, metadata (3) | `.github/workflows/ci.yml` (add/add), `.gitignore`, `VERSION` |

Largest code conflicts by conflict-marker lines (OBSERVED counts; the one-line summaries
are INFERRED from the hunks and diffs):

1. `install_transaction.py` (4 hunks, 83 lines). Both sides added about 300 lines for the
   same #24 fix. Main added `untrusted_symlink()` trust rules; the archive added
   `_profile_home()` and `SIGIL_FORGE_*` env handling.
2. `sigil_forge.py` (8 hunks, 80 lines). Main added the 60-character description gate and
   Hermes-state help text; the archive renamed `hermes_ok` to `agent_contract_ok` and
   added five extension subcommands.
3. `install.sh` (3 hunks, 32 lines). Main routes the symlink check through
   `untrusted_symlink` and keeps the Hermes default; the archive defaults to
   `~/.sigil-forge`, adds `--hermes`, and has its own symlink check.
4. `paths.py` (1 hunk, 13 lines). Main added `ensure_private_dir` and
   `write_private_text` and a Hermes-first state dir; the archive added the
   `SIGIL_FORGE_HOME` env chain and `default_state_root()`.
5. `wizard.py` (2 hunks, 13 lines). Main switched sessions to the private-dir helpers;
   the archive added the extension wizard steps and changed the state path wording.

Largest overall: `SKILL.md` (8 hunks, 298 lines) because main rewrote it to 226 lines.

Hidden risk: `scripts/construct.py` and three `tests/` files merge without conflict
although both sides edited them (INFERRED). They need a run, not just a conflict check.

## Tests on each line

Run from a scratch copy of each tip with the shared venv interpreter, `-q -p no:cacheprovider`,
`TMPDIR` set to a symlink-free directory. The venv has no PyYAML (OBSERVED).

| Line | Summary line (OBSERVED) | `def test_` count |
|---|---|---|
| main | `319 passed, 12 skipped, 20 subtests passed in 167.62s` | 286 |
| archive | `268 passed, 18 subtests passed in 157.04s` | 268 |

No archive test failed. The 12 skips on main are tests that need PyYAML or argon2; they
skip on this interpreter, so they are environmental, not defects. The archive suite passes
without PyYAML only because its validator keeps the scalar-only fallback (hardening row 3).
The archive suite does not run the default macOS temp dir: I did not test that, and the
base is known to fail there (INFERRED from the November review).

## Licence and metadata

| Item | main | archive tip |
|---|---|---|
| `LICENSE` first lines | "ZERO STATE PROPRIETARY LICENSE", "Version 1.0, August 2026" | "MIT License", "Copyright (c) 2026 Daniel Meyer" |
| SKILL.md `license:` | `LicenseRef-Zero-State-Proprietary-1.0` | `MIT` |
| SKILL.md `version:` | `0.13.1` | `0.14.0` |
| `VERSION` | `0.13.1` | `0.14.0` |
| SKILL.md `description:` | 54 characters | 275 characters |
| SKILL.md author | Daniel Meyer (scrimshawlife-ctrl), Hermes Agent | Applied Alchemy Labs / scrimshawlife-ctrl |

Other public MIT copies exist (the archived personal repo, with a v0.14.0 GitHub release
per the release notes; INFERRED, not checked on GitHub). Anything merged from the archive
arrives under MIT unless re-licensed by the author. The author is the same person.

## Other preserved branches

| Branch | Tip | Ancestor of archive tip | Unique content |
|---|---|---|---|
| `personal-archive/feat/agent-agnostic-standalone-engine` | 251e69c | yes (OBSERVED) | none |
| `personal-archive/fix/authored-skills-audit` | 54af671 | no (OBSERVED) | 4 commits (7b15eca, 567780b, f74c121, 54af671) from 2026-09-04 |

The audit branch is the pre-squash history of #24. Its tree equals 9ed8caa, the squash on
the archive line (OBSERVED: `git diff` between 54af671 and 9ed8caa is empty). The archive
tip also contains the "undecodable Neon provenance" fix (`install_transaction.py:169`).
So nothing is lost by ignoring this branch except commit history. Neither branch is an
ancestor of main.

## Options and recommendation

All effort figures are INFERRED.

| Option | PRs | Risky parts | What could be lost | Hardening and CI |
|---|---|---|---|---|
| (a) merge archive into main | 1 big PR plus 1 to 2 fix-ups | 18 conflicts; `install_transaction.py` (two versions of one file); SKILL.md; licence; version | little, but easy to resolve wrongly: a resolve toward the archive side silently reverts hardening | kept only if every conflict is resolved toward main; clean-merging files keep main's fixes |
| (b) port themes onto main, one PR each | about 4 to 5: paths, install.sh, extensions, wizard steps, optional docs | agent-agnostic (touches paths and install, and collides with the `src/sigil_forge/` move); extensions need cleanup first | commit history only; the five stubs if you decide to skip them | untouched: you build on main, so all 17 rows stay |
| (c) restart from archive tip | 6 or more: re-apply 16 hardening commits, licence, org files, SKILL.md contract | everything in main's review; the `shell=True` fix and licence history | main's 17 commits as history, and the independent review in section 3c | re-done by hand; high chance of a missed row |
| (d) archive stays unmerged | 1 docs PR plus a tag | none | agent-agnostic layer, extensions, tests that only the archive has (`test_extensions.py`) | untouched |

Recommendation: (b), narrowed. Declare main canonical now (the (d) step), then port only
what is worth having, in this order: the path layer, then `install.sh --hermes`, then the
extensions after they are fixed (no `/tmp` writes, no `xml.etree`, no hardcoded analysis
numbers, tests for each). Skip the plan stubs, release notes and generated samples. Do
the path layer before the `scripts/` to `src/sigil_forge/` move, because both rewrite
`paths.py` and `install.sh`, and the second one is cheaper to do on top of the first.

First concrete PR: port `scripts/paths.py` environment resolution from the archive
(`SIGIL_FORGE_HOME` and the other three variables ahead of `HERMES_SKILL_DIR`, plus
`default_state_root()`), keeping main's `ensure_private_dir` and `write_private_text`,
with the archive's `tests/test_paths.py` additions. Keep today's default state location
(`~/.hermes/state/sigil-forge`) so installed users see no change. Pair it with a
no-code step: push a tag on the archive tip so the line cannot be lost.

Before PR 2 (changing the install default to `~/.sigil-forge`), the owner has to decide
whether this is a Hermes skill or a standalone engine. That is a product decision, not a
merge detail.

## Not determined

- Whether the v0.14.0 tag and GitHub release exist on the archived personal repo. Taken
  from the release notes; I did not query GitHub.
- The default macOS temp-dir behaviour of the archive suite (I used a symlink-free dir as
  instructed), so how many archive tests fail there is untested.
- Whether main's stdlib frontmatter parser would accept the archive's `triggers:` list and
  flow-style `related_skills`. The validator already fails on description length first.
- Whether the `.hallmark/` and `.ignore` additions on the archive matter to anyone.
- Which contents of the extension modules could be kept as real features. I read three of
  the five modules in full or in part; `comfyui_templates.py` and `storyboard.py` were
  not read beyond their CLI handlers.
- Conflict resolutions were not attempted, so the true merge effort is an estimate.
- The correct version number after a port (0.14.0 is already public on the archive).
