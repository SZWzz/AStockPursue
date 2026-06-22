package grpc

import (
	"context"
	"fmt"
	"log"
	"math"
	"os"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/connectivity"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health/grpc_health_v1"
)

type ConnManager struct {
	addr           string
	connectTimeout time.Duration
	conn           *grpc.ClientConn
	mu             sync.RWMutex
	maxBackoff     time.Duration

	reconnecting    bool
	reconnectMu     sync.Mutex
	reconnectCtx    context.Context
	reconnectCancel context.CancelFunc

	healthCancel context.CancelFunc
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

	conn, err := grpc.NewClient(m.addr,
		m.dialOpts()...,
	)
	if err != nil {
		return fmt.Errorf("grpc dial %s: %w", m.addr, err)
	}
	conn.Connect()
	for {
		state := conn.GetState()
		if state == connectivity.Ready {
			break
		}
		if !conn.WaitForStateChange(ctx, state) {
			conn.Close()
			return fmt.Errorf("gRPC connect to %s: timeout", m.addr)
		}
	}
	m.conn = conn
	log.Printf("gRPC: connected to %s", m.addr)
	return nil
}

func (m *ConnManager) reconnect() {
	m.reconnectMu.Lock()
	if m.reconnecting {
		m.reconnectMu.Unlock()
		return
	}
	m.reconnecting = true
	ctx := m.reconnectCtx
	m.reconnectMu.Unlock()

	defer func() {
		m.reconnectMu.Lock()
		m.reconnecting = false
		m.reconnectMu.Unlock()
	}()

	bo := 1 * time.Second
	for {
		select {
		case <-ctx.Done():
			return
		default:
		}
		log.Printf("gRPC: attempting reconnect to %s (backoff %v)", m.addr, bo)
		if err := m.Connect(ctx); err == nil {
			return
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(bo):
		}
		bo = time.Duration(math.Min(float64(bo*2), float64(m.maxBackoff)))
	}
}

func (m *ConnManager) StartHealthCheck(ctx context.Context) func() {
	ctx, cancel := context.WithCancel(ctx)
	m.mu.Lock()
	m.healthCancel = cancel
	m.mu.Unlock()

	go func() {
		ticker := time.NewTicker(10 * time.Second)
		defer ticker.Stop()

		m.reconnectMu.Lock()
		m.reconnectCtx, m.reconnectCancel = context.WithCancel(ctx)
		m.reconnectMu.Unlock()
		defer m.reconnectCancel()

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
					m.reconnectMu.Lock()
					reconnecting := m.reconnecting
					m.reconnectMu.Unlock()
					if !reconnecting {
						go m.reconnect()
					}
					continue
				}

				healthClient := grpc_health_v1.NewHealthClient(conn)
				hcCtx, hcCancel := context.WithTimeout(ctx, 3*time.Second)
				resp, err := healthClient.Check(hcCtx, &grpc_health_v1.HealthCheckRequest{})
				hcCancel()

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
						m.reconnectMu.Lock()
						reconnecting := m.reconnecting
						m.reconnectMu.Unlock()
						if !reconnecting {
							go m.reconnect()
						}
					}
				} else {
					failCount = 0
				}
			}
		}
	}()

	return cancel
}

func (m *ConnManager) GetConn() *grpc.ClientConn {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.conn
}

func (m *ConnManager) Close() {
	m.mu.Lock()
	if m.healthCancel != nil {
		m.healthCancel()
	}
	if m.conn != nil {
		m.conn.Close()
		m.conn = nil
	}
	m.mu.Unlock()
}

func (m *ConnManager) dialOpts() []grpc.DialOption {
	if os.Getenv("GRPC_TLS_ENABLED") == "true" {
		creds := credentials.NewClientTLSFromCert(nil, "")
		return []grpc.DialOption{grpc.WithTransportCredentials(creds)}
	}
	return []grpc.DialOption{grpc.WithTransportCredentials(insecure.NewCredentials())}
}
