#!/usr/bin/env bash
# Sigil-Forge — Hermes skill installer
# Usage:
#   ./install.sh
#   ./install.sh --dry-run
#   ./install.sh --target DIR
#   ./install.sh --version
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_TARGET="${HERMES_HOME:-$HOME/.hermes}/skills/sigil-forge"
VERSION="$(tr -d '[:space:]' < "${ROOT}/VERSION" 2>/dev/null || echo "0.0.0")"

DRY_RUN=0
ALLOW_OUTSIDE_HOME=0
TARGET="$DEFAULT_TARGET"

usage() {
  cat <<EOF
Sigil-Forge Hermes skill installer v${VERSION}

Usage: ./install.sh [options]

Options:
  --dry-run               Show actions without writing
  --target DIR            Install to DIR (default: ${DEFAULT_TARGET})
  --allow-outside-home    Permit --target outside \$HOME
  --version               Print version and exit
  -h, --help              Show this help

Post-install:
  python3 "\$TARGET/scripts/sigil_forge.py" check
EOF
}

log()  { printf '==> %s\n' "$*"; }
warn() { printf '!!  %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

resolve_path() {
  python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

is_forbidden_prefix() {
  case "$1" in
    /|/etc|/usr|/bin|/sbin|/System|/boot|/dev|/proc|/sys) return 0 ;;
    /etc/*|/usr/*|/bin/*|/sbin/*|/System/*) return 0 ;;
    *) return 1 ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --allow-outside-home) ALLOW_OUTSIDE_HOME=1; shift ;;
    --version) echo "$VERSION"; exit 0 ;;
    --target)
      [[ $# -ge 2 ]] || die "--target requires a path"
      TARGET="$2"
      shift 2
      ;;
    --target=*) TARGET="${1#--target=}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

validate_target() {
  python3 - "$TARGET" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1]).expanduser().absolute()
if not sys.argv[1].strip() or any(q.is_symlink() for q in (p, *p.parents)):
    raise SystemExit("refusing empty or symlinked target path")
PY

  local parent base resolved home_resolved
  parent="$(dirname "$TARGET")"
  base="$(basename "$TARGET")"
  # Validation and dry-run do not create destination parents.
  if [[ -d "$parent" ]]; then
    resolved="$(resolve_path "$parent")/${base}"
  else
    # dry-run or missing parent: still normalize for display/validation
    resolved="$(python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$TARGET")"
  fi
  TARGET="$resolved"

  [[ -n "$TARGET" ]] || die "empty target"
  [[ "$TARGET" != "/" ]] || die "refusing filesystem root"
  [[ "$TARGET" != "$HOME" ]] || die "refusing \$HOME itself"

  if [[ "$TARGET" == "$ROOT" || "$TARGET" == "$ROOT"/* ]]; then
    die "refusing to install into source tree (${TARGET})"
  fi

  home_resolved="$(resolve_path "$HOME")"
  if [[ "$TARGET" != "$home_resolved" && "$TARGET" != "$home_resolved"/* ]]; then
    if is_forbidden_prefix "$TARGET"; then
      die "refusing system path: ${TARGET}"
    fi
    if [[ $ALLOW_OUTSIDE_HOME -ne 1 ]]; then
      die "target outside \$HOME (${TARGET}); use --allow-outside-home if intentional"
    fi
    warn "installing outside \$HOME: ${TARGET}"
  fi
}

validate_source() {
  log "Validating source at ${ROOT}"
  # Hermes skill runtime surface (agent contract + offline engine + PoI)
  local required=(
    "SKILL.md"
    "VERSION"
    "QUICKSTART.md"
    "install.sh"
    "scripts/sigil_forge.py"
    "scripts/construct.py"
    "scripts/verify.py"
    "scripts/forge_core.py"
    "scripts/intent_capsule.py"
    "scripts/commitment.py"
    "scripts/crypto_domains.py"
    "scripts/stego_envelope.py"
    "scripts/inspect_artifact.py"
    "scripts/validate_hermes_skill.py"
    "scripts/proofs/__init__.py"
    "scripts/proofs/registry.py"
    "scripts/proofs/zk_commit.py"
    "scripts/proofs/risc0_provider.py"
    "scripts/wizard.py"
    "references/hermes-runtime-contract.md"
    "references/proof-of-intent.md"
    "schemas/forge-packet.schema.json"
    "schemas/construction-result.schema.json"
    "schemas/channel-manifest.schema.json"
    "schemas/intent-capsule.schema.json"
    "schemas/artifact-root.schema.json"
    "schemas/forge-manifest.schema.json"
    "schemas/proof-manifest.schema.json"
  )
  local f
  for f in "${required[@]}"; do
    [[ -f "${ROOT}/${f}" ]] || die "missing required file: ${f}"
  done
  python3 -c "import ast, pathlib; ast.parse(pathlib.Path(r'''${ROOT}/scripts/sigil_forge.py''').read_text())" \
    || die "scripts/sigil_forge.py failed syntax check"
  # Frontmatter hygiene before copy (fail closed on bad skill packaging)
  if ! python3 "${ROOT}/scripts/validate_hermes_skill.py" >/dev/null; then
    die "validate_hermes_skill.py failed — fix SKILL.md frontmatter before install"
  fi
  log "Source validation OK"
}

sync_tree() {
  local dest="$1"
  log "Installing to ${dest}"
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '[dry-run] copy skill tree %q → %q\n' "$ROOT" "$dest"
    printf '[dry-run] exclude: .git out/ .venv __pycache__ .pytest_cache .superpowers docs/superpowers .worktrees *.pyc\n'
    return 0
  fi
  mkdir -p "$dest"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '.git' \
      --exclude '.git/' \
      --exclude 'out' \
      --exclude 'out/' \
      --exclude '.venv' \
      --exclude '__pycache__' \
      --exclude '.pytest_cache' \
      --exclude '.superpowers' \
      --exclude '*.pyc' \
      --exclude '.worktrees' \
      --exclude 'docs/superpowers' \
      --exclude 'docs/superpowers/' \
      "${ROOT}/" "${dest}/"
  else
    tar -C "${ROOT}" \
      --exclude '.git' \
      --exclude 'out' \
      --exclude '.venv' \
      --exclude '__pycache__' \
      --exclude '.pytest_cache' \
      --exclude '.superpowers' \
      --exclude '.worktrees' \
      --exclude 'docs/superpowers' \
      -cf - . | tar -C "${dest}" -xf -
  fi
  chmod +x "${dest}/install.sh" 2>/dev/null || true
  chmod +x "${dest}/scripts/sigil_forge.py" 2>/dev/null || true
  if [[ -e "${dest}/.git" ]]; then
    rm -rf "${dest}/.git"
  fi
}

post_check() {
  local dest="$1"
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '[dry-run] python3 %q/scripts/validate_hermes_skill.py\n' "$dest"
    printf '[dry-run] HERMES_SKILL_DIR=%q python3 %q/scripts/sigil_forge.py check\n' "$dest" "$dest"
    return 0
  fi
  log "Post-install Hermes frontmatter check"
  python3 "${dest}/scripts/validate_hermes_skill.py" \
    || die "post-install validate_hermes_skill failed"
  log "Post-install engine check"
  # Resolve skill root from install path (not the clone cwd)
  HERMES_SKILL_DIR="${dest}" python3 "${dest}/scripts/sigil_forge.py" check \
    || die "post-install check failed: HERMES_SKILL_DIR=${dest} python3 ${dest}/scripts/sigil_forge.py check"
  log "Post-install check OK"
}

validate_source
validate_target

if [[ $DRY_RUN -eq 1 ]]; then
  log "DRY RUN: would install Sigil-Forge v${VERSION} → ${TARGET}"
  sync_tree "$TARGET"
  post_check "$TARGET"
  exit 0
fi

python3 "${ROOT}/scripts/install_transaction.py" "$ROOT" "$TARGET" sigil-forge

echo ""
log "Sigil-Forge v${VERSION} installed → ${TARGET}"
echo ""
echo "Next:"
echo "  export HERMES_SKILL_DIR=\"${TARGET}\""
echo "  python3 \"\$HERMES_SKILL_DIR/scripts/sigil_forge.py\" check"
echo "  python3 \"\$HERMES_SKILL_DIR/scripts/sigil_forge.py\" construct \\"
echo "    --intent \"I maintain calm focus\" --out out/sigil-forge"
echo "  # Reload Hermes skills if the agent is already running"
echo ""
