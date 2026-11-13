# Changelog

All notable changes to this project are recorded here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- Storyboard sheet: `storyboard` now also writes `storyboards/storyboard-<board_id>.svg`, one
  SVG that embeds every frame's glyph byte for byte, in order. It carries the whole board: the
  board can be checked from the sheet alone.
- `board_root` in the storyboard index and sheet: a commitment to the ordered frames (digest,
  root and glyph bytes). Frames in the index also record `glyph_sha256`.
- `storyboard-verify PATH` checks a board from its index (`.json`) or its sheet (`.svg`). An
  index written before `board_root` existed still verifies, and the result says so.

## 0.16.0 - 2026-11-13

Tags `v0.13.1`, `v0.15.0` and `v0.16.0` were added with this release; the two earlier releases
had been cut without one. There is no `v0.14.0` tag in this line (see 0.15.0 below).

### Added

- `scripts/set_version.py` writes the version to every place it appears, and `--check` fails
  when one disagrees with `VERSION`. CI runs the check, and a test requires a changelog section
  and a roadmap row for the current version.
- A Grok Bot skill: `integrations/grok-bot/SKILL.md`, with a README on importing it. It runs
  the same engine from a standalone install and changes no engine behaviour. Tests check that
  every command in it exists and that its install and forge steps work with no Hermes present.
  It has not been run inside Grok Bot itself.
- `integrations/grok-bot/BOT.md`: a name, description and brief for a dedicated Grok Bot that
  uses that skill, with notes on sharing it as a template. The skill installs the tagged
  release, not `main`.
- The Noir `zk-knowledge` proof works with the current toolchain (nargo 1.0.0, bb 6.0.0):
  `nargo execute`, then `bb prove` and `bb verify`. It needs `bb` as well as `nargo` now.
- `scripts/install-noir-toolchain.sh` installs both tools from the official release archives
  after checking pinned SHA-256 hashes. CI runs the real prove and verify tests with it.

### Fixed

- The wizard's `spare_mode` step offered `automatic_drawing` and `mantric_alphabet`, which the
  engine rejects. It now offers the real mode names, and a test keeps the two lists in step.
- Docs brought up to date with the code: default output and state locations, the channel list
  (16 channels), optional dependencies, the Spare mode names, crypto defaults, and the command
  tables.

### Changed

- The Noir circuit is version 2: SHA-256 is built from the standard library's compression
  function, because Noir 1.0 removed `std::hash::sha256`. The intent length is now a public
  input bound to the bytes, so the published length is proven. An intent containing a NUL
  byte is refused by the Noir path.
- `verify-proof` without a passphrase no longer reports `verified: true` because the local
  attestation file says `"ok": true`. It reports `verified: false`, `attestation_present: true`
  and says a passphrase is required. With the passphrase, or with a Noir proof, nothing changes.
- `verify-proof` credits a Noir proof only when its commitment and length equal the ones in
  the run's packet. A failed Noir step reports an exit code, never tool output.
- Noir proving and verifying run in a private temporary copy of the circuit. The installed
  skill tree is never written, and the witness is deleted with that copy.
- Noir `verify` rebuilds the verification key from the installed circuit, builds the public
  inputs from the commitment it is asked about, and checks the exact proof file it is given.
  A proof made by the old flow (circuit version 1) does not verify.

- Run receipts are documented as private operator records. They hold no plaintext intent, but
  their `methods` block is derived from the intent and `intent_digest` is an unsalted hash. The
  receipt format is unchanged.
- New `run-receipt.json` files and a newly created `run-receipts.jsonl` are owner-only (`0600`).
  Existing files keep their mode.

## 0.15.0 - 2026-11-12

This release is numbered 0.15.0, not 0.14.0. An earlier personal line of this project already
published a "v0.14.0" with different content. It is preserved in this repository as the tag
`personal-archive-v0.14.0`. Reusing that number would have given two different trees the same
version. The last release from this line was 0.13.1.

### Added

- `png-stats` command: real least-significant-bit counts and a chi-square statistic for a PNG.
  It reports descriptive statistics only and makes no detection claim.
- `storyboard` command: one forge run per intent (1 to 12), plus an index of public digests.
  Every intent passes the same safety and authority-seal checks first, and one refusal fails the
  whole board with nothing written.
- `install.sh --standalone` (installs to `$SIGIL_FORGE_HOME` or `~/.sigil-forge`) and
  `install.sh --hermes` (the existing default, now nameable). `--target` still wins.
