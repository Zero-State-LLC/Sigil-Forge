# Contributing

Agents and contributors follow [`AGENTS.md`](AGENTS.md). Non-trivial Hermes skill work starts with an intent under [`intent/`](intent/). This repository is a standalone Hermes skill — do not invent plugins, extra bots, or Noema deploy dumps here. Do not rewrite [`SKILL.md`](SKILL.md) unless that file is the accepted change.


## Licensing and contributions

This project is licensed under the MIT License. See [`LICENSE`](LICENSE) and [`LICENSE_POLICY.md`](LICENSE_POLICY.md).

Contributions are accepted under the same licence. Do not add third-party code or assets without documenting their licence and keeping required notices.

## Releasing

`VERSION` is the source of truth; `pyproject.toml` reads it. The same number
is repeated in a few docs, so never edit those by hand.

1. `python3 scripts/set_version.py X.Y.Z` writes the version everywhere.
2. In `CHANGELOG.md`, turn `## Unreleased` into `## X.Y.Z - YYYY-MM-DD` and
   leave an empty `## Unreleased` above it.
3. Add a row for `vX.Y.Z` to the Shipped table in
   `references/expansion-spine.md`.
4. `python3 scripts/set_version.py --check` and `python3 -m pytest -q`.
5. Merge, then tag the merge commit: `git tag -a vX.Y.Z -m "vX.Y.Z: <summary>"`
   and `git push origin vX.Y.Z`. The Grok Bot skill installs that tag, so a
   release is not finished until the tag exists.

Use MAJOR.MINOR.PATCH. Before 1.0, a change in behaviour or a new feature
raises MINOR; a fix alone raises PATCH.
