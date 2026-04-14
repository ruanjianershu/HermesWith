#!/bin/bash
# Prepare vendor/hermes-agent for Docker build
# Docker cannot COPY symlinks that point outside build context,
# so we copy the real files into vendor/hermes-agent-copy/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SOURCE="$PROJECT_DIR/vendor/hermes-agent"
DEST="$PROJECT_DIR/vendor/hermes-agent-copy"

# Resolve symlink to real path
REAL_SOURCE="$(readlink -f "$SOURCE" 2>/dev/null || realpath "$SOURCE" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$SOURCE")"

echo "Copying Hermes agent from $REAL_SOURCE to $DEST..."
rm -rf "$DEST"
mkdir -p "$DEST"
rsync -a --exclude='.git' "$REAL_SOURCE/" "$DEST/"
echo "Done."
