package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func newTestArenaHandler() *ArenaHandler {
	arenaEngine := engine.NewArenaEngine(nil, engine.DefaultArenaConfig())
	return NewArenaHandler(nil, arenaEngine)
}

func TestArenaSubmit_RequiresAuth(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestArenaHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("POST", "/api/v1/arena/submit", nil)

	h.Submit(c)

	assert.Equal(t, http.StatusUnauthorized, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)
	assert.Equal(t, "authentication required", resp["error"])
}

func TestArenaSubmit_Validation(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestArenaHandler()

	t.Run("missing strategy_name returns 400", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("POST", "/api/v1/arena/submit",
			strings.NewReader(`{"strategy_code":"print(1)"}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.Submit(c)

		assert.Equal(t, http.StatusBadRequest, w.Code)
	})

	t.Run("missing strategy_code returns 400", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("POST", "/api/v1/arena/submit",
			strings.NewReader(`{"strategy_name":"Test Strategy"}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.Submit(c)

		assert.Equal(t, http.StatusBadRequest, w.Code)
	})

	t.Run("empty body returns 400", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("POST", "/api/v1/arena/submit",
			strings.NewReader(`{}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.Submit(c)

		assert.Equal(t, http.StatusBadRequest, w.Code)
	})
}

func TestArenaSubmit_ValidationPassesThenDBUnavailable(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestArenaHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("user_id", 1)
	c.Request = httptest.NewRequest("POST", "/api/v1/arena/submit",
		strings.NewReader(`{"strategy_name":"Test","strategy_code":"print(1)"}`))
	c.Request.Header.Set("Content-Type", "application/json")

	h.Submit(c)

	// With nil db, we expect 503 (DB unavailable), not 400 (parsing passed)
	assert.Equal(t, http.StatusServiceUnavailable, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)
	assert.Equal(t, "database unavailable", resp["error"])
}

func TestArenaListSubmissions_RequiresAuth(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestArenaHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/api/v1/arena/submissions", nil)

	h.ListSubmissions(c)

	assert.Equal(t, http.StatusUnauthorized, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)
	assert.Equal(t, "authentication required", resp["error"])
}

func TestArenaListSubmissions_NilDBReturnsError(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestArenaHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("user_id", 1)
	c.Request = httptest.NewRequest("GET", "/api/v1/arena/submissions", nil)

	h.ListSubmissions(c)

	// Nil db → query fails with internal error
	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)
	assert.Equal(t, "failed to query submissions", resp["error"])
}

func TestArenaRankings_NilDBReturnsEmpty(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestArenaHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/api/v1/arena/rankings", nil)

	h.Rankings(c)

	// Rankings is public (no auth required), nil db → query fails → empty array
	assert.Equal(t, http.StatusOK, w.Code)

	var resp map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)

	rankings, ok := resp["rankings"].([]interface{})
	assert.True(t, ok, "rankings should be an array")
	assert.Equal(t, 0, len(rankings))
}

func TestArenaRankings_AcceptsWeekFilter(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestArenaHandler()

	t.Run("with week filter", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/api/v1/arena/rankings?week=2025-W01", nil)

		h.Rankings(c)

		// Even with week filter, nil db returns empty array
		assert.Equal(t, http.StatusOK, w.Code)

		var resp map[string]interface{}
		err := json.Unmarshal(w.Body.Bytes(), &resp)
		require.NoError(t, err)

		rankings, ok := resp["rankings"].([]interface{})
		assert.True(t, ok, "rankings should be an array")
		assert.Equal(t, 0, len(rankings))
	})

	t.Run("without week filter", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/api/v1/arena/rankings", nil)

		h.Rankings(c)

		assert.Equal(t, http.StatusOK, w.Code)

		var resp map[string]interface{}
		err := json.Unmarshal(w.Body.Bytes(), &resp)
		require.NoError(t, err)

		rankings, ok := resp["rankings"].([]interface{})
		assert.True(t, ok, "rankings should be an array")
		assert.Equal(t, 0, len(rankings))
	})
}

func TestArenaEngine_DefaultConfig(t *testing.T) {
	cfg := engine.DefaultArenaConfig()

	assert.Equal(t, "HS300", cfg.Universe)
	assert.Equal(t, 1_000_000.0, cfg.Capital)
	assert.Equal(t, 0.0003, cfg.Commission)
	assert.Equal(t, 0.001, cfg.Slippage)
	assert.Equal(t, "000300.SH", cfg.Benchmark)
	assert.False(t, cfg.Start.IsZero())
	assert.False(t, cfg.End.IsZero())
	assert.True(t, cfg.End.After(cfg.Start))
}

func TestArenaEngine_NewWithZeroCapital(t *testing.T) {
	eng := engine.NewArenaEngine(nil, engine.ArenaConfig{})
	assert.NotNil(t, eng)
}

func TestArenaEngine_DetectFutureLeak(t *testing.T) {
	eng := engine.NewArenaEngine(nil, engine.DefaultArenaConfig())

	t.Run("normal result not flagged", func(t *testing.T) {
		result := &engine.ArenaResult{WinRate: 0.58}
		assert.False(t, eng.DetectFutureLeak(result))
	})

	t.Run("suspicious result flagged", func(t *testing.T) {
		result := &engine.ArenaResult{WinRate: 0.995}
		assert.True(t, eng.DetectFutureLeak(result))
	})

	t.Run("exactly threshold", func(t *testing.T) {
		result := &engine.ArenaResult{WinRate: 0.99}
		assert.False(t, eng.DetectFutureLeak(result))
	})
}
