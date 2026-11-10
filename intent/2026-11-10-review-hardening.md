# Intent

## Problem

The November 2026 review (`docs/REVIEW-2026-11.md`) found that the code was
mostly careful but its surroundings were not: CI ran no tests, a production
deploy workflow for another product sat in this repo, the stdlib-only install
failed without PyYAML, the Noir prover witness (plaintext intent and nonce)
was left on disk, untrusted PNGs could exhaust memory, the installer refused
macOS temp paths, and defaults had fallen behind current guidance.

## Proposed outcome

Pull request #14 lands the fixes listed in sections 3 and 3b of the review,
each as its own commit with a test, so any one can be dropped.

Out of scope: packaging the engine as an importable module, porting the Noir
provider to `bb`, swapping the pure-Python AES-GCM for a library, the Abraxas
adapter, the licence decision, and every repository setting.

## Affected users / systems

Hermes operators installing or running the skill; the offline CLI
(`construct`, `verify`, `open`, `inspect`, `wizard`); the install tree; CI.
`SKILL.md`, `AGENTS.md` and `references/` are not changed.

## Constraints / non-goals

Hermes skill, not a plugin. No new bots. No `SKILL.md` rewrite. No new
required dependency: the core path stays stdlib-only. Existing sealed images
and existing state directories must keep working. No efficacy or
authority-seal changes.

## Open questions

- Licence: `LICENSE` is ZSPL-1.0, draft #5 proposes MIT. Owner decides. The
  landing-page commit only makes the page match the current `LICENSE`.
- Repository settings (secret scanning, push protection, required checks,
  re-enabling CodeQL): owner decides.
- This intent was written after the work started, at the request of the
  automated review on #14. Acceptance is the owner's review of that PR.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The suite passes on Linux on Python 3.10 (pytest only) and 3.13 (optional extras) | `OBSERVED` | CI checks on #14 |
| No secret exists in the tree or in history | `OBSERVED` | gitleaks with and without the allowlist over all branches; regex sweep |
| Images sealed at 200,000 PBKDF2 iterations still open | `OBSERVED` | `tests/test_crypto_seal.py` |
| OWASP's floor for PBKDF2-HMAC-SHA256 is 600,000 | `OBSERVED` | OWASP Password Storage Cheat Sheet, read 2026-11-10 |
| Current Noir no longer ships `nargo prove` / `nargo verify` | `INFERRED` | noir-lang/noir issue 4960 and current Noir docs; `nargo` not installed here |
| The Noir path works end to end with any toolchain | `NOT_COMPUTABLE` | No `nargo` or `bb` on the review machine |
| The symlink policy is safe on Windows | `INFERRED` | Without POSIX ownership every link stays refused, as before |

## Author / date

- Author: Claude (review session for the repository owner)
- Date: 2026-11-10
