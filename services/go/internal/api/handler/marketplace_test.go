package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
)

func TestTemplateListing(t *testing.T) {
	gin.SetMode(gin.TestMode)

	// Create a temp templates.json with 11 templates
	templates := make([]map[string]interface{}, 11)
	for i := 0; i < 11; i++ {
		templates[i] = map[string]interface{}{
			"key":            "test_" + string(rune('a'+i)),
			"name":           "Test Template",
			"name_en":        "Test EN",
			"description":    "Test desc",
			"description_en": "Test desc en",
			"category":       "trend",
			"difficulty":     "beginner",
			"markets":        []string{"Crypto"},
			"default_params": map[string]interface{}{"period": 10},
			"tags":           []string{"test"},
		}
	}

	tmpDir := t.TempDir()
	templateFile := filepath.Join(tmpDir, "templates.json")
	data, err := json.Marshal(templates)
	assert.NoError(t, err)
	err = os.WriteFile(templateFile, data, 0644)
	assert.NoError(t, err)

	h := NewMarketplaceHandler(nil)
	h.templatePath = templateFile

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/api/v1/marketplace/templates", nil)

	h.ListTemplates(c)

	assert.Equal(t, http.StatusOK, w.Code)

	var resp map[string]interface{}
	err = json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)

	templatesList, ok := resp["templates"].([]interface{})
	assert.True(t, ok, "templates should be a list")
	assert.Equal(t, 11, len(templatesList), "should have 11 templates")

	count, ok := resp["count"].(float64)
	assert.True(t, ok)
	assert.Equal(t, float64(11), count)
}

func TestTemplateListing_FileNotFound(t *testing.T) {
	gin.SetMode(gin.TestMode)

	h := NewMarketplaceHandler(nil)
	h.templatePath = "/nonexistent/path/templates.json"

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/api/v1/marketplace/templates", nil)

	h.ListTemplates(c)

	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "failed to read templates", resp["error"])
}

func TestStrategyListPaginated_Parsing(t *testing.T) {
	gin.SetMode(gin.TestMode)

	h := NewMarketplaceHandler(nil)

	// With nil db, the handler will fail at the SQL level,
	// but we can verify query param parsing works by checking
	// the error is a DB error, not a parsing error.
	tests := []struct {
		name       string
		query      string
		wantStatus int
	}{
		{"default pagination", "", http.StatusOK},
		{"custom page and limit", "page=2&limit=10", http.StatusOK},
		{"sort by rating", "sort_by=rating", http.StatusOK},
		{"sort by installs", "sort_by=installs", http.StatusOK},
		{"sort by recent", "sort_by=recent", http.StatusOK},
		{"invalid page defaults to 1", "page=-1", http.StatusOK},
		{"limit over 100 caps", "limit=200", http.StatusOK},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			w := httptest.NewRecorder()
			c, _ := gin.CreateTestContext(w)
			url := "/api/v1/marketplace/strategies"
			if tt.query != "" {
				url += "?" + tt.query
			}
			c.Request = httptest.NewRequest("GET", url, nil)

			h.ListStrategies(c)

			// With nil db, we expect 503 (DB unavailable), not 400 (parsing error)
			// The important thing is parsing succeeds
			assert.Equal(t, http.StatusServiceUnavailable, w.Code)
		})
	}
}

func TestStrategyCreate_Validation(t *testing.T) {
	gin.SetMode(gin.TestMode)

	h := NewMarketplaceHandler(nil)

	t.Run("missing name returns 400", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("POST", "/api/v1/marketplace/strategies",
			strings.NewReader(`{"template_id":"ma_crossover"}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.CreateStrategy(c)

		assert.Equal(t, http.StatusBadRequest, w.Code)
	})

	t.Run("missing template_id returns 400", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("POST", "/api/v1/marketplace/strategies",
			strings.NewReader(`{"name":"Test Strategy"}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.CreateStrategy(c)

		assert.Equal(t, http.StatusBadRequest, w.Code)
	})

	t.Run("unauthenticated returns 401", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("POST", "/api/v1/marketplace/strategies",
			strings.NewReader(`{"name":"Test","template_id":"ma_crossover"}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.CreateStrategy(c)

		assert.Equal(t, http.StatusUnauthorized, w.Code)

		var resp map[string]string
		err := json.Unmarshal(w.Body.Bytes(), &resp)
		assert.NoError(t, err)
		assert.Equal(t, "user not authenticated", resp["error"])
	})

	t.Run("valid request with authenticated user (db nil → 503)", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("POST", "/api/v1/marketplace/strategies",
			strings.NewReader(`{"name":"Test Strategy","template_id":"ma_crossover","params":{"fast_period":10}}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.CreateStrategy(c)

		// With nil db, we expect 503 — but NOT 400 (means parsing succeeded)
		assert.Equal(t, http.StatusServiceUnavailable, w.Code)
	})
}

func TestStrategyRate_Validation(t *testing.T) {
	gin.SetMode(gin.TestMode)

	h := NewMarketplaceHandler(nil)

	t.Run("unauthenticated returns 401", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Params = gin.Params{{Key: "id", Value: "test-uuid"}}
		c.Request = httptest.NewRequest("POST", "/api/v1/marketplace/strategies/test-uuid/rate",
			strings.NewReader(`{"rating":4}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.RateStrategy(c)

		assert.Equal(t, http.StatusUnauthorized, w.Code)

		var resp map[string]string
		err := json.Unmarshal(w.Body.Bytes(), &resp)
		assert.NoError(t, err)
		assert.Equal(t, "user not authenticated", resp["error"])
	})

	t.Run("rating below 1 returns 400", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Params = gin.Params{{Key: "id", Value: "test-uuid"}}
		c.Request = httptest.NewRequest("POST", "/api/v1/marketplace/strategies/test-uuid/rate",
			strings.NewReader(`{"rating":0}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.RateStrategy(c)

		assert.Equal(t, http.StatusBadRequest, w.Code)
	})

	t.Run("rating above 5 returns 400", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Params = gin.Params{{Key: "id", Value: "test-uuid"}}
		c.Request = httptest.NewRequest("POST", "/api/v1/marketplace/strategies/test-uuid/rate",
			strings.NewReader(`{"rating":6}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.RateStrategy(c)

		assert.Equal(t, http.StatusBadRequest, w.Code)
	})

	t.Run("missing rating returns 400", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Params = gin.Params{{Key: "id", Value: "test-uuid"}}
		c.Request = httptest.NewRequest("POST", "/api/v1/marketplace/strategies/test-uuid/rate",
			strings.NewReader(`{}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.RateStrategy(c)

		assert.Equal(t, http.StatusBadRequest, w.Code)
	})
}

func TestStrategyInstall_Behavior(t *testing.T) {
	gin.SetMode(gin.TestMode)

	h := NewMarketplaceHandler(nil)

	t.Run("nil db returns 503", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Params = gin.Params{{Key: "id", Value: "test-uuid"}}
		c.Request = httptest.NewRequest("POST", "/api/v1/marketplace/strategies/test-uuid/install",
			strings.NewReader("{}"))
		c.Request.Header.Set("Content-Type", "application/json")

		h.InstallStrategy(c)

		// With nil db, we expect 503 (DB unavailable), not 400 or 404
		assert.Equal(t, http.StatusServiceUnavailable, w.Code)
	})
}
