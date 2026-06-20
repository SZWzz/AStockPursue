package config

import "os"

type Config struct {
	Port        string
	DatabaseURL string
	RedisURL    string
	GrpcPort    string
}

func Load() *Config {
	return &Config{
		Port:        getEnv("PORT", "8899"),
		DatabaseURL: getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/astockpursue?sslmode=disable"),
		RedisURL:    getEnv("REDIS_URL", "redis://localhost:6379/0"),
		GrpcPort:    getEnv("GRPC_PORT", "8901"),
	}
}

func getEnv(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}
