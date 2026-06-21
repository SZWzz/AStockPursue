package market

import (
	"context"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
)

// FetchRequest defines the parameters for fetching bar data from a market data source.
type FetchRequest struct {
	Symbol    string
	StartDate time.Time
	EndDate   time.Time
	Frequency string
}

// Adapter defines a unified interface for all market data sources (loaders, WebSocket
// feeds, third-party APIs, etc.). Each adapter represents a single data provider that may
// support one or more markets.
//
// Implementations must be safe for concurrent use. The Fetch method should be cancellable
// via the provided context.
//
// See also: loader.Loader (backwards-compatible alias for this interface).
type Adapter interface {
	// Name returns a human-readable identifier for this data source (e.g. "eastmoney", "binance").
	Name() string

	// Markets returns the list of market identifiers this adapter supports.
	// Examples: ["CN"], ["HK","US"], ["CN","HK","US","CRYPTO"].
	Markets() []string

	// RequiresAuth reports whether this adapter needs credentials (API key, token, etc.)
	// before it can be used. Callers should check IsAvailable before attempting a Fetch.
	RequiresAuth() bool

	// IsAvailable checks whether the adapter can serve requests right now (network reachable,
	// credentials valid, rate limits not exceeded). Implementations should perform a lightweight
	// connectivity check and return quickly.
	IsAvailable(ctx context.Context) bool

	// Fetch retrieves bar data for the given request. The context may carry a deadline or
	// cancellation signal; implementations must respect these. Returns the requested bars
	// or an error describing the failure.
	Fetch(ctx context.Context, req FetchRequest) ([]*commonv1.Bar, error)
}
