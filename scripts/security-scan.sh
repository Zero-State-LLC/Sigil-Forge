#!/usr/bin/env bash
#
# Security scan — run this locally, exactly as CI runs it.
#
#   ./scripts/security-scan.sh                 # scan, fail on findings
#   REPORT_ONLY=1 ./scripts/security-scan.sh   # scan, always exit 0
#
# CodeQL is licensed for open source only, so these private repos use
# permissively-licensed scanners instead. Nothing here uploads source code:
# gitleaks and bandit are entirely local, osv-scanner sends package names and
# versions, semgrep downloads rules and runs with metrics disabled.
#
# Tools are cached outside the repo, so the working tree stays clean.

set -euo pipefail

GITLEAKS_VERSION="${GITLEAKS_VERSION:-8.30.1}"
OSV_VERSION="${OSV_VERSION:-2.5.0}"
REPORT_ONLY="${REPORT_ONLY:-0}"

ROOT="$(git rev-parse --show-toplevel)"
TOOLDIR="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/zsl-security-tools"
BIN="$TOOLDIR/bin"
VENV="$TOOLDIR/venv"

# The cache holds binaries this script executes: it must be ours and private.
file_uid() { stat -c %u "$1" 2>/dev/null || stat -f %u "$1"; }
mkdir -m 700 "$TOOLDIR" 2>/dev/null || true
if [ -L "$TOOLDIR" ] || [ ! -d "$TOOLDIR" ]; then
  echo "refusing tool cache $TOOLDIR: not a plain directory" >&2
  exit 2
fi
if [ "$(file_uid "$TOOLDIR")" != "$(id -u)" ]; then
  echo "refusing tool cache $TOOLDIR: not owned by the current user" >&2
  exit 2
fi
chmod 700 "$TOOLDIR"
mkdir -p "$BIN"
if [ -L "$BIN" ]; then
  echo "refusing tool cache $BIN: is a symlink" >&2
  exit 2
fi

failed=()
note() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
record() { failed+=("$1"); printf '\033[31mFAIL: %s\033[0m\n' "$1"; }

case "$(uname -s)" in Darwin) OS=darwin ;; *) OS=linux ;; esac
case "$(uname -m)" in arm64|aarch64) ARCH=arm64 ;; *) ARCH=amd64 ;; esac

# SHA-256 of each pinned release asset, copied from the projects' own
# checksum files (gitleaks_<ver>_checksums.txt, osv-scanner_SHA256SUMS).
# Bump these together with the version numbers above.
expected_sha256() {
  case "$1" in
    gitleaks_8.30.1_darwin_arm64.tar.gz) echo b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5 ;;
    gitleaks_8.30.1_darwin_x64.tar.gz)   echo dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709 ;;
    gitleaks_8.30.1_linux_arm64.tar.gz)  echo e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080 ;;
    gitleaks_8.30.1_linux_x64.tar.gz)    echo 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb ;;
    osv-scanner_2.5.0_darwin_amd64)      echo baef4f4a4ce2924a9241869c36d4bd9d6c04b632cae6637a0f6347ab9272eb16 ;;
    osv-scanner_2.5.0_darwin_arm64)      echo fff5a2e351b7f0a60001e87cbf862e82fb82e2792d368b533fec7a5865a73da2 ;;
    osv-scanner_2.5.0_linux_amd64)       echo edcfc41d257db36148f065055655fe3fcfc434b0b423ea67468a84c207524e0c ;;
    osv-scanner_2.5.0_linux_arm64)       echo fe152e1a546af223e6c557cc3111a8bb3e5dc02fcbf7dbe95d26567c0f0041f2 ;;
    *) echo "" ;;
  esac
}

# verify_download FILE KEY: refuse to run a binary whose hash is not pinned.
verify_download() {
  local want got
  want="$(expected_sha256 "$2")"
  if [ -z "$want" ]; then
    rm -f "$1"
    echo "no pinned checksum for $2; add it to expected_sha256 in $0" >&2
    exit 2
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    got="$(sha256sum "$1" | cut -d' ' -f1)"
  else
    got="$(shasum -a 256 "$1" | cut -d' ' -f1)"
  fi
  if [ "$got" != "$want" ]; then
    rm -f "$1"
    echo "checksum mismatch for $2: got $got, want $want" >&2
    exit 2
  fi
}

# ---------------------------------------------------------------- install ---
# The pinned hashes are re-checked on every run, not only at download time.
GL_ARCH="$ARCH"; [ "$ARCH" = amd64 ] && GL_ARCH=x64
GL_ASSET="gitleaks_${GITLEAKS_VERSION}_${OS}_${GL_ARCH}.tar.gz"
GL_TARBALL="$TOOLDIR/$GL_ASSET"
if [ ! -f "$GL_TARBALL" ]; then
  note "installing gitleaks $GITLEAKS_VERSION"
  curl -fsSL -o "$GL_TARBALL.part" \
    "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/$GL_ASSET"
  verify_download "$GL_TARBALL.part" "$GL_ASSET"
  mv "$GL_TARBALL.part" "$GL_TARBALL"
