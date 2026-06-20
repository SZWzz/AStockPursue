package middleware

import (
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
)

func Auth() gin.HandlerFunc {
	apiKey := os.Getenv("API_KEY")
	return func(c *gin.Context) {
		if apiKey == "" {
			c.Next()
			return
		}
		if c.GetHeader("X-API-Key") != apiKey {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
			return
		}
		c.Next()
	}
}
