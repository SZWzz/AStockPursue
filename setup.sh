#!/bin/bash
set -e

echo "============================================"
echo "  AStockPursue — First Time Setup"
echo "============================================"
echo ""

cd "$(dirname "$0")"

# ── Step 1: Create .env from template ─────────────────────────────────────

if [ -f agent/.env ]; then
    echo "[!] agent/.env already exists, skipping template copy."
    echo "    Remove it manually if you want to start fresh: rm agent/.env"
else
    cp agent/.env.example agent/.env
    echo "[✓] Created agent/.env from template"
fi

# ── Step 2: Generate secrets ──────────────────────────────────────────────

if ! grep -q "^JWT_SECRET=" agent/.env 2>/dev/null; then
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "JWT_SECRET=$JWT_SECRET" >> agent/.env
    echo "[✓] Generated JWT secret"
else
    echo "[✓] JWT secret already configured"
fi

if ! grep -q "^USER_CONFIG_ENCRYPTION_KEY=" agent/.env 2>/dev/null; then
    USER_KEY=$(python3 -c "from src.db.crypto import generate_key_b64; print(generate_key_b64())" 2>/dev/null || python3 -c "
import base64, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
key = AESGCM.generate_key(bit_length=256)
print(base64.b64encode(key).decode('ascii'))
")
    echo "USER_CONFIG_ENCRYPTION_KEY=$USER_KEY" >> agent/.env
    echo "[✓] Generated user config encryption key"
else
    echo "[✓] User config encryption key already configured"
fi

# ── Step 3: Database configuration ────────────────────────────────────────

echo ""
echo "--- PostgreSQL Configuration ---"
echo ""
read -p "Do you already have a PostgreSQL instance? [Y/n]: " HAS_PG
HAS_PG=${HAS_PG:-y}

if [ "$HAS_PG" = "n" ] || [ "$HAS_PG" = "N" ] || [ "$HAS_PG" = "no" ]; then
    echo ""
    echo "[✓] Will auto-deploy PostgreSQL via Docker."
    echo "    Database: AStockPursue | User: AStockPursue | Password: vr_pg_2026"
    echo "    (change password in docker-compose.yml after setup)"
    echo ""

    DB_HOST=postgres
    DB_PORT=5432
    DB_NAME=AStockPursue
    DB_USER=AStockPursue
    DB_PASSWORD=vr_pg_2026

    # Mark that we need the PG compose file
    USE_AUTO_PG=true
else
    echo ""
    echo "--- Existing PostgreSQL Configuration ---"
    echo "(press Enter to keep default values)"
    echo ""

    read -p "Host [localhost]: " DB_HOST
    DB_HOST=${DB_HOST:-localhost}
    read -p "Port [5432]: " DB_PORT
    DB_PORT=${DB_PORT:-5432}
    read -p "Database name [AStockPursue]: " DB_NAME
    DB_NAME=${DB_NAME:-AStockPursue}
    read -p "Username [postgres]: " DB_USER
    DB_USER=${DB_USER:-postgres}
    USE_AUTO_PG=false
fi
read -sp "Password: " DB_PASSWORD
echo ""

if [ -n "$DB_PASSWORD" ]; then
    # Generate encryption key and encrypt password
    DB_KEY=$(python3 -c "
from src.db.crypto import generate_key_b64, encrypt_password
key = generate_key_b64()
enc = encrypt_password('$DB_PASSWORD', key)
print(f'{key}|{enc}')
" 2>/dev/null)

    if [ -n "$DB_KEY" ]; then
        ENC_KEY=$(echo "$DB_KEY" | cut -d'|' -f1)
        ENC_PASS=$(echo "$DB_KEY" | cut -d'|' -f2)

        # Update .env with DB settings
        python3 -c "
import re
path = 'agent/.env'
with open(path) as f:
    content = f.read()
for old, new in [
    ('DB_HOST=localhost', 'DB_HOST=$DB_HOST'),
    ('DB_PORT=5432', 'DB_PORT=$DB_PORT'),
    ('DB_NAME=AStockPursue', 'DB_NAME=$DB_NAME'),
    ('DB_USER=postgres', 'DB_USER=$DB_USER'),
]:
    content = content.replace(old, new)
# Remove old DB key lines, add new ones
lines = [l for l in content.split('\n') if not l.startswith(('DB_PASSWORD_ENC=', 'DB_ENCRYPTION_KEY='))]
lines.append(f'DB_PASSWORD_ENC=$ENC_PASS')
lines.append(f'DB_ENCRYPTION_KEY=$ENC_KEY')
with open(path, 'w') as f:
    f.write('\n'.join(lines))
"
        echo "[✓] Database credentials encrypted and saved"
    else
        echo "[!] Encryption failed (cryptography not installed?). Saving plain text."
        python3 -c "
path = 'agent/.env'
with open(path) as f:
    content = f.read()
for old, new in [
    ('DB_HOST=localhost', 'DB_HOST=$DB_HOST'),
    ('DB_PORT=5432', 'DB_PORT=$DB_PORT'),
    ('DB_NAME=AStockPursue', 'DB_NAME=$DB_NAME'),
    ('DB_USER=postgres', 'DB_USER=$DB_USER'),
]:
    content = content.replace(old, new)
lines = [l for l in content.split('\n') if not l.startswith('DB_PASSWORD=')]
lines.append(f'DB_PASSWORD=$DB_PASSWORD')
with open(path, 'w') as f:
    f.write('\n'.join(lines))
"
    fi
else
    echo "[!] No password entered, skipping DB configuration"
fi

# ── Step 4: Done ──────────────────────────────────────────────────────────

echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
if [ "$USE_AUTO_PG" = true ]; then
    echo "  Next steps:"
    echo "    1. Review agent/.env and edit if needed"
    echo "    2. docker compose --profile pg up -d --build"
    echo "    3. Open http://localhost:8899"
    echo ""
    echo "  PostgreSQL is auto-deployed (port 5432)."
    echo "  To stop: docker compose --profile pg down"
else
    echo "  Next steps:"
    echo "    1. Review agent/.env and edit if needed"
    echo "    2. docker compose up -d --build"
    echo "    3. Open http://localhost:8899"
fi
echo ""
echo "  Admin login: admin / admin123"
echo "  ⚠ WARNING: Change the admin password immediately after first login!"
echo "  ⚠ WARNING: Default credentials are a security risk in production."
echo ""
