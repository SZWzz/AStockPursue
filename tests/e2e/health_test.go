package e2e

import (
	"io"
	"net/http"
	"testing"
	"time"
)

const baseURL = "http://localhost:8899"

func TestHealthEndpoint(t *testing.T) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(baseURL + "/health")
	if err != nil {
		t.Skipf("server not running, skipping E2E: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", resp.StatusCode)
	}
}

func TestPingEndpoint(t *testing.T) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(baseURL + "/api/v1/system/ping")
	if err != nil {
		t.Skipf("server not running, skipping E2E: %v", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if string(body) != "pong" {
		t.Errorf("expected pong, got %s", string(body))
	}
}
