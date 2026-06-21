#!/bin/bash
set -e

cd "$(dirname "$0")"

case "$1" in
    frontend)
        echo "============================================"
        echo "  AStockPursue — Frontend Dev Mode"
        echo "  Frontend (5899)"
        echo "  Press Ctrl+C to stop"
        echo "============================================"
        cd frontend
        cp middleware.ts middleware.ts.bak
        cat > middleware.ts << 'EOF'
export default function middleware() { return }
EOF
        npx next dev -p 5899
        cd ..
        mv frontend/middleware.ts.bak frontend/middleware.ts 2>/dev/null
        ;;

    backend)
        echo "============================================"
        echo "  AStockPursue — Backend Dev Mode"
        echo "  Go (8899)"
        echo "  Press Ctrl+C to stop"
        echo "============================================"
        cd services/go
        go run ./cmd/server
        ;;

    grpc)
        echo "============================================"
        echo "  AStockPursue — gRPC Dev Mode"
        echo "  Python gRPC (8902)"
        echo "  Press Ctrl+C to stop"
        echo "============================================"
        cd services/python
        python -m src.grpc.server
        ;;

    *)
        echo "============================================"
        echo "  AStockPursue — Dev Mode"
        echo "  Go (8899) + Python gRPC (8902) + Frontend (5899)"
        echo "  Press Ctrl+C to stop all"
        echo "============================================"

        # 1. Start Python gRPC server
        echo "[1/3] Starting Python gRPC server on :8902..."
        cd services/python
        python -m src.grpc.server &
        GRPC_PID=$!
        cd ../..

        # 2. Start Go backend
        echo "[2/3] Starting Go backend on :8899..."
        cd services/go
        go run ./cmd/server &
        GO_PID=$!
        cd ../..

        # 3. Start Frontend (skip auth)
        echo "[3/3] Starting Frontend on :5899 (auth bypassed)..."
        cd frontend
        # Temporarily disable auth middleware
        cp middleware.ts middleware.ts.bak
        cat > middleware.ts << 'EOF'
export default function middleware() { return }
EOF
        npx next dev -p 5899 &
        FE_PID=$!
        cd ..

        echo ""
        echo "All services started:"
        echo "  Frontend: http://localhost:5899"
        echo "  Go API:   http://localhost:8899/health"
        echo "  gRPC:     localhost:8902"
        echo ""

        # Wait for interrupt
        trap "echo 'Shutting down...'; kill $GRPC_PID $GO_PID $FE_PID 2>/dev/null; cd frontend && mv middleware.ts.bak middleware.ts 2>/dev/null; exit 0" INT TERM
        wait
        ;;
esac
