package grpc

import (
	"context"
	"fmt"
	"log"
	"math"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health/grpc_health_v1"
)

type ConnManager struct {
	addr           string
	connectTimeout time.Duration
	conn           *grpc.ClientConn
	mu             sync.RWMutex
	maxBackoff     time.Duration
}

func NewConnManager(addr string, connectTimeout time.Duration) *ConnManager {
	return &ConnManager{
		addr:           addr,
		connectTimeout: connectTimeout,
		maxBackoff:     30 * time.Second,
	}
}

func (m *ConnManager) Connect(ctx context.Context) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	ctx, cancel := context.WithTimeout(ctx, m.connectTimeout)
	defer cancel()

	conn, err := grpc.DialContext(ctx, m.addr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	)
	if err != nil {
		return fmt.Errorf("grpc dial %s: %w", m.addr, err)
	}
	m.conn = conn
	log.Printf("gRPC: connected to %s", m.addr)
	return nil
}

func (m *ConnManager) reconnect() {
	bo := 1 * time.Second
	for {
		log.Printf("gRPC: attempting reconnect to %s (backoff %v)", m.addr, bo)
		if err := m.Connect(context.Background()); err == nil {
			return
		}
		time.Sleep(bo)
		bo = time.Duration(math.Min(float64(bo*2), float64(m.maxBackoff)))
	}
}

func (m *ConnManager) StartHealthCheck(ctx context.Context) {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	failCount := 0
	const maxFailBeforeReconnect = 3

	for {
		select {
		case <-ctx.Done():
			log.Printf("gRPC: health check stopped")
			return
		case <-ticker.C:
			m.mu.RLock()
			conn := m.conn
			m.mu.RUnlock()

			if conn == nil {
				go m.reconnect()
				continue
			}

			healthClient := grpc_health_v1.NewHealthClient(conn)
			hcCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
			resp, err := healthClient.Check(hcCtx, &grpc_health_v1.HealthCheckRequest{})
			cancel()

			if err != nil || resp.GetStatus() != grpc_health_v1.HealthCheckResponse_SERVING {
				failCount++
				log.Printf("gRPC: health check fail %d/3", failCount)
				if failCount >= maxFailBeforeReconnect {
					log.Printf("gRPC: health check failed %d times, triggering reconnect", failCount)
					failCount = 0
					m.mu.Lock()
					if m.conn != nil {
						m.conn.Close()
						m.conn = nil
					}
					m.mu.Unlock()
					go m.reconnect()
				}
			} else {
				failCount = 0
			}
		}
	}
}

func (m *ConnManager) GetConn() *grpc.ClientConn {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.conn
}
