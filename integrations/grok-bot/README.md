# Sigil-Forge as a Grok Bot skill

[`SKILL.md`](SKILL.md) in this folder is a self-contained skill for
[Grok Bot](https://docs.x.ai/grok-bot/overview), xAI's cloud agent. It tells a
Bot how to install the engine on its own computer, forge a wallpaper, check
the result, and what to keep private.

It is a second way to reach the same engine. The Hermes skill (`SKILL.md` at
the repository root) is unchanged and stays the reference contract.

## Add it to a Bot

1. In Grok Bot, open the Bot's **Skills**, choose **+**, then **Import Existing
   Skill** and give it this folder's `SKILL.md`. If your client offers only
   **Add Custom Skill**, paste the file's contents.
2. Keep the name `sigil-forge` and the description: Bots use the description
   to decide when the skill applies.
3. Ask the Bot: "Use sigil-forge to make a phone lock-screen wallpaper for:
   I maintain calm focus." The first run asks to install the engine.

## Why it fits

A Bot's computer keeps files between tasks but drops installed packages and
virtual environments after a computer update. Sigil-Forge needs no packages:
the engine is plain Python files under `~/.sigil-forge`, so it survives.

## What is and is not verified

- **Verified in this repository's tests** (`tests/test_grok_bot_skill.py`):
  every command in the skill exists with the flags shown, and the install and
  forge steps work in a clean home directory with no Hermes present.
- **Not verified:** behaviour inside Grok Bot itself. Nobody has run this
  skill in a Bot from this repository. In particular, how a value from the
  secure secret card becomes the `SIGIL_FORGE_PASSPHRASE` environment variable
  is untested; the skill tells the Bot to stop if it cannot do that without
  exposing the passphrase.

## Grok Build

Grok Build (the terminal coding agent) reads `SKILL.md` folders directly and
needs nothing from this folder. Install the root skill where it looks:

```bash
bash install.sh --target "$HOME/.grok/skills/sigil-forge"
```

Not affiliated with or endorsed by xAI. Grok is a trademark of its owner.
