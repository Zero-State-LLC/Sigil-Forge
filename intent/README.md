# Intent files

Non-trivial **Hermes skill** work starts here. Copy [`_TEMPLATE.md`](_TEMPLATE.md)
to a dated, scoped file (for example `intent/2026-09-04-short-slug.md`) and
fill every section before writing a spec, plan, or code.

This repository is the `sigil-forge` Hermes skill (not a plugin). Do not
invent a second skill, a plugin adapter, extra bots, or product work that
belongs in another repo. Do not dump Noema deploy-worker or pin workflows
here.

Do not invent a parallel process. After the intent is written, continue
with the flow this repo already uses:

1. `intent.md` — problem, proposed outcome, constraints, verified vs assumed
2. Spec / plan — `README.md`, `SKILL.md` (runtime contract; do not rewrite
   unless the change is specifically the Hermes contract),
   `references/hermes-runtime-contract.md`, and any approved issue
3. Implementation of skill docs, offline CLI, schemas, or tests only
4. PR with honest `OBSERVED` / `INFERRED` / `NOT_COMPUTABLE` evidence

Trivial docs, chore, and single-line fixes do not need an intent file.
`_TEMPLATE.md` is the blank form; do not fill it in place.

An intent is not a spec, not a plan, and not implementation authority.
It does not authorize rewriting `SKILL.md` by default, extra bots, or
production deploy.
