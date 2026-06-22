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
func Auth() gin.HandlerFunc {
	apiKey := os.Getenv("API_KEY")

	return func(c *gin.Context) {
		// API key mode: if API_KEY env is set, require matching header
		if apiKey != "" {
			if c.GetHeader("X-API-Key") == apiKey {
				c.Next()
				return
			}
		}

		// JWT Bearer token mode
		authHeader := c.GetHeader("Authorization")
		if strings.HasPrefix(authHeader, "Bearer ") {
			tokenStr := strings.TrimPrefix(authHeader, "Bearer ")
			username, userID, err := handler.ValidateTokenWithID(tokenStr)
			if err == nil {
				c.Set("username", username)
				c.Set("user_id", userID)
				c.Next()
				return
			}
		}

		// If API_KEY is set and neither method matched, reject
		if apiKey != "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
			return
		}

		// No auth configured — allow all
		c.Next()
	}
}
