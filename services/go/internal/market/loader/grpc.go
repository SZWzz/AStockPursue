package loader

import (
	"context"
	"fmt"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	datav1 "github.com/astockpursue/go-core/internal/gen/data/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// GrpcDataLoader bridges Python-only data sources (mootdx, tushare, akshare, futu)
// to Go via the Python DataService gRPC endpoint.
type GrpcDataLoader struct {
	source string // "mootdx", "tushare", "akshare", "futu"
	name   string // display name for the loader
	addr   string // gRPC server address
	conn   *grpc.ClientConn
	client datav1.DataServiceClient
}

// NewGrpcDataLoader creates a gRPC-backed loader for a named Python data source.
func NewGrpcDataLoader(source string, addr string) *GrpcDataLoader {
	return &GrpcDataLoader{
		source: source,
		name:   "grpc-" + source,
		addr:   addr,
	}
}

func (g *GrpcDataLoader) Name() string { return g.name }

func (g *GrpcDataLoader) IsAvailable() bool {
	if g.client != nil {
		return true
	}
	conn, err := grpc.Dial(g.addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return false
	}
	g.conn = conn
	g.client = datav1.NewDataServiceClient(conn)
	return true
}

func (g *GrpcDataLoader) FetchBars(symbol string, start, end time.Time) ([]*commonv1.Bar, error) {
	if g.client == nil {
		if !g.IsAvailable() {
			return nil, fmt.Errorf("grpc data loader %s: not connected", g.source)
		}
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	resp, err := g.client.FetchBars(ctx, &datav1.FetchBarsRequest{
		Source:    g.source,
		Symbol:    symbol,
		StartDate: start.Format("2006-01-02"),
		EndDate:   end.Format("2006-01-02"),
		Frequency: "1d",
	})
	if err != nil {
		return nil, fmt.Errorf("grpc fetch %s: %w", g.source, err)
	}
	if resp.Error != "" {
		return nil, fmt.Errorf("grpc fetch %s: %s", g.source, resp.Error)
	}

	return resp.Bars, nil
}

// Default gRPC data service address (Python DataService on port 8902).
const grpcDataServiceAddr = "localhost:8902"

func init() {
	// Priority 2: mootdx — free TCP, fastest A-share source
	RegisterPriority(NewGrpcDataLoader("mootdx", grpcDataServiceAddr), 2)
	// Priority 3: tushare — needs API key, excellent coverage
	RegisterPriority(NewGrpcDataLoader("tushare", grpcDataServiceAddr), 3)
	// Priority 4: futu — needs FutuOpenD, HK + A-share
	RegisterPriority(NewGrpcDataLoader("futu", grpcDataServiceAddr), 4)
	// Priority 11: akshare — slow but multi-market, last resort
	RegisterPriority(NewGrpcDataLoader("akshare", grpcDataServiceAddr), 11)
}

func (g *GrpcDataLoader) Close() error {
	if g.conn != nil {
		return g.conn.Close()
	}
	return nil
}
