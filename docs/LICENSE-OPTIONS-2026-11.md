# Sigil-Forge licence options

Date: 2026-11-11

This is decision support for the repository owner, not legal advice.

## Recommendation

Choose (c), the MIT licence, with copyright held by "Zero State LLC".
Do it only after the owner confirms who owns the code (see "Open points for a lawyer").

Reasons:

1. Most of the code that exists outside this repo is already MIT. The archived public
   copy carries MIT up to v0.14.0 (2026-09-23), which is newer than the live repo (v0.13.1).
   Going proprietary again cannot take that code back.
2. The owner's own stated decision (PR #5, 2026-08-20) is that Zero State Hermes skill
   repos should be open source. The live repo is the odd one out of its own plan.
3. Abraxas is MIT. MIT code can be vendored or installed into it with no licence analysis.
   Every other option adds a licence to track.
4. The code was largely written by AI agents. Section "AI authorship" explains why a
   strict licence on such code is weaker than it reads, so MIT gives up less than it seems.

Single biggest risk: MIT lets anyone sell or host the tool, including a competitor,
with no obligation to pay or share changes. Nothing in the code can be re-restricted later
for versions already released.

The one fact only the owner knows: do you intend to sell the code itself, or charge
for it as a hosted or licensed product?

- If no (you sell wallpapers, services, support, or nothing): MIT, as above.
- If yes, or you want a two-year head start on any competitor: FSL-1.1-MIT. It has a
  real SPDX id, lets anyone read, run and modify it for most purposes, forbids competing
  use for two years per release, then turns each release into MIT. Accept that the
  already-published MIT versions stay MIT.
- Not recommended in either case: keeping ZSPL-1.0 (home-made, contradictory with the
  repo's own tooling and with the MIT copy), or dual licensing (needs a contributor
  agreement you do not have).

## Facts established

Each line has the command or URL. "Unverified" marks what I could not confirm.

