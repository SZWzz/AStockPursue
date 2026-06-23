package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
)

func TestNewAuthHandler_NoHardcodedAdmin(t *testing.T) {
	// Without ADMIN_PASSWORD, no admin should exist
	os.Unsetenv("ADMIN_PASSWORD")
	h := NewAuthHandler(nil)

	h.mu.RLock()
	_, exists := h.users["admin"]
	h.mu.RUnlock()

	assert.False(t, exists, "admin user should not exist without ADMIN_PASSWORD env var")
}

func TestNewAuthHandler_AdminFromEnv(t *testing.T) {
	os.Setenv("ADMIN_PASSWORD", "secure-admin-pass-123")
	defer os.Unsetenv("ADMIN_PASSWORD")

	h := NewAuthHandler(nil)

	h.mu.RLock()
	admin, exists := h.users["admin"]
	h.mu.RUnlock()

	assert.True(t, exists, "admin user should exist when ADMIN_PASSWORD is set")
	assert.True(t, verifyPassword("secure-admin-pass-123", admin.Password), "admin password hash does not match")
}

func TestAdminSetup_Success(t *testing.T) {
	os.Unsetenv("ADMIN_PASSWORD")
	gin.SetMode(gin.TestMode)

	h := NewAuthHandler(nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("POST", "/api/v1/admin/setup",
		strings.NewReader(`{"password":"admin-setup-pass-123"}`))
	c.Request.Header.Set("Content-Type", "application/json")

	h.AdminSetup(c)

	assert.Equal(t, http.StatusCreated, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "admin_created", resp["status"])

	// Verify admin now exists in memory
	h.mu.RLock()
	admin, exists := h.users["admin"]
	h.mu.RUnlock()
	assert.True(t, exists)
	assert.True(t, verifyPassword("admin-setup-pass-123", admin.Password))
}

func TestAdminSetup_Duplicate(t *testing.T) {
	os.Unsetenv("ADMIN_PASSWORD")
	gin.SetMode(gin.TestMode)

	h := NewAuthHandler(nil)

	// First setup should succeed
	w1 := httptest.NewRecorder()
	c1, _ := gin.CreateTestContext(w1)
	c1.Request = httptest.NewRequest("POST", "/api/v1/admin/setup",
		strings.NewReader(`{"password":"admin-setup-pass-123"}`))
	c1.Request.Header.Set("Content-Type", "application/json")

	h.AdminSetup(c1)

	assert.Equal(t, http.StatusCreated, w1.Code)

	// Second setup should fail with conflict
	w2 := httptest.NewRecorder()
	c2, _ := gin.CreateTestContext(w2)
	c2.Request = httptest.NewRequest("POST", "/api/v1/admin/setup",
		strings.NewReader(`{"password":"another-password"}`))
	c2.Request.Header.Set("Content-Type", "application/json")

	h.AdminSetup(c2)

	assert.Equal(t, http.StatusConflict, w2.Code)

	var resp map[string]string
	err := json.Unmarshal(w2.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "admin user already exists", resp["error"])
}

func TestAdminSetup_InvalidPassword(t *testing.T) {
	os.Unsetenv("ADMIN_PASSWORD")
	gin.SetMode(gin.TestMode)

	h := NewAuthHandler(nil)

	// Password too short (min=8)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("POST", "/api/v1/admin/setup",
		strings.NewReader(`{"password":"short"}`))
	c.Request.Header.Set("Content-Type", "application/json")

	h.AdminSetup(c)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestAdminSetup_EndpointResponse(t *testing.T) {
	os.Unsetenv("ADMIN_PASSWORD")
	gin.SetMode(gin.TestMode)

	h := NewAuthHandler(nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("POST", "/api/v1/admin/setup",
		strings.NewReader(`{"password":"response-test-pass"}`))
	c.Request.Header.Set("Content-Type", "application/json")

	h.AdminSetup(c)

	assert.Equal(t, http.StatusCreated, w.Code)
	assert.Contains(t, w.Header().Get("Content-Type"), "application/json")

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "admin_created", resp["status"])
	// Response must NOT contain the password or any sensitive data
	bodyStr := w.Body.String()
	assert.NotContains(t, bodyStr, "response-test-pass")
	assert.NotContains(t, bodyStr, "password")
}

func TestAdminSetup_MissingBody(t *testing.T) {
	os.Unsetenv("ADMIN_PASSWORD")
	gin.SetMode(gin.TestMode)

	h := NewAuthHandler(nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("POST", "/api/v1/admin/setup", nil)
	c.Request.Header.Set("Content-Type", "application/json")

	h.AdminSetup(c)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestUsernameToID_Deterministic(t *testing.T) {
	id1 := usernameToID("admin")
	id2 := usernameToID("admin")
	if id1 != id2 {
		t.Errorf("usernameToID should be deterministic: got %d and %d", id1, id2)
	}
}

func TestUsernameToID_DifferentUsers(t *testing.T) {
	id1 := usernameToID("admin")
	id2 := usernameToID("user123")
	if id1 == id2 {
		t.Errorf("different usernames should produce different IDs: both got %d", id1)
	}
}

func TestUsernameToID_NonZero(t *testing.T) {
	id := usernameToID("admin")
	if id == 0 {
		t.Error("usernameToID should return non-zero for any username")
	}
}

func TestGenerateToken_UserIDIsNumeric(t *testing.T) {
	oldSecret := jwtSecret
	jwtSecret = []byte("test-secret-key-for-unit-tests")
	defer func() { jwtSecret = oldSecret }()

	token, err := generateToken("testuser")
	if err != nil {
		t.Fatalf("generateToken failed: %v", err)
	}
	if token == "" {
		t.Fatal("expected non-empty token")
	}

	username, userID, err := ValidateTokenWithID(token)
	if err != nil {
		t.Fatalf("ValidateTokenWithID failed: %v", err)
	}
	if username != "testuser" {
		t.Errorf("expected username 'testuser', got %q", username)
	}
	if userID == 0 {
		t.Error("expected non-zero userID from token")
	}
}
