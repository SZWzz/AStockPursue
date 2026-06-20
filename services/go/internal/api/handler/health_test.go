package handler

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
)

func TestHealth(t *testing.T) {
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request, _ = http.NewRequest("GET", "/health", nil)
	h := &HealthHandler{}
	h.Health(c)
	assert.Equal(t, 200, w.Code)
	assert.True(t, strings.Contains(w.Body.String(), `"status":"ok"`))
}
