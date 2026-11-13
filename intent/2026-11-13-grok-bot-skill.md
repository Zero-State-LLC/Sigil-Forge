# Intent

## Problem

Sigil-Forge is packaged as a Hermes skill only. The owner also uses Grok Bot
(xAI's cloud agent) and asked for Sigil-Forge to be usable there. Grok Bot
does not read a Hermes skill directory: it keeps its own skill library, and a
Bot works from a cloud computer with a command line and a persistent
filesystem.

## Proposed outcome

A self-contained skill file a person can import into Grok Bot, which has the
Bot install the engine with `install.sh --standalone`, forge and verify a
wallpaper, and keep the same refusals and private files as the Hermes
contract. No engine behaviour changes.

Added the same day at the owner's request: `BOT.md`, a brief to paste when
creating a dedicated Bot. Grok Bot has no importable Bot file, so this is
text for a person to paste; publishing a template stays with the owner.

Out of scope: a plugin or adapter layer, a second engine entry point, a
routine or trigger, any change to `SKILL.md`, and publishing to a Grok Bot
marketplace.

## Affected users / systems

People who use Grok Bot. Hermes operators are unaffected. The install tree
gains one folder, `integrations/grok-bot/`.

## Constraints / non-goals

`AGENTS.md` says this repository is a Hermes skill and not to invent a second
Hermes contract or new bots. This adds neither: the Hermes contract is
untouched and remains the reference, and the new file is a host-specific
description of the same CLI, added at the owner's request. Offline-first
still holds; the only download is the one-time clone, which the skill makes
the Bot ask approval for. No efficacy or authority-seal change.

## Open questions

- How a value from Grok Bot's secure secret card reaches an environment
  variable is not documented where I could find it. The skill tells the Bot to
  stop if it cannot set `SIGIL_FORGE_PASSPHRASE` without exposing it.
- The skill clones `main`, because no release tag has been published.
  Pinning to a tag is better once one exists.
- `AGENTS.md` still describes the repository as Hermes-only. Its wording is
  the owner's to change.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Every command and flag in the skill exists | `OBSERVED` | `tests/test_grok_bot_skill.py` against the real CLI |
| The install and forge steps work with no Hermes present | `OBSERVED` | same test file, in a clean home directory |
| A Bot's computer has a command line and keeps files but not installed packages | `OBSERVED` | docs.x.ai/grok-bot/computer-and-apps, read 2026-11-13 |
| Grok Bot accepts a skill by "Add Custom Skill" or "Import Existing Skill" | `OBSERVED` | docs.x.ai/grok-bot/team-bots, read 2026-11-13 |
| Grok Bot accepts this file's exact format on import | `INFERRED` | The docs do not specify a format; public Grok Bot skill collections use `SKILL.md` with `name` and `description` |
| The skill behaves as written inside Grok Bot | `NOT_COMPUTABLE` | No Grok Bot available to this session |

## Author / date

- Author: Claude (review session for the repository owner)
- Date: 2026-11-13
- Status: ACCEPTED. The owner asked for this in chat on 2026-11-13.
