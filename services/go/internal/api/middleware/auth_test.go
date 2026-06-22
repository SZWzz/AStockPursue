package middleware

import (
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/stretchr/testify/assert"
)

func setupTestRouter() *gin.Engine {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(Auth())
	router.GET("/api/v1/test", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})
	return router
}

func makeTestRequest(router *gin.Engine, method, path string, headers map[string]string) *httptest.ResponseRecorder {
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(method, path, nil)
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	router.ServeHTTP(w, req)
	return w
}

// generateTestToken creates a valid JWT token for testing.
// Requires JWT_SECRET env var to be set, or GO_ENV=development.
func generateTestToken(t *testing.T, username string) string {
	t.Helper()

	secret := os.Getenv("JWT_SECRET")
	if secret == "" {
		secret = "astockpursue-dev-secret-not-for-production"
	}

	claims := jwt.MapClaims{
		"sub":     username,
		"user_id": "1",
		"iat":     time.Now().Unix(),
		"exp":     time.Now().Add(24 * time.Hour).Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenStr, err := token.SignedString([]byte(secret))
	if err != nil {
		t.Fatalf("failed to generate test token: %v", err)
	}
	return tokenStr
}

func TestAuthPublicRoute(t *testing.T) {
	os.Setenv("API_KEY", "")
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(Auth())
	router.GET("/api/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	w := makeTestRequest(router, "GET", "/api/health", nil)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestAuthPublicRouteAuthPrefix(t *testing.T) {
	os.Setenv("API_KEY", "")
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(Auth())
	router.POST("/api/auth/login", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	w := makeTestRequest(router, "POST", "/api/auth/login", nil)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestAuthAPIKeySuccess(t *testing.T) {
	os.Setenv("API_KEY", "test-api-key-123")
	defer os.Unsetenv("API_KEY")

	router := setupTestRouter()

	w := makeTestRequest(router, "GET", "/api/v1/test", map[string]string{
		"X-API-Key": "test-api-key-123",
	})

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestAuthAPIKeyWrong(t *testing.T) {
	os.Setenv("API_KEY", "test-api-key-123")
	defer os.Unsetenv("API_KEY")

	router := setupTestRouter()

	w := makeTestRequest(router, "GET", "/api/v1/test", map[string]string{
		"X-API-Key": "wrong-key",
	})

	assert.Equal(t, http.StatusUnauthorized, w.Code)
}

func TestAuthAPIKeyMissing(t *testing.T) {
	os.Setenv("API_KEY", "")
	os.Unsetenv("JWT_SECRET")

	router := setupTestRouter()

	w := makeTestRequest(router, "GET", "/api/v1/test", nil)

	assert.Equal(t, http.StatusUnauthorized, w.Code)
}

func TestAuthJWTSuccess(t *testing.T) {
	os.Setenv("API_KEY", "")
	os.Setenv("JWT_SECRET", "test-secret")
	defer os.Unsetenv("JWT_SECRET")

	router := setupTestRouter()

	token := generateTestToken(t, "testuser")

	w := makeTestRequest(router, "GET", "/api/v1/test", map[string]string{
		"Authorization": "Bearer " + token,
	})

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestAuthJWTInvalid(t *testing.T) {
	os.Setenv("API_KEY", "")
	os.Setenv("JWT_SECRET", "test-secret")
	defer os.Unsetenv("JWT_SECRET")

	router := setupTestRouter()

	w := makeTestRequest(router, "GET", "/api/v1/test", map[string]string{
		"Authorization": "Bearer invalid.jwt.token",
	})

	assert.Equal(t, http.StatusUnauthorized, w.Code)
}

func TestAuthMissingBoth(t *testing.T) {
	os.Setenv("API_KEY", "")
	os.Unsetenv("JWT_SECRET")

	router := setupTestRouter()

	w := makeTestRequest(router, "GET", "/api/v1/test", nil)

	assert.Equal(t, http.StatusUnauthorized, w.Code)
}

func TestAuthContextValues(t *testing.T) {
	os.Setenv("API_KEY", "")
	os.Setenv("JWT_SECRET", "test-secret")
	defer os.Unsetenv("JWT_SECRET")

	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(Auth())
	router.GET("/api/v1/test", func(c *gin.Context) {
		authMethod, _ := c.Get("auth_method")
		username, _ := c.Get("username")
		userID, _ := c.Get("user_id")
		c.JSON(http.StatusOK, gin.H{
			"auth_method": authMethod,
			"username":    username,
			"user_id":     userID,
		})
	})

	token := generateTestToken(t, "testuser")

	w := makeTestRequest(router, "GET", "/api/v1/test", map[string]string{
		"Authorization": "Bearer " + token,
	})

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), `"auth_method":"jwt"`)
	assert.Contains(t, w.Body.String(), `"username":"testuser"`)
}

func TestAuthContextValuesAPIKey(t *testing.T) {
	os.Setenv("API_KEY", "test-api-key-456")
	os.Unsetenv("JWT_SECRET")
	defer os.Unsetenv("API_KEY")

	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(Auth())
	router.GET("/api/v1/test", func(c *gin.Context) {
		authMethod, _ := c.Get("auth_method")
		username, _ := c.Get("username")
		c.JSON(http.StatusOK, gin.H{
			"auth_method": authMethod,
			"username":    username,
		})
	})

	w := makeTestRequest(router, "GET", "/api/v1/test", map[string]string{
		"X-API-Key": "test-api-key-456",
	})

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), `"auth_method":"apikey"`)
}

func TestAuthAPIKeyTakesPrecedenceOverJWT(t *testing.T) {
	os.Setenv("API_KEY", "test-api-key-789")
	os.Setenv("JWT_SECRET", "test-secret")
	defer os.Unsetenv("API_KEY")
	defer os.Unsetenv("JWT_SECRET")

	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(Auth())
	router.GET("/api/v1/test", func(c *gin.Context) {
		authMethod, _ := c.Get("auth_method")
		c.JSON(http.StatusOK, gin.H{
			"auth_method": authMethod,
		})
	})

	token := generateTestToken(t, "testuser")

	// Send both API key and JWT — API key should take precedence
	w := makeTestRequest(router, "GET", "/api/v1/test", map[string]string{
		"X-API-Key":     "test-api-key-789",
		"Authorization": "Bearer " + token,
	})

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), `"auth_method":"apikey"`)
}

func TestAuthNoAuthWithoutBearerPrefix(t *testing.T) {
	os.Setenv("API_KEY", "")
	os.Setenv("JWT_SECRET", "test-secret")
	defer os.Unsetenv("JWT_SECRET")

	router := setupTestRouter()

	// Authorization header without Bearer prefix should be rejected
	w := makeTestRequest(router, "GET", "/api/v1/test", map[string]string{
		"Authorization": generateTestToken(t, "testuser"),
	})

	assert.Equal(t, http.StatusUnauthorized, w.Code)
}

func TestAuthNoAPIKeyEnvDoesNotAuth(t *testing.T) {
	os.Unsetenv("API_KEY")

	router := setupTestRouter()

	// Even with a valid-looking X-API-Key, if env API_KEY is empty, it should fail
	w := makeTestRequest(router, "GET", "/api/v1/test", map[string]string{
		"X-API-Key": "some-key",
	})

	assert.Equal(t, http.StatusUnauthorized, w.Code)
}