fi
verify_download "$GL_TARBALL" "$GL_ASSET"
tar xzf "$GL_TARBALL" -C "$BIN" gitleaks

OSV_KEY="osv-scanner_${OSV_VERSION}_${OS}_${ARCH}"
osv_ok() {
  [ -x "$BIN/osv-scanner" ] && [ ! -L "$BIN/osv-scanner" ] || return 1
  local want got
  want="$(expected_sha256 "$OSV_KEY")"
  if command -v sha256sum >/dev/null 2>&1; then
    got="$(sha256sum "$BIN/osv-scanner" | cut -d' ' -f1)"
  else
    got="$(shasum -a 256 "$BIN/osv-scanner" | cut -d' ' -f1)"
  fi
  [ -n "$want" ] && [ "$got" = "$want" ]
}
if ! osv_ok; then
  note "installing osv-scanner $OSV_VERSION"
  rm -f "$BIN/osv-scanner"
  curl -fsSL -o "$TOOLDIR/osv-scanner.download" \
    "https://github.com/google/osv-scanner/releases/download/v${OSV_VERSION}/osv-scanner_${OS}_${ARCH}"
  verify_download "$TOOLDIR/osv-scanner.download" "$OSV_KEY"
  chmod +x "$TOOLDIR/osv-scanner.download"
  mv "$TOOLDIR/osv-scanner.download" "$BIN/osv-scanner"
fi

has_python=0
if find "$ROOT" -name '*.py' -not -path '*/.git/*' -print -quit 2>/dev/null | grep -q .; then
  has_python=1
fi

if [ ! -x "$VENV/bin/semgrep" ]; then
  note "installing semgrep + bandit"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  # Deliberately unpinned: stale rules are worse than non-reproducible ones
  # for a security scanner.
  "$VENV/bin/pip" install --quiet semgrep bandit
fi

EXCLUDES=(--exclude=.git --exclude=build --exclude=DerivedData
          --exclude=node_modules --exclude=.venv --exclude=Pods)

# ------------------------------------------------------------------ scans ---
note "secrets (gitleaks, full history)"
GL_CONF=()
[ -f "$ROOT/.gitleaks.toml" ] && GL_CONF=(--config "$ROOT/.gitleaks.toml")
"$BIN/gitleaks" detect --source "$ROOT" "${GL_CONF[@]}" \
  --redact --no-banner || record "gitleaks: secrets detected"

BANDIT_EXCLUDE="$ROOT/.git,$ROOT/build,$ROOT/DerivedData,$ROOT/.venv,$ROOT/node_modules"

if [ "$has_python" = 1 ]; then
  # Note on flags: -l/-ll/-lll is severity LOW/MEDIUM/HIGH and above, and
  # -i/-ii/-iii is the same for confidence. So -ll -ii means MEDIUM and above,
  # NOT high -- which is why this gate first failed on repos whose worst
  # finding was medium.
  note "python SAST (bandit) — informational, medium severity and above"
  "$VENV/bin/bandit" -r "$ROOT" -ll -ii -q --exclude "$BANDIT_EXCLUDE" || true

  note "python SAST (bandit) — gate, high severity AND high confidence"
  "$VENV/bin/bandit" -r "$ROOT" -lll -iii -q --exclude "$BANDIT_EXCLUDE" \
    || record "bandit: high-severity, high-confidence python findings"
else
  note "python SAST (bandit) — no python sources, skipped"
fi

note "multi-language SAST (semgrep)"
"$VENV/bin/semgrep" scan --config=p/security-audit \
  --metrics=off --error --severity=ERROR --quiet \
  "${EXCLUDES[@]}" "$ROOT" || record "semgrep: ERROR-severity findings"

note "dependencies (osv-scanner) — advisory only"
# Never blocking: a fresh CVE in a transitive dependency should not stop an
# unrelated PR. Review these, do not gate on them.
"$BIN/osv-scanner" scan source --recursive "$ROOT" || true

# ----------------------------------------------------------------- result ---
echo
if [ ${#failed[@]} -eq 0 ]; then
  printf '\033[32mAll blocking checks passed.\033[0m\n'
  exit 0
fi
printf '\033[31m%d blocking check(s) failed:\033[0m\n' "${#failed[@]}"
printf '  - %s\n' "${failed[@]}"
[ "$REPORT_ONLY" = "1" ] && { echo "REPORT_ONLY=1 — exiting 0 anyway."; exit 0; }
exit 1
