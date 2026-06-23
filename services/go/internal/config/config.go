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
}

const (
	defaultDB    = "postgres://postgres:postgres@localhost:5432/astockpursue?sslmode=disable"
	defaultRedis = "redis://localhost:6379/0"
	defaultPort  = "8899"
	defaultGRPC  = "8901"
	defaultDir   = "./data"
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
	}, nil
}

func getEnv(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}
