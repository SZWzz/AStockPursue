"""Trading execution — migrated to Go.

All trading logic (engine, pipeline, risk, broker, signal) has been
migrated to Go (services/go/internal/engine/, broker/, market/feed/).

This package is retained as a stub for any remaining Python consumers
that import through this namespace. See TODO(P6) markers for remaining
migration work.
"""

# TODO(P6): All trading modules migrated to Go — delete this package
# once remaining Python consumers (workflow nodes, live_bridge) are
# updated to use Go gRPC services.
