#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$ROOT/VERSION"
PKG_JSON="$ROOT/frontend/package.json"
CHANGELOG="$ROOT/CHANGELOG.md"
VERSION_TAG_PREFIX="v"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <new-version>"
    echo "Example: $0 2026.5.27"
    exit 1
fi

NEW_VERSION="$1"
OLD_VERSION="$(cat "$VERSION_FILE")"

echo "Bumping version: $OLD_VERSION → $NEW_VERSION"

# 1. Update VERSION file
echo -n "$NEW_VERSION" > "$VERSION_FILE"
echo "  ✓ VERSION updated"

# 2. Update frontend package.json
if [ -f "$PKG_JSON" ]; then
    if command -v python3 &>/dev/null; then
        python3 -c "
import json, sys
with open('$PKG_JSON') as f:
    pkg = json.load(f)
pkg['version'] = '$NEW_VERSION'
with open('$PKG_JSON', 'w') as f:
    json.dump(pkg, f, indent=2)
    f.write('\n')
"
        echo "  ✓ frontend/package.json updated"
    else
        echo "  ⚠ python3 not found — skip package.json update"
    fi
fi

# 3. Add CHANGELOG section for new version
if [ -f "$CHANGELOG" ]; then
    TODAY="$(date +%Y.%-m.%-d 2>/dev/null || date +%Y.%m.%d)"
    sed -i '' "1s/^# Changelog/# Changelog\n\n## $TODAY\n\n(待填写)\n/" "$CHANGELOG"
    echo "  ✓ CHANGELOG date section added ($TODAY)"
fi

echo ""
echo "Done. Next steps:"
echo "  1. Edit $CHANGELOG to fill in the $NEW_VERSION section"
echo "  2. git add -A && git commit -m \"chore: bump to $NEW_VERSION\""
echo "  3. git tag ${VERSION_TAG_PREFIX}${NEW_VERSION}"
echo "  4. git push && git push --tags"
