package config

import (
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

func Load() *Config {
	seedStr := getEnv("SEED_SYMBOLS", "000001.SZ,600519.SH,000300.SH,600036.SH,000858.SZ,600000.SH,601318.SH,000002.SZ,601166.SH,600276.SH,002415.SZ,601012.SH")
	seedSymbols := []string{}
	for _, s := range strings.Split(seedStr, ",") {
		if trimmed := strings.TrimSpace(s); trimmed != "" {
			seedSymbols = append(seedSymbols, trimmed)
		}
	}

	return &Config{
		Port:          getEnv("PORT", "8899"),
		DatabaseURL:   getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/astockpursue?sslmode=disable"),
		RedisURL:      getEnv("REDIS_URL", "redis://localhost:6379/0"),
		GrpcPort:      getEnv("GRPC_PORT", "8901"),
		DataDir:       getEnv("DATA_DIR", "./data"),
		DevMode:       getEnv("GO_ENV", "") == "development",
		SeedSymbols:   seedSymbols,
		EncryptionKey: getEnv("ENCRYPTION_KEY", ""),
	}
}

func getEnv(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}
