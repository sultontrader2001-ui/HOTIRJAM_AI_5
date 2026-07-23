#!/usr/bin/env bash
# Install the `hotirjam` command on macOS (symlink onto PATH).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$BIN_DIR/hotirjam"

if [[ ! -f "$SRC" ]]; then
  echo "error: launcher not found at $SRC" >&2
  exit 1
fi
chmod +x "$SRC"

# Prefer user-local bin (no sudo). Use --system for /usr/local/bin.
TARGET_DIR="${HOTIRJAM_INSTALL_BIN:-$HOME/bin}"
if [[ "${1:-}" == "--system" ]]; then
  TARGET_DIR="/usr/local/bin"
fi

mkdir -p "$TARGET_DIR"
TARGET="$TARGET_DIR/hotirjam"

ln -sfn "$SRC" "$TARGET"
chmod +x "$TARGET" 2>/dev/null || true

echo "Installed: $TARGET -> $SRC"

case ":$PATH:" in
  *":$TARGET_DIR:"*)
    echo "PATH already includes $TARGET_DIR"
    ;;
  *)
    echo
    echo "Add to your shell profile (~/.zshrc):"
    echo "  export PATH=\"$TARGET_DIR:\$PATH\""
    echo
    echo "Then:  source ~/.zshrc && hotirjam"
    ;;
esac

echo
echo "Run:  hotirjam"