Live repo
- Public, licence shown by GitHub as "Other": `gh repo view Zero-State-LLC/Sigil-Forge --json visibility,licenseInfo`.
- `LICENSE` is ZSPL-1.0, "Version 1.0, August 2026", copyright Zero State LLC. Read in full.
- History of `LICENSE`: `git log -- LICENSE` shows two commits only: 1344374 (2026-08-07,
  "Initial commit") and a80628e (2026-08-09, PR #1, adopt ZSPL-1.0). Both by Daniel Meyer.
- The initial commit's `LICENSE` is MIT, "Copyright (c) 2026 Daniel Meyer"
  (a person, not the LLC): `git show 1344374:LICENSE | head`. So the live repo was MIT for
  about two days. Whether it was public in that window: unverified. The GitHub API says the
  repo was created 2026-08-08T15:16:41Z and the PR #1 commit is dated 2026-08-09, so a window of
  about a day is possible.
- `VERSION` is 0.13.1 (branch `hardening/review-2026-11`, same on `origin/main`).
  Latest tag is v0.13.0 (2026-08-07 commit date). `git tag`.
- Latest `origin/main` commit is 2026-10-09 (aeb3289); this review branch is later.
- No `pyproject.toml` exists. `SKILL.md` line 6: `license: LicenseRef-Zero-State-Proprietary-1.0`.
  README says the same twice.
- On `origin/main`, `docs/index.html` says MIT at lines 15, 57 and 266:
  `git show origin/main:docs/index.html | grep -n MIT`. The review branch already changed it to ZSPL-1.0.
- `LICENSE_POLICY.md` says `LicenseRef-Zero-State-Proprietary-1.0` is "an internal SPDX-style
  identifier" and "not an OSI-approved open-source license identifier". It also says earlier
  grants in history, forks or third-party components are not retroactively revoked.
- `tests_audit/test_license_metadata.py` fails if `\bMIT\b` appears in `SKILL.md`, `README.md`,
  `pyproject.toml` or manifests, and requires the ZSPL text in `LICENSE`.
- Forks of the live repo: 0, stars: 0 (`gh api repos/Zero-State-LLC/Sigil-Forge`, `/forks`).

Archived personal copy
- `scrimshawlife-ctrl/Sigil-Forge`: PUBLIC, archived, MIT, created 2026-08-08, last push
  2026-09-23T05:01:16Z (`gh repo view`, `gh api repos/scrimshawlife-ctrl/Sigil-Forge`).
- Its `LICENSE` was never changed after the initial commit: `gh api .../commits?path=LICENSE`
  returns only 1344374. The text is MIT, "Copyright (c) 2026 Daniel Meyer".
- Its `VERSION` is 0.14.0 and it has tag v0.14.0 (`gh api .../contents/VERSION`, `.../tags`).
  Last commit b0fb11d, "polish RELEASE_NOTES.md for v0.14.0".
- The owner's old local clone `~/Sigil-Forge` is older than the archive.
  It has 3 commits, HEAD 251e69c (2026-09-16), `VERSION` 0.13.0, on branch
  `feat/agent-agnostic-standalone-engine`. It is not the last published state.
- The two histories diverged (REVIEW-2026-11.md section 1). The live repo is not a descendant of the
  archive, so MIT-published code (v0.14.0 and earlier on the archive) is newer than
  the proprietary live code (v0.13.1) by version number.
- Net: MIT-licensed public code exists for v0.10.0 to v0.14.0 on the archive. The live repo
  has been proprietary since 2026-08-09 and has not caught up to v0.14.0. I did not diff the
  two trees, so how much of 0.14.0 is absent from live is unverified.

Draft PR #5 (`gh pr view 5 -R Zero-State-LLC/Sigil-Forge`)
- Title "docs: relicense original Zero State materials to MIT", state DRAFT, created 2026-08-21,
  opened by the owner's account through a Cursor agent.
- Stated reason: owner decision on 2026-08-20 that all Zero State Hermes skill repos should be
  open source; aligns with "the MIT posture used by Hyperlex and Kubrick".
- Reviewer prabu-openclaw held approval as a business and legal decision.
- Says "does not rewrite earlier grants in repository history". Changes LICENSE,
  LICENSE_POLICY.md, SKILL.md metadata, README, CONTRIBUTING. It does not touch
  `tests_audit/test_license_metadata.py` in the first 200 diff lines I read (later lines: unverified).
- Hyperlex on GitHub shows licence "other", not MIT (below). Whether its skill frontmatter says MIT: unverified.

Org pattern (`gh repo list Zero-State-LLC --limit 60 --json name,visibility,isArchived,licenseInfo`)
- 60 repos: 31 public, 29 private.
- Public by GitHub licence key: 18 "other" (includes Sigil-Forge, Hyperlex, Noema, Waykin,
  Abraxas-v2.0), 6 MIT (Kubrick, agent-context, athanor-public, continuity-forge, hermes-agent,
  the-long-ascent), 2 Apache-2.0 (noema-client, pawl), 5 none.
- Private: 14 MIT, 11 other, 4 none.
- `Zero-State-LLC/Abraxas` is PRIVATE (licence MIT).
- Most "other" repos are probably ZSPL-1.0 too. I did not open them: unverified.

Contributors (`git shortlog -sne --all`)
- Daniel Meyer, 109 commits, and "Daniel", 57 (same person, two identities).
- Agents and others: Hermes Agent 5, Cursor Agent 3, prabu-openclaw 2, copilot-swe-agent[bot] 1.
- Since a80628e: Daniel Meyer 33, Hermes Agent 1, prabu-openclaw 2.
- No third-party code or dependencies are vendored (stdlib-only Python), per the November review. Not
  re-audited here.

Web sources, each opened (full list under "Sources")
- GitHub ToS D.5: making a repo public lets other users view it and fork it, and "You may grant
  additional rights by adopting a license." D.6: contributions to a repo with a licence notice come in under that licence ("inbound=outbound") unless a separate agreement says otherwise.
- GitHub Docs "Licensing a repository": without a licence, default copyright applies; forks
  and local copies survive if you later make the repo private.
- MIT text (opensource.org, choosealicense.com): says nothing about revocation. Apache-2.0
  section 2 says the copyright licence is "irrevocable".
- Python packaging: `license` takes an SPDX expression, `LicenseRef-` is allowed for
  non-SPDX licences, `license-files` lists the files, licence classifiers are deprecated (PEP 639, packaging.python.org).
- U.S. Copyright Office press release for Part 2 of its AI report (2025-01-29).

## Answers to the five questions

1. Can the MIT grant be revoked? The MIT text has no termination clause and no
   revocation clause, and also does not say "irrevocable". Apache-2.0 does say it.
   Whether a United States court would let a licensor end a free, unconditioned licence at will is a
   legal question I could not settle from a primary source: unverified. Practical position:
   the code is public, copied, and other people may rely on it. Plan as if MIT-published
   versions stay MIT. You can stop publishing new versions under MIT. You cannot rely on being
   able to pull back v0.10.0 to v0.14.0. Closing or deleting the archive would not remove forks or
   clones (GitHub Docs says forks and local copies survive).
2. Public rights under ZSPL-1.0 on a public repo. GitHub ToS D.5 gives every GitHub user the
   right to view and fork. ZSPL section 16 says it does not revoke those platform rights. Beyond that, ZSPL
   section 2 allows inspection for evaluation, security review, education or considering a
   deal. Sections 3a to 3e forbid copying, modifying, distributing, any commercial use (even
   internal), and any production use. Section 4 forbids using it to train or evaluate AI models. Section 15 says it is not open source. So the public may look, and
   may fork on GitHub, but may not run it for work. Problem with a custom licence:
   no SPDX id (only `LicenseRef-`), GitHub shows "Other", licence scanners and procurement checks cannot classify it, section 3d and 3e make even an in-house trial a breach, and section 2 is
   vague about "consideration of a commercial relationship". Partners and contributors
   cannot tell whether they may touch it. It also contradicts the owner's stated plan.
3 to 5. See the table, the AI authorship section, and the checklist.

## AI authorship

The U.S. Copyright Office concluded in January 2025 that AI output is protected only where a
human author determined enough of the expressive elements. Writing prompts alone does
not qualify. Human selection, arrangement and modification of the output can qualify, and using
AI as an aid does not defeat copyright in the human part (Copyright Office, press release
NN 1060 on Part 2 of its AI report). Here that means: where an agent wrote most of a file
and the owner mainly directed it, the file may have thin or no copyright. A restrictive licence
only controls what copyright controls. So a strict licence like ZSPL-1.0 may be weaker than it reads,
and a trade-secret or contract position is not available for code that is public. I only read
the press release, not the report itself, and the PDF would not render to me: unverified in detail.
Also, no source I opened covers code specifically. This also affects whether you can
"sell" or dual-license the code later. Ask a lawyer how to document human authorship.

## Options compared

"Vendored" means a copy lives inside Abraxas. "Separate" means Abraxas calls an installed
copy or a CLI. Abraxas is currently private, so only your own use is at stake today.

| Option | What others may do | Inside MIT Abraxas | Selling it later | Packaging | Reversibility | Effort |
|---|---|---|---|---|---|---|
| (a) Keep ZSPL-1.0, stay public | View, fork on GitHub, inspect. No copying, running at work, or training | Vendored: Abraxas would need to be proprietary too, or you rely on being the owner. Separate: fine for you, blocked for others | Strongest control on paper, but weakened by AI authorship and by the MIT archive | `license = "LicenseRef-Zero-State-Proprietary-1.0"` plus `license-files = ["LICENSE"]`. Valid, but non-standard | Easy to loosen, cannot unpublish the MIT archive | None now. Ongoing: explain it to every partner |
| (b) Keep ZSPL-1.0, make repo private | Nothing, unless invited | Same as (a) but no public confusion | Same as (a). Hides it from buyers too | Same as (a) | Easy to reopen later. Existing forks and copies stay (GitHub Docs). Archive stays MIT and public | Low: one setting, plus decide what to do with the archive and docs site |
| (c) MIT | Anything, including selling and hosting. Keep the notice | Vendored: no conflict. Separate: no conflict | You can still sell services, support and your own builds. You cannot stop others selling the same code | `license = "MIT"` (SPDX). `license-files = ["LICENSE"]` | One way for released versions. Future versions can change licence | Medium: see checklist |
| (d) Apache-2.0 | Anything, plus an express patent grant, with NOTICE and change notes | Vendored: allowed (Apache and MIT mix fine in practice). Needs NOTICE handling. Separate: no conflict | Same as MIT | `license = "Apache-2.0"` | One way for released versions | Medium, a little more than MIT |
| (e1) PolyForm Noncommercial 1.0.0 | Any noncommercial use, modify, distribute under the same terms | Vendored: Abraxas could no longer be pure MIT. Separate: fine for noncommercial users | Good: commercial users must ask you | SPDX `PolyForm-Noncommercial-1.0.0` (confirmed); `license = "PolyForm-Noncommercial-1.0.0"` | Easy to loosen later | Medium. Not OSI approved |
| (e2) PolyForm Shield 1.0.0 | Any use except building a competing product | Same as (e1) for vendoring. Separate: fine unless Abraxas competes | Protects against clones, not against ordinary use | Likely `PolyForm-Shield-1.0.0`. SPDX page did not load: unverified | Easy to loosen | Medium |
| (e3) BUSL-1.1 | Copy, modify, non-production use. Production only if your Additional Use Grant allows it. Becomes GPL-2.0-or-later, or another listed licence, after at most 4 years | Awkward: production use by Abraxas needs your grant. The change licence is GPL-leaning, which clashes with MIT downstream | Good for sales, with conversion | SPDX `BUSL-1.1` (confirmed) | Moderate; the change date is built in | Higher: you fill in parameters |
| (e4) FSL-1.1-MIT | Run, study, modify and share for most purposes. Not for competing use. Each release becomes MIT after 2 years | Vendored: restricted for 2 years per release, then MIT. As the owner you may still use your own code. Separate: fine | Protects the first 2 years, which suits a small product | SPDX `FSL-1.1-MIT` (confirmed to exist) | Releases convert on a schedule. Not OSI approved (not stated on the SPDX page: unverified) | Medium |
| (f) Dual licensing | Public gets one licence (often an open or source-available one), buyers get a paid one | Fine for you; third parties pick one | Best fit for selling. Needs you to hold all rights | Expression like `MIT OR LicenseRef-Zero-State-Commercial` only describes what you offer | Flexible, but only if you own all the code | High: needs contributor agreements and clear ownership, which the AI authorship point complicates |

Notes on the table:
- Choosing (a) or (b) does not remove the MIT archive. Choosing (c) removes the contradiction.
- For (e) and (f), published MIT versions remain MIT, so the new licence only covers new versions.
- Nothing in Abraxas needs a licence for the owner's own use, since the owner owns it. The licence
  matters when Abraxas or Sigil-Forge is shared, sold, or accepted from other contributors.

## What each option would change in this repo

All paths are relative to this repository unless stated. None of these was changed by this document.

Option (c) MIT (recommended)
- [ ] `LICENSE`: standard MIT text, "Copyright (c) 2026 Zero State LLC" (PR #5 already has this).
- [ ] `LICENSE_POLICY.md`: rewrite for MIT and `SPDX-License-Identifier: MIT`. Keep the third-party notices rule.
- [ ] `SKILL.md` line 6: `license: MIT`.
- [ ] `README.md` line 8 badge text and the two "License" sections near lines 460 to 469. There are two
      headings called "License"; merge them.
- [ ] `CONTRIBUTING.md` licensing paragraph. Replace "authorized contributors only" with inbound=outbound (GitHub ToS D.6) or add a short DCO.
- [ ] `docs/index.html`: on `main` it already says MIT (lines 15, 57, 266). On the review branch it says ZSPL-1.0, so drop that review commit or revert it.
- [ ] `tests_audit/test_license_metadata.py`: invert it. It currently asserts the ZSPL text and bans "MIT".
- [ ] `pyproject.toml` (does not exist yet; review rank 3): `license = "MIT"`, `license-files = ["LICENSE"]`.
- [ ] Draft PR #5: use it as the base. It already does most of the above. Check it covers the test file; rebase onto current `main`.
- [ ] Archived repo `scrimshawlife-ctrl/Sigil-Forge`: leave it public and archived. Add a pointer to the org repo
      only if you can unarchive briefly; archived repos are read-only (that restriction is general GitHub behaviour: unverified here).

Option (a) keep ZSPL-1.0
- [ ] Close draft PR #5 with a note.
- [ ] Keep `LICENSE`, `LICENSE_POLICY.md`, `SKILL.md`, README, CONTRIBUTING, test as they are.
- [ ] Keep the review branch's `docs/index.html` fix (ZSPL-1.0) so the page and file agree.
- [ ] Decide the archived repo: leave it MIT and public, and state in the live README that
      earlier versions elsewhere are MIT. Hiding it does not undo the grant.
- [ ] Add `pyproject.toml` with `LicenseRef-Zero-State-Proprietary-1.0` and `license-files`.
- [ ] Tell Abraxas to call Sigil-Forge as a separate process only.

Option (e) standard source-available licence (example: FSL-1.1-MIT)
- [ ] `LICENSE`: official FSL-1.1-MIT text with year and "Zero State LLC" filled in (take it from fsl.software; I did not copy the text).
- [ ] `LICENSE_POLICY.md`: new identifier `FSL-1.1-MIT`, plus a sentence on the two-year conversion.
- [ ] `SKILL.md` line 6, README (two places), `docs/index.html` (all three MIT mentions), `pyproject.toml`: `license = "FSL-1.1-MIT"`.
- [ ] `CONTRIBUTING.md`: contributions come in under the same licence, or require a CLA.
- [ ] `tests_audit/test_license_metadata.py`: assert the new id; remove the "MIT" ban (the licence name contains MIT).
- [ ] Draft PR #5: close, or retitle and rewrite it. Its MIT text would be wrong.
- [ ] Archive: unchanged. It remains MIT, which undercuts the restriction for v0.14.0 and earlier.

## Open points for a lawyer

- Who owns the code: Daniel Meyer personally (the MIT notice in the first commit says so) or Zero State LLC
  (ZSPL and PR #5 say so). Is there a written assignment from you to the LLC?
- Whether the MIT grant made under your personal name binds the LLC as a successor.
- Whether the roughly one day of MIT in the live history and the long-lived MIT archive can be
  limited at all, and whether anyone relying on it has rights to later versions.
- Contributions from prabu-openclaw and from agent accounts (Cursor, Copilot, Hermes): do
  those people or tools' providers hold any rights, and does ZSPL section 6 or GitHub ToS D.6 apply?
- How much of the code is protected given AI authorship, and how to keep a record of human direction.
- If you pick FSL, PolyForm or BUSL: whether their competing-use terms are enforceable
  and clear enough for a solo founder (conversion terms, your state's law).
- Trademarks: "Sigil-Forge" and "Zero State". MIT and Apache-2.0 grant no trademark rights (Apache says so
  explicitly); decide whether to register and add a short trademark note.

## Sources

Opened and used:
- https://docs.github.com/en/site-policy/github-terms/github-terms-of-service (D.5, D.6)
- https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
- https://choosealicense.com/no-permission/
- https://choosealicense.com/licenses/mit/
- https://choosealicense.com/licenses/apache-2.0/
- https://opensource.org/license/mit
- https://www.apache.org/licenses/LICENSE-2.0.txt
- https://polyformproject.org/licenses/noncommercial/1.0.0
- https://polyformproject.org/licenses/shield/1.0.0
- https://spdx.org/licenses/PolyForm-Noncommercial-1.0.0.html
- https://spdx.org/licenses/BUSL-1.1.html
- https://spdx.org/licenses/FSL-1.1-MIT.html
- https://mariadb.com/bsl11/
- https://fsl.software/
- https://peps.python.org/pep-0639/
- https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- https://www.copyright.gov/ai/ (Part 2 published 2025-01-29)
- https://www.copyright.gov/newsnet/2025/1060.html

Tried and not read:
- https://www.copyright.gov/ai/Copyright-and-Artificial-Intelligence-Part-2-Copyrightability-Report.pdf (fetched, text did not extract)
- https://opensource.stackexchange.com/questions/4012/are-licenses-irrevocable-by-default (fetch blocked; seen only as a search snippet, not relied on)
- https://spdx.org/licenses/PolyForm-Shield-1.0.0.html (404)
- https://polyformproject.org/licenses/noncommercial/1.0.0/ and `/shield/1.0.0/` with a trailing slash (404; the versions without it worked)
- GitHub repo data came from `gh` and `git` only; those are local tool output, not web pages.
