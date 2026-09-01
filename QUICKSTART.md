# Sigil-Forge quickstart

Run from the skill root (clone or install dir). **Current version: 0.13.1.**

**Product:** wallpaper PNG with intent + methods sealed in-image (SF12 vault).  
Hermes packaging: **skill** (not plugin). Default install: `~/.hermes/skills/sigil-forge`.

```bash
# 1. Smoke-check
python3 scripts/sigil_forge.py check

# 2. Product path — forge + wallpaper vault (passphrase required for sealed intent)
export SIGIL_FORGE_PASSPHRASE='operator-secret'
python3 scripts/sigil_forge.py construct \
  --intent "I maintain calm focus" \
  --wallpaper --surface phone_lock \
  --embed vault \
  --out out/sigil-forge

# 3. Open the deliverable (wallpaper), not the packet
python3 scripts/sigil_forge.py open --wallpaper \
  out/sigil-forge/*/wallpaper/phone-lock.png --json

# 4. Optional: wizard for guided intake
# python3 scripts/sigil_forge.py wizard --session-new --path quick

# 5. Workspace-only construct (glyph + packet) then wallpaper later
# python3 scripts/sigil_forge.py construct --intent "…" --out out/sigil-forge
# python3 scripts/sigil_forge.py wallpaper --run out/sigil-forge/<run-id> \
#   --surface phone_lock --embed vault

# One-shot construct + wallpaper:
# python3 scripts/sigil_forge.py construct --intent "…" --out out/sigil-forge \
#   --wallpaper --surface phone_lock --wp-mode focus --theme mercurial

# Host AI background (after generating from wallpaper/background-prompt-*.json):
# python3 scripts/sigil_forge.py wallpaper --run out/sigil-forge/<run-id> \
#   --surface phone_lock --background-method ai_generated \
#   --background /path/to/ai-bg.png --provider host_file

# 5. Privacy + Proof of Intent (prefer env over --passphrase)
export SIGIL_FORGE_PASSPHRASE='operator-secret'
python3 scripts/sigil_forge.py construct \
  --intent "I maintain calm focus" \
  --mode practice \
  --seal-packet \
  --proof commitment \
  --kdf auto \
  --out out/sigil-forge
python3 scripts/sigil_forge.py open out/sigil-forge/*/forge-packet.json
python3 scripts/sigil_forge.py open --capsule out/sigil-forge/*/intent-capsule.json --json
python3 scripts/sigil_forge.py inspect out/sigil-forge/*/glyph.svg
python3 scripts/sigil_forge.py verify-proof out/sigil-forge/*/ \
  --passphrase "$SIGIL_FORGE_PASSPHRASE"

# 6. Policy preflight + Hermes hygiene (dev)
python3 scripts/sigil_forge.py policy check --text "I maintain calm focus"
python3 -m pytest -q
python3 scripts/validate_hermes_skill.py
```

**Install to Hermes** (skill tree under `~/.hermes/skills/sigil-forge`):

```bash
bash install.sh --dry-run    # preview (lean tree; no docs/superpowers)
bash install.sh              # install + post-check (validate_hermes + check)
export HERMES_SKILL_DIR="$HOME/.hermes/skills/sigil-forge"
python3 "$HERMES_SKILL_DIR/scripts/sigil_forge.py" doctor
# Reload Hermes skills if the agent is already running
```

Wallpaper outputs live under `<run-id>/wallpaper/` and `<run-id>/receipts/`.  
Canonical `glyph.svg` is never rewritten by wallpaper generation.  
Every construct also emits `intent_commitment` + `sigil_root` (capsule only with passphrase + proof/seal).

See [README.md](README.md), [SKILL.md](SKILL.md),
[references/hermes-runtime-contract.md](references/hermes-runtime-contract.md),
[references/wizard.md](references/wizard.md),
[references/proof-of-intent.md](references/proof-of-intent.md), and
[references/wallpaper-framework.md](references/wallpaper-framework.md).
