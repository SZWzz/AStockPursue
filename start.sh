#!/bin/sh
set -e

# ── MCP Server (Streamable HTTP, port 8900) ──────────────────────────
echo "[start] Launching MCP server on :8900 ..."
AStockPursue-mcp --transport streamable-http --port 8900 --host 0.0.0.0 --path /mcp &
MCP_PID=$!
echo "[start] MCP server PID: $MCP_PID"

# Clean up MCP server when the container stops
cleanup() {
    echo "[start] Shutting down MCP server (PID $MCP_PID)..."
    kill "$MCP_PID" 2>/dev/null || true
    wait "$MCP_PID" 2>/dev/null || true
    echo "[start] MCP server stopped."
    exit 0
}
trap cleanup INT TERM

# ── API Server (foreground, becomes PID 1) ─────────────────────────
echo "[start] Launching API server on :8899 ..."
exec AStockPursue serve --host 0.0.0.0 --port 8899
