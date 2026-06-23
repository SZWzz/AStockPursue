package engine

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	grpcpkg "github.com/astockpursue/go-core/internal/grpc"
	signalv1 "github.com/astockpursue/go-core/internal/gen/signal/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// BarStore is an interface for loading OHLCV bars needed by the signal adapter
// when callers do not provide in-memory bars.  market.DataStore satisfies this.
type BarStore interface {
	GetLatestBars(symbols []string, start, end time.Time, freq string) (map[string]*Bar, error)
}

type SignalAdapter struct {
	address  string
	connMgr  *grpcpkg.ConnManager
	timeout  time.Duration
	barStore BarStore
}

func NewSignalAdapter(addr string, timeout time.Duration) *SignalAdapter {
	return &SignalAdapter{
		address: addr,
		timeout: timeout,
	}
}

func NewSignalAdapterFromConnMgr(mgr *grpcpkg.ConnManager, timeout time.Duration) *SignalAdapter {
	return &SignalAdapter{
		connMgr: mgr,
		timeout: timeout,
	}
}

// WithBarStore attaches a BarStore for loading bars when none are
// provided to Generate.
func (s *SignalAdapter) WithBarStore(bs BarStore) *SignalAdapter {
	s.barStore = bs
	return s
}

func (s *SignalAdapter) getClient() (signalv1.SignalServiceClient, *grpc.ClientConn, func(), error) {
	if s.connMgr != nil {
		conn := s.connMgr.GetConn()
		if conn == nil {
			return nil, nil, nil, fmt.Errorf("signal adapter: ConnManager has no active connection")
		}
		client := signalv1.NewSignalServiceClient(conn)
		return client, conn, func() {}, nil
	}

	var dialOpt grpc.DialOption
	if os.Getenv("GRPC_TLS_ENABLED") == "true" {
		creds, err := grpcpkg.LoadTLSCredentials()
		if err != nil {
			return nil, nil, nil, fmt.Errorf("signal adapter: TLS setup failed: %w", err)
		}
		dialOpt = grpc.WithTransportCredentials(creds)
	} else {
		dialOpt = grpc.WithTransportCredentials(insecure.NewCredentials())
	}
	conn, err := grpc.NewClient(s.address, dialOpt)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("signal adapter: grpc dial error: %w", err)
	}
	client := signalv1.NewSignalServiceClient(conn)
	cleanup := func() { conn.Close() }
	return client, conn, cleanup, nil
}

func (s *SignalAdapter) Generate(bars map[string]*Bar, ts time.Time) (map[string]float64, error) {
	client, _, cleanup, err := s.getClient()
	if err != nil {
		return nil, err
	}
	defer cleanup()

	// If no bars were provided and a BarStore is configured, load
	// recent bars for common symbols from the data store.
	if (bars == nil || len(bars) == 0) && s.barStore != nil {
		bars = s.loadBarsFromStore(ts)
	}

	log.Printf("signal adapter: calling Python gRPC with %d bars", len(bars))

	pbBars := make([]*commonv1.Bar, 0, len(bars))
	for _, bar := range bars {
		pbBars = append(pbBars, &commonv1.Bar{
			Symbol:    bar.Symbol,
			Open:      bar.Open,
			High:      bar.High,
			Low:       bar.Low,
			Close:     bar.Close,
			Volume:    bar.Volume,
			Timestamp: ts.UnixMilli(),
		})
	}

	ctx, cancel := context.WithTimeout(context.Background(), s.timeout)
	defer cancel()

	resp, err := client.GenerateSignals(ctx, &signalv1.SignalRequest{Bars: pbBars})
	if err != nil {
		return nil, fmt.Errorf("generate signals: %w", err)
	}

	return resp.Weights, nil
}

// loadBarsFromStore loads the most recent daily bar for each tracked
// symbol using the last 30 days as a look-back window.
func (s *SignalAdapter) loadBarsFromStore(ts time.Time) map[string]*Bar {
	start := ts.AddDate(0, 0, -30)
	candidates := []string{
		"000001.SZ", "000002.SZ", "000858.SZ",
		"600519.SH", "600036.SH", "601318.SH",
		"300750.SZ", "002594.SZ",
	}

	bars, err := s.barStore.GetLatestBars(candidates, start, ts, "1d")
	if err != nil || len(bars) == 0 {
		log.Printf("signal adapter: no bars loaded from store: %v", err)
		return make(map[string]*Bar)
	}

	log.Printf("signal adapter: loaded %d bar(s) from bar store for gRPC call", len(bars))
	return bars
}
