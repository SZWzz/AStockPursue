#!/bin/bash
set -e
echo "=== AStockPursue Data Initialization ==="
echo ""

# Check Python
python3 --version || { echo "Python 3 required"; exit 1; }

# Install deps
echo "Installing dependencies..."
pip install akshare pandas pyarrow tqdm -q

# Run init
echo ""
python3 scripts/init_data.py "$@"

# Verify
echo ""
python -c "import pandas as pd; from pathlib import Path; p=Path('cache/preload'); print('OK' if p.exists() else 'No data yet, run: bash scripts/init_data.sh')"

# Summary
echo ""
echo "Data files:"
ls -lh cache/preload/ 2>/dev/null || echo "  (run scripts/init_data.py first)"
echo ""
echo "=== Done! Start with: docker-compose up -d ==="
