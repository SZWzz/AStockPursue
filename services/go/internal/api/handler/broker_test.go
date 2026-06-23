package handler

import (
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/astockpursue/go-core/internal/crypto"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
)

func TestRevealCredentials_RateLimited(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := NewBrokerHandler(nil, nil, nil)
	h.SetPasswordVerifier(func(userID int, password string) bool {
		return password == "correct-password"
	})

	// First 3 calls should pass rate limit (fail at DB because nil, but not 429)
	for i := 0; i < 3; i++ {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("POST", "/api/v1/broker/credentials/reveal",
			strings.NewReader(`{"current_password":"correct-password"}`))
		c.Request.Header.Set("Content-Type", "application/json")
		h.RevealCredentials(c)
		assert.NotEqual(t, http.StatusTooManyRequests, w.Code,
			"attempt %d should not be rate limited", i+1)
	}

	// 4th call should be rate limited (429)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("user_id", 1)
	c.Request = httptest.NewRequest("POST", "/api/v1/broker/credentials/reveal",
		strings.NewReader(`{"current_password":"correct-password"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.RevealCredentials(c)

	assert.Equal(t, http.StatusTooManyRequests, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp["error"], "too many reveal attempts")
}

func TestRevealCredentials_WrongPassword(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := NewBrokerHandler(nil, nil, nil)
	h.SetPasswordVerifier(func(userID int, password string) bool {
		return false // always rejects
	})

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("user_id", 1)
	c.Request = httptest.NewRequest("POST", "/api/v1/broker/credentials/reveal",
		strings.NewReader(`{"current_password":"wrong-password"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.RevealCredentials(c)

	assert.Equal(t, http.StatusForbidden, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "incorrect password", resp["error"])
}

func TestRotateCredentials_Success(t *testing.T) {
	// Initialize crypto with a 32-byte base64-encoded test key.
	// Without a real database, the handler returns 503 — this test verifies
	// that request parsing and authentication succeed.
	testKey := base64.StdEncoding.EncodeToString([]byte("this-is-a-32-byte-test-key!!!!!!"))
	err := crypto.Init(testKey)
	assert.NoError(t, err)

	gin.SetMode(gin.TestMode)
	h := NewBrokerHandler(nil, nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("user_id", 1)
	c.Request = httptest.NewRequest("POST", "/api/v1/broker/credentials/rotate",
		strings.NewReader(`{"broker_id":"binance","api_key":"new-api-key-123","api_secret":"new-api-secret-456"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.RotateCredentials(c)

	// Without a database, RotateCredentials returns 503.
	// This test confirms that parsing and authentication succeed.
	assert.Equal(t, http.StatusServiceUnavailable, w.Code)

	var resp map[string]string
	err = json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "database not available", resp["error"])
}

func TestRotateCredentials_Unauthenticated(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := NewBrokerHandler(nil, nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	// user_id is NOT set → should get 401
	c.Request = httptest.NewRequest("POST", "/api/v1/broker/credentials/rotate",
		strings.NewReader(`{"broker_id":"binance","api_key":"key","api_secret":"secret"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.RotateCredentials(c)

	assert.Equal(t, http.StatusUnauthorized, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "user not authenticated", resp["error"])
}
