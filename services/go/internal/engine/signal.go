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
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
)

type SignalAdapter struct {
	address string
	connMgr *grpcpkg.ConnManager
	timeout time.Duration
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
		dialOpt = grpc.WithTransportCredentials(credentials.NewClientTLSFromCert(nil, ""))
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