- The `SIGIL_FORGE_HOME` family of variables (`SIGIL_FORGE_HOME`, `SIGIL_FORGE_ROOT`,
  `SIGIL_FORGE_DIR`, `SIGIL_FORGE_SKILL_DIR`) so the engine can be located without
  Hermes-specific variables. `SIGIL_FORGE_STATE_DIR` already existed and still wins for state.
- `agent_contract_ok` in `check` and `doctor` output, beside the legacy `hermes_ok`. Both carry
  the same value.
- `sigil_forge` importable package and a `sigil-forge` console script.
- `pyproject.toml` with project metadata. The version is read from `VERSION`.
- CI that runs the tests, ruff, the Hermes frontmatter validator and `install.sh --dry-run`, and
  that installs the built package into a clean venv and runs it.
- Dependabot for GitHub Actions and pip.
- Optional `cryptography` backend for AES-GCM. When the package is installed it is used instead
  of the built-in pure-Python implementation; sealed files open with either. `doctor` reports
  which one is active as `aes_backend`, and `SIGIL_FORGE_AES_BACKEND` can force one.

### Changed

- Licence: the original Zero State materials are now MIT, copyright Zero State LLC.
- The engine moved from `scripts/` to `src/sigil_forge/`. `scripts/sigil_forge.py` and
  `scripts/validate_hermes_skill.py` remain as thin shims. Bare-name imports such as
  `import paths` no longer work.
- The install root is found by a `SKILL.md` plus `VERSION` marker, not by where the code file sits.
- The ledger, receipts and canon proposals default to `<state root>/ledger/`. A ledger at the old
  location is still read and used if the new file does not exist.
- The PBKDF2 default is now 600,000 iterations (was 200,000). Older sealed images still open,
  because each records its own count.
- Default state directories are created `0700` and wizard session files `0600`. Existing
  directories and operator-chosen paths keep their mode.
- Installer symlink policy: links that the operating system ships (for example macOS `/tmp`) are
  accepted. Links planted by a user are refused, and every link is refused when running as root
  or without POSIX ownership.

### Security

These come from `docs/REVIEW-2026-11.md`, sections 3, 3b and 3c.

- The Noir prover witness (`Prover.toml`, with plaintext intent and nonce) is created with
  exclusive no-follow `0600` and deleted after `nargo` returns.
- `install.sh` no longer evaluates the checkout path as Python.
- Zlib inflation is bounded when reading untrusted PNG carriers, and the PNG reader rejects empty
  or over-100-megapixel headers.
- Provider command templates are split first and placeholders are expanded inside each argument.
- Noir `verify` fails closed unless the proof it is given matches the one `nargo` will check.
- `security-scan.sh` verifies pinned SHA-256 checksums for downloaded scanner binaries.
- The stdlib frontmatter parser, used when PyYAML is absent, fails closed on YAML it does not
  support.
- Argon2 parameters are read from the sealed blob within bounds (integers only, memory capped at
  256 MiB).

### Removed

- The Noema deploy workflow (`deploy-worker-pin-pr.yml`).
- The dead Pages workflow (`pages.yml`).
- Issue forms that could not parse.

### Not included

The personal v0.14.0 line is not carried over in full. These parts were left out:

- `adapters`: it returned fixed labels and reported success without exporting anything. See `docs/EXTENSIONS-ASSESSMENT-2026-11.md`.
- `comfyui`: it printed lists of node names, not workflows that ComfyUI can load. See `docs/EXTENSIONS-ASSESSMENT-2026-11.md`.
- `plate-import`: it kept no geometry, and the assessment calls for a rewrite before any port. See `docs/EXTENSIONS-ASSESSMENT-2026-11.md`.
- The `~/.sigil-forge` default install target: the default stays `~/.hermes/skills/sigil-forge`
  so existing Hermes installs are unaffected. See `docs/ARCHIVE-DIVERGENCE-2026-11.md`.

### Upgrade notes

- Reinstall with `bash install.sh`. There is nothing to migrate.
- `python3 scripts/sigil_forge.py` works as before.
- Code that imports engine modules must use `sigil_forge.<module>`, for example
  `from sigil_forge.paths import ...`.
- New ledger files go to `<state root>/ledger/`. An existing ledger at the old location keeps
  being used.
- The Noir zk-knowledge proof path is experimental. Its port to `bb` is tracked in issue #15
  (done in 0.16.0).

---

Earlier history is in git and in the personal archive tag `personal-archive-v0.14.0`.
