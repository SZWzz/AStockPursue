package engine

import (
	"context"
	"fmt"
	"log"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	signalv1 "github.com/astockpursue/go-core/internal/gen/signal/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type GrpcSignalAdapter struct {
	grpcAddr string
	timeout  time.Duration
	conn     *grpc.ClientConn
	client   signalv1.SignalServiceClient
}

func NewSignalAdapter(addr string, timeout time.Duration) *GrpcSignalAdapter {
	conn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Printf("signal adapter: grpc dial error: %v", err)
		return &GrpcSignalAdapter{grpcAddr: addr, timeout: timeout}
	}
	client := signalv1.NewSignalServiceClient(conn)
	return &GrpcSignalAdapter{
		grpcAddr: addr,
		timeout:  timeout,
		conn:     conn,
		client:   client,
	}
}

func (s *GrpcSignalAdapter) Close() error {
	if s.conn != nil {
		return s.conn.Close()
	}
	return nil
}

func (s *GrpcSignalAdapter) Generate(bars []interface{}, ts time.Time) (map[string]float64, error) {
	if s.client == nil {
		return nil, fmt.Errorf("signal adapter: not connected")
	}
	log.Printf("signal adapter: calling Python gRPC at %s with %d bars", s.grpcAddr, len(bars))

	pbBars := make([]*commonv1.Bar, len(bars))
	for i, b := range bars {
		bar := b.(*Bar)
		pbBars[i] = &commonv1.Bar{
			Symbol:    bar.Symbol,
			Open:      bar.Open,
			High:      bar.High,
			Low:       bar.Low,
			Close:     bar.Close,
			Volume:    bar.Volume,
			Timestamp: ts.UnixMilli(),
		}
	}

	ctx, cancel := context.WithTimeout(context.Background(), s.timeout)
	defer cancel()

	resp, err := s.client.GenerateSignals(ctx, &signalv1.SignalRequest{Bars: pbBars})
	if err != nil {
		return nil, fmt.Errorf("generate signals: %w", err)
	}

	return resp.Weights, nil
}
