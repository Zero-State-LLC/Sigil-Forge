#!/usr/bin/env bash
#
# Install the optional Noir proof toolchain (nargo + bb) for `--proof zk-knowledge`.
#
#   ./scripts/install-noir-toolchain.sh
#
# Sigil-Forge works without it. This script exists so the toolchain can be
# installed without piping a remote script into a shell: it downloads the two
# official release archives, checks each against a SHA-256 pinned below, and
# only then unpacks them. The hashes are the ones GitHub publishes for the
# release assets of noir-lang/noir v1.0.0 and AztecProtocol/aztec-packages
# v6.0.0 (the bb version Barretenberg pairs with Noir 1.0.0).
#
# Installs to the same places the upstream installers use:
#   $HOME/.nargo/bin/nargo     $HOME/.bb/bb
# The engine looks there as well as on PATH, so no shell profile is edited.
# The first proof makes bb download its reference string to $HOME/.bb-crs.

set -euo pipefail

NOIR_VERSION="1.0.0"
BB_VERSION="6.0.0"

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)
    NOIR_ASSET="noir-aarch64-apple-darwin.tar.gz"
    NOIR_SHA="ac2166fc06fe289fd2524f9eb9da228550159c976e88c1013bfc6d0e0b4a2309"
    BB_ASSET="barretenberg-arm64-darwin.tar.gz"
    BB_SHA="48bd18a7d53781a2820e7538dfd89584ca5b4d76c7908e8be4910ce994e7c35e" ;;
  Darwin-x86_64)
    NOIR_ASSET="noir-x86_64-apple-darwin.tar.gz"
    NOIR_SHA="a68f08c656d7b2e0160feee4194feea790d49e582b40b873a72dc8473d73d64f"
    BB_ASSET="barretenberg-amd64-darwin.tar.gz"
    BB_SHA="b0f872ad96ba35a57a3b8b91a7e1b8baf39dbe6e33a8a5b969e5d110638f1161" ;;
  Linux-x86_64)
    NOIR_ASSET="noir-x86_64-unknown-linux-gnu.tar.gz"
    NOIR_SHA="a62f5b44a6db8ca8f0c20f841aa788ea56776e5aaf2ebd672c02dcf397901264"
    BB_ASSET="barretenberg-amd64-linux.tar.gz"
    BB_SHA="6a310ede6457cf47e6dcf11f8d6b59dd709328c272a70c03afb1417c5a798b67" ;;
  Linux-aarch64|Linux-arm64)
    NOIR_ASSET="noir-aarch64-unknown-linux-gnu.tar.gz"
    NOIR_SHA="b4ad6521a580c576548f1fc8240d7f2b245ab569a9e8dde33ec0dd6b8cd55056"
    BB_ASSET="barretenberg-arm64-linux.tar.gz"
    BB_SHA="cbdf8cb01b80cca089b63834c543e49e65d1e4e0b969844ce7f302c3de30b432" ;;
  *)
    echo "unsupported platform: $(uname -s)-$(uname -m)" >&2
    exit 2 ;;
esac

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

fetch_verified() { # url expected-sha dest
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 -o "$3" "$1"
  local got
  got="$(sha256_of "$3")"
  if [ "$got" != "$2" ]; then
    echo "checksum mismatch for $1" >&2
    echo "  expected $2" >&2
    echo "  got      $got" >&2
    exit 1
  fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fetch_verified \
  "https://github.com/noir-lang/noir/releases/download/v${NOIR_VERSION}/${NOIR_ASSET}" \
  "$NOIR_SHA" "$TMP/noir.tar.gz"
fetch_verified \
  "https://github.com/AztecProtocol/aztec-packages/releases/download/v${BB_VERSION}/${BB_ASSET}" \
  "$BB_SHA" "$TMP/bb.tar.gz"

mkdir -p "$TMP/noir" "$TMP/bb" "$HOME/.nargo/bin" "$HOME/.bb"
tar -xzf "$TMP/noir.tar.gz" -C "$TMP/noir"
tar -xzf "$TMP/bb.tar.gz" -C "$TMP/bb"
install -m 755 "$TMP/noir/nargo" "$HOME/.nargo/bin/nargo"
install -m 755 "$TMP/bb/bb" "$HOME/.bb/bb"

"$HOME/.nargo/bin/nargo" --version | head -1
echo "bb version = $("$HOME/.bb/bb" --version)"
