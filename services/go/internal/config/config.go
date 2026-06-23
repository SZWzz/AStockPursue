package config

import (
	"errors"
	"os"
	"strings"
)

type Config struct {
	Port          string
	DatabaseURL   string
	RedisURL      string
	GrpcPort      string
	DataDir       string
	DevMode       bool
	SeedSymbols   []string
	EncryptionKey string
	// WebSocket and API endpoint URLs for exchange connectivity.
	BinanceWSURL  string
	OKXWSURL      string
	BinanceAPIURL string
	OKXAPIURL     string
	FutuHost      string
	FutuPort      string
}

const (
	defaultDB          = "postgres://postgres:postgres@localhost:5432/astockpursue?sslmode=disable"
	defaultRedis       = "redis://localhost:6379/0"
	defaultPort        = "8899"
	defaultGRPC        = "8901"
	defaultDir         = "./data"
	defaultBinanceWS   = "wss://fstream.binance.com/ws"
	defaultOKXWS       = "wss://ws.okx.com:8443/ws/v5/public"
	defaultBinanceAPI  = "https://fapi.binance.com"
	defaultOKXAPI      = "https://www.okx.com"
	defaultFutuHost    = "localhost"
	defaultFutuPort    = "11111"
)

func Load() (*Config, error) {
	isDev := os.Getenv("DEVELOPMENT") == "true"

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		if isDev {
			dbURL = defaultDB
		} else {
			return nil, errors.New("DATABASE_URL must be set in production")
		}
	}

	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		if isDev {
			redisURL = defaultRedis
		} else {
			return nil, errors.New("REDIS_URL must be set in production")
		}
	}

	seedStr := getEnv("SEED_SYMBOLS", "000001.SZ,600519.SH,000300.SH,600036.SH,000858.SZ,600000.SH,601318.SH,000002.SZ,601166.SH,600276.SH,002415.SZ,601012.SH")
	seedSymbols := []string{}
	for _, s := range strings.Split(seedStr, ",") {
		if trimmed := strings.TrimSpace(s); trimmed != "" {
			seedSymbols = append(seedSymbols, trimmed)
		}
	}

	return &Config{
		Port:          getEnv("PORT", defaultPort),
		DatabaseURL:   dbURL,
		RedisURL:      redisURL,
		GrpcPort:      getEnv("GRPC_PORT", defaultGRPC),
		DataDir:       getEnv("DATA_DIR", defaultDir),
		DevMode:       getEnv("GO_ENV", "") == "development",
		SeedSymbols:   seedSymbols,
		EncryptionKey: getEnv("ENCRYPTION_KEY", ""),
		BinanceWSURL:  getEnv("BINANCE_WS_URL", defaultBinanceWS),
		OKXWSURL:      getEnv("OKX_WS_URL", defaultOKXWS),
		BinanceAPIURL: getEnv("BINANCE_API_URL", defaultBinanceAPI),
		OKXAPIURL:     getEnv("OKX_API_URL", defaultOKXAPI),
		FutuHost:      getEnv("FUTU_HOST", defaultFutuHost),
		FutuPort:      getEnv("FUTU_PORT", defaultFutuPort),
	}, nil
}

// Validate checks that required URL fields are non-empty.
func (c *Config) Validate() error {
	if c.BinanceWSURL == "" {
		return errors.New("BINANCE_WS_URL must not be empty")
	}
	if c.OKXWSURL == "" {
		return errors.New("OKX_WS_URL must not be empty")
	}
	if c.BinanceAPIURL == "" {
		return errors.New("BINANCE_API_URL must not be empty")
	}
	if c.OKXAPIURL == "" {
		return errors.New("OKX_API_URL must not be empty")
	}
	if c.FutuHost == "" {
		return errors.New("FUTU_HOST must not be empty")
	}
	if c.FutuPort == "" {
		return errors.New("FUTU_PORT must not be empty")
	}
	return nil
}

func getEnv(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}
