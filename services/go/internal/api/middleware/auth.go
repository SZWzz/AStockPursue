package middleware

import (
	"net/http"
	"os"
	"strings"

	"github.com/astockpursue/go-core/internal/api/handler"
	"github.com/gin-gonic/gin"
)

// Auth provides authentication middleware supporting both:
// 1. X-API-Key header (simple API key, for dev/service-to-service)
// 2. Authorization: Bearer <jwt> (for user login tokens)
//
// All routes except /api/auth/* and /api/health require authentication.
// There is no fallthrough to anonymous access.
func Auth() gin.HandlerFunc {
	apiKey := os.Getenv("API_KEY")

	return func(c *gin.Context) {
		path := c.Request.URL.Path

		// Public routes
		if strings.HasPrefix(path, "/api/auth/") || path == "/api/health" {
			c.Next()
			return
		}

		// API key mode
		if apiKey != "" && c.GetHeader("X-API-Key") == apiKey {
			c.Set("auth_method", "apikey")
			c.Next()
			return
		}

		// JWT Bearer token mode
		authHeader := c.GetHeader("Authorization")
		if strings.HasPrefix(authHeader, "Bearer ") {
			tokenStr := strings.TrimPrefix(authHeader, "Bearer ")
			username, userID, err := handler.ValidateTokenWithID(tokenStr)
			if err == nil {
				c.Set("auth_method", "jwt")
				c.Set("username", username)
				c.Set("user_id", userID)
				c.Next()
				return
			}
		}

		c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
	}
}
