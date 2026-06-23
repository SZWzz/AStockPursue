package api

import (
	"net/http/httptest"
	"testing"
)

func TestWebSocketOriginCheck_AllowedOrigin(t *testing.T) {
	r := httptest.NewRequest("GET", "/ws", nil)
	r.Header.Set("Origin", "http://localhost:5899")
	if !upgrader.CheckOrigin(r) {
		t.Error("expected localhost:5899 to be allowed")
	}
}

func TestWebSocketOriginCheck_DisallowedOrigin(t *testing.T) {
	r := httptest.NewRequest("GET", "/ws", nil)
	r.Header.Set("Origin", "https://evil.com")
	if upgrader.CheckOrigin(r) {
		t.Error("expected evil.com to be denied")
	}
}

func TestWebSocketOriginCheck_SameOrigin(t *testing.T) {
	r := httptest.NewRequest("GET", "/ws", nil)
	// No Origin header = same-origin request
	if !upgrader.CheckOrigin(r) {
		t.Error("expected same-origin (no Origin header) to be allowed")
	}
}
