# Agent contract — Sigil-Forge

You are working in **Sigil-Forge** (`Zero-State-LLC/Sigil-Forge`), a
**standalone Hermes skill** (not a plugin). This file is the canonical
contributor contract for Cursor, Claude, Codex, Grok, and OpenClaw.
Harness adapters (`CLAUDE.md`) only point here.

`SKILL.md` is the Hermes **runtime** behavior contract. Do not rewrite
it as part of this pack. Do not invent a second Hermes contract, a
plugin adapter, or new bots.

## Intent

Read the active `intent.md` under [`intent/`](intent/) before editing.
Next stage is a spec or plan from this repo's existing docs — do not
skip to code.

If the change is non-trivial and no intent exists, draft one from
[`intent/_TEMPLATE.md`](intent/_TEMPLATE.md) and wait for a human to
accept it. Trivial docs and chore fixes do not need an intent file.
See [`intent/README.md`](intent/README.md).

## Commands

Fill only from this repo's scripts. Do not invent commands.

| Task | Command |
|---|---|
| Tests | `python3 -m pytest -q` |
| Hermes frontmatter | `python3 scripts/validate_hermes_skill.py` |
| Smoke (hermes + PoI) | `python3 scripts/sigil_forge.py check` |
| Env / packaging | `python3 scripts/sigil_forge.py doctor` |
| Offline evals | `python3 scripts/sigil_forge.py eval` |
| Install preview | `bash install.sh --dry-run` |

## Invariants

- Hermes **skill**, not a plugin. Install: `~/.hermes/skills/sigil-forge`.
- Offline-first. No cloud image APIs inside the skill.
- Never mutate `references/` during ordinary runs.
- Refuse harm and authority-seal (Enochian / Goetic) requests. No
  silent Spare substitute. No efficacy claims.
- Wallpaper PNG is the product; packets are workspace. Public media:
  digests/roots only — never plaintext intent or commitment nonce.
- Learning ledger stays PROPOSED; human-only `ledger promote`.
- No secrets in the tree. Human yes on deploy, spend, and legal.
  Do not copy Noema deploy-worker or pin workflows here.

## Docs

No `graft/`. Start at `README.md`. Runtime: `SKILL.md`,
`references/hermes-runtime-contract.md`. Safety:
`references/safety-and-framing.md`. Design (clone only):
`docs/superpowers/specs/2026-08-07-sigil-forge-design.md`.

## Escalation

If CI, tests, or validators look wrong — missing coverage, silent
skips, green-but-inert checks, or a suite that contradicts the spec:

1. Open a bounded defect issue labeled `bug`. Do not expand the
   current task to paper over it.
2. Do **not** weaken, skip, or rewrite assertions to obtain a
   passing result.
3. Reward-hacking is forbidden: no silent skips, no fixture forgery,
   no green-at-any-cost edits.

Escalate to the owner instead of guessing on `SKILL.md` frontmatter
or Hermes index limits, authority-seal / efficacy policy, passphrase
or vault handling, or production deploy. A red honest check is
better than a green lie.

## Team context

Org and partner status is not this repo. When a task needs
cross-repo or partner state, load
[Zero-State-LLC/agent-context](https://github.com/Zero-State-LLC/agent-context):

1. `HANDOFF.md`
2. `STATUS.md`
3. `DECISIONS.md` only if a prior choice affects this task

Clone: `gh repo clone Zero-State-LLC/agent-context ~/agent-context`.
Pull `--ff-only` before trusting a local copy.

## Skills

Name only skills that already exist. Do not invent skills or bots.
This repo **is** the `sigil-forge` Hermes skill. Defaults:
`anti-slop-code`, `production-systems`, `google-developer-style`.
