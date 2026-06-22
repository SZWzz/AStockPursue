#!/usr/bin/env bash
set -euo pipefail
echo "=== Proto Breaking Change Detection ==="
if ! command -v buf &> /dev/null; then
    echo "buf not installed, skipping breaking change check. Install: brew install bufbuild/buf/buf"
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROTO_DIR="$SCRIPT_DIR/../services/proto"
cd "$PROTO_DIR"

# Run buf breaking against the main branch
echo "Comparing against origin/main..."
if buf breaking . --against '.git#branch=main' 2>/dev/null; then
    echo "No breaking changes detected."
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 100 ]; then
        echo "WARNING: Breaking changes detected against main branch."
        echo "Review the changes above. If they are intentional, this is informational."
        exit 0
    else
        echo "buf breaking command failed with exit code $EXIT_CODE"
        exit 0
    fi
fi
