#!/usr/bin/env bash
set -euo pipefail
echo "=== Proto Lint Check ==="
if command -v buf &> /dev/null; then
    cd "$(dirname "$0")/../services/proto"
    buf lint
    echo "Proto lint passed."
else
    echo "buf not installed, skipping lint. Install: brew install bufbuild/buf/buf"
fi
