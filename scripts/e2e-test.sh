#!/usr/bin/env bash
set -euo pipefail
echo "=== Running E2E Tests ==="
cd "$(dirname "$0")/../tests/e2e"
go test ./... -v -count=1 -timeout 60s
echo "E2E tests complete."
