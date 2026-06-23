package config

import (
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestLoad_DevelopmentDefaults(t *testing.T) {
	os.Setenv("DEVELOPMENT", "true")
	os.Setenv("DATABASE_URL", "")
	os.Setenv("REDIS_URL", "")
	defer func() {
		os.Unsetenv("DEVELOPMENT")
		os.Unsetenv("DATABASE_URL")
		os.Unsetenv("REDIS_URL")
	}()

	cfg, err := Load()
	require.NoError(t, err, "development mode should load defaults")
	assert.NotEmpty(t, cfg.DatabaseURL)
	assert.NotEmpty(t, cfg.RedisURL)
}

func TestLoad_ProductionRequiresDB(t *testing.T) {
	os.Setenv("DEVELOPMENT", "")
	os.Setenv("DATABASE_URL", "")
	os.Setenv("REDIS_URL", "")
	defer func() {
		os.Unsetenv("DEVELOPMENT")
		os.Unsetenv("DATABASE_URL")
		os.Unsetenv("REDIS_URL")
	}()

	_, err := Load()
	assert.Error(t, err, "production without DATABASE_URL should fail")
	assert.Contains(t, err.Error(), "DATABASE_URL")
}

func TestLoad_ProductionRequiresRedis(t *testing.T) {
	os.Setenv("DEVELOPMENT", "")
	os.Setenv("DATABASE_URL", "postgres://localhost/test")
	os.Setenv("REDIS_URL", "")
	defer func() {
		os.Unsetenv("DEVELOPMENT")
		os.Unsetenv("DATABASE_URL")
		os.Unsetenv("REDIS_URL")
	}()

	_, err := Load()
	assert.Error(t, err, "production without REDIS_URL should fail")
	assert.Contains(t, err.Error(), "REDIS_URL")
}

func TestLoad_EnvOverrides(t *testing.T) {
	os.Setenv("DEVELOPMENT", "true")
	os.Setenv("DATABASE_URL", "postgres://custom:5432/mydb")
	os.Setenv("REDIS_URL", "redis://custom:6379")
	os.Setenv("PORT", "9999")
	defer func() {
		os.Unsetenv("DEVELOPMENT")
		os.Unsetenv("DATABASE_URL")
		os.Unsetenv("REDIS_URL")
		os.Unsetenv("PORT")
	}()

	cfg, err := Load()
	require.NoError(t, err)
	assert.Equal(t, "postgres://custom:5432/mydb", cfg.DatabaseURL)
	assert.Equal(t, "redis://custom:6379", cfg.RedisURL)
	assert.Equal(t, "9999", cfg.Port)
}

func TestLoad_URLDefaultsInDev(t *testing.T) {
	os.Setenv("DEVELOPMENT", "true")
	os.Setenv("DATABASE_URL", "postgres://localhost/test")
	os.Setenv("REDIS_URL", "redis://localhost/0")
	defer func() {
		os.Unsetenv("DEVELOPMENT")
		os.Unsetenv("DATABASE_URL")
		os.Unsetenv("REDIS_URL")
	}()

	cfg, err := Load()
	require.NoError(t, err)
	assert.NotEmpty(t, cfg.BinanceWSURL)
	assert.NotEmpty(t, cfg.OKXWSURL)
	assert.NotEmpty(t, cfg.BinanceAPIURL)

	err = cfg.Validate()
	assert.NoError(t, err, "default URLs should pass validation")
}
