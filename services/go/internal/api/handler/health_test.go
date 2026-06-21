package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestHealthFullCheckDegraded(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := NewHealthHandler(nil, nil, nil) // no dependencies → degraded

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/health", nil)

	h.FullCheck(c)

	assert.Equal(t, http.StatusOK, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)
	assert.Equal(t, "degraded", resp["status"])
	assert.Equal(t, "disconnected", resp["db"])
	assert.Equal(t, "disconnected", resp["grpc"])
	assert.Equal(t, "disconnected", resp["redis"])
}
