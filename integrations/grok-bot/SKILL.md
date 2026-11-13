---
name: sigil-forge
description: Forge an intent statement into a sigil wallpaper PNG with the offline Sigil-Forge engine. Use when asked for a sigil, intent glyph or sigil wallpaper.
---

# Sigil-Forge for Grok Bot

Turn a short statement of intent into a deterministic glyph and a wallpaper
PNG, using the Sigil-Forge command-line engine on your computer. The engine
is plain Python with no packages to install and no image API. You run it; you
never draw the sigil yourself.

This is a creative and focus tool. Never say or imply that a sigil works,
causes events, or replaces professional help.

## 1. When to use it

Use it when the user asks for a sigil, an intent glyph, or a wallpaper made
from a statement of intent, or asks to verify or open one made earlier.

Do not use it for:

- General image generation.
- Enochian, Goetic or other authority seals. The engine refuses these. Do not
  offer a substitute and do not relabel another glyph as one.
- Intents about violence, self-harm, controlling another person, or
  exploitation. Refuse before running anything.
- Any request to state that a sigil has an effect.

## 2. Inputs and access

- **From the user:** the intent, in their own words, as one short sentence
  with consonants in it (for example "I maintain calm focus"). Optionally the
  surface: `phone_lock` (default), `phone_home`, `tablet`, `desktop` or
  `desktop_ultrawide`.
- **On your computer:** `python3` 3.10 or newer, `git` and `bash`. Nothing else.
- **A passphrase, only if the user wants the intent sealed inside the image.**
  Ask for it through the secure secret card, never in chat. It must reach the
  engine as the environment variable `SIGIL_FORGE_PASSPHRASE`. Do not put it
  on a command line, in a file, or in a message. If you cannot set it without
  it appearing in chat, stop and say so.

## 3. Sequence of work

### 3a. Set up (first use, and again after a computer update or reset)

Files persist on your computer, so this normally runs once. Check first:

```bash
export SIGIL_FORGE_HOME="$HOME/.sigil-forge"
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" check
```

If that prints `"ok": true`, skip to 3b. If the file is missing, install.
Installing downloads code, so ask the user to approve it first:

```bash
git clone --depth 1 --branch v0.17.0 https://github.com/Zero-State-LLC/Sigil-Forge "$HOME/sigil-forge-src"
git -C "$HOME/sigil-forge-src" rev-parse HEAD
bash "$HOME/sigil-forge-src/install.sh" --standalone
export SIGIL_FORGE_HOME="$HOME/.sigil-forge"
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" check
```

That installs the tagged release named in the first line. Tell the user that
version and the commit that `rev-parse` printed. Continue only when `check`
prints `"ok": true`. Always set `SIGIL_FORGE_HOME` as shown before any
command: it keeps all output under `~/.sigil-forge/state`.

### 3b. Check the intent

```bash
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" policy check --text "I maintain calm focus"
```

Put the user's sentence in place of the example. If it reports hits, or the
intent is harmful, stop and explain. Do not rewrite a refused intent into
something that passes.

### 3c. Forge

```bash
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" construct --intent "I maintain calm focus" --mode creative --wallpaper --surface phone_lock
```

The command prints JSON. Read `run_id`, `svg`, and `wallpapers[0].wallpaper`
(the PNG to deliver). `wallpapers[0].vault_status` says whether the intent was
sealed into the image; without a passphrase it is not, and the image carries
digests only.

If the engine prints `NOT_COMPUTABLE` (for example an intent with no
consonants) or `AUTHORITY_SEAL_EXCLUDED`, report that plainly. Do not retry
with a different intent the user did not give you.

For a user who wants to be guided one question at a time, use the wizard
instead of 3c:

```bash
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" wizard --session-new --path quick
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" wizard --next --session SESSION_ID --answers-json '{"intent":"I maintain calm focus"}'
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" wizard --session SESSION_ID --path quick
```

Ask only the question the wizard returns each turn. Run the last line when
`next.done` is true.

## 4. Validate the result

Run this on the `svg` path from the forge output before saying anything about
integrity:

```bash
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" verify PATH_TO_GLYPH_SVG
```

Done means all of these hold:

- `construct` printed `"ok": true`.
- `verify` printed `"ok": true`.
- `wallpapers[0].geometry_preserved` is `true`.

If any is false, say which one and do not present the wallpaper as verified.

## 5. What to return

- The wallpaper PNG as a file attachment, not a pasted or re-encoded preview:
  re-compressing the image destroys the data hidden in its pixels.
- One or two sentences: the surface, whether the intent is sealed in the
  image, and that `verify` passed.
- Nothing about what the sigil will do.

Never return, quote, attach, post or sync these files from the run folder.
They are private:

- `forge-packet.json` and `forge-packet.md`: hold the plaintext intent.
- `run-receipt.json` and the receipt log: hold data derived from the intent.
- `intent-capsule.json` and anything under `proofs/`.
- `method-manifest.json`, and `forge-manifest.json` from any run made before
  version 0.18.

Do not paste the intent, the passphrase or a recovered intent into Slack,
email, a pull request, or any shared place.

## 6. What needs the user's approval

Ask first, every time, before you:

- Install or update the engine (it downloads code from GitHub).
- Send the wallpaper anywhere other than this conversation.
- Open a sealed image or packet (`open`), which reveals the intent.
- Delete a run folder.
- Record a learning entry (`learn`). Never run `ledger promote`: that step is
  for a person only.

Do not put this skill in a routine. A sigil starts from an intent a person
states at that moment; nothing here should run on a schedule or trigger.

## Other commands

Use these only when the user asks for what they do.

```bash
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" wallpaper --run PATH_TO_RUN_FOLDER --surface desktop --mode focus
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" inspect PATH_TO_GLYPH_SVG
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" open --wallpaper PATH_TO_WALLPAPER_PNG --json
python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" doctor
```

`wallpaper` makes another surface from an existing run. `inspect` shows the
public data in a glyph. `open` needs `SIGIL_FORGE_PASSPHRASE` and the user's
approval. `doctor` reports the environment.

## If something fails

- `check` is not ok after install: report its output. Do not edit the engine.
- A command is not found or a flag is rejected: run
  `python3 "$SIGIL_FORGE_HOME/scripts/sigil_forge.py" help` and report the
  mismatch. This skill may be older than the engine.
- After a computer update the engine folder is normally still there, because
  it is plain files. If it is gone, repeat 3a.
