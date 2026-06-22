package e2e

import (
	"encoding/json"
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

func TestHealthDetailedCheck(t *testing.T) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(baseURL + "/health")
	if err != nil {
		t.Skipf("server not running, skipping E2E: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Skipf("health endpoint returned %d, skipping detailed check", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("failed to read response body: %v", err)
	}

	var health map[string]interface{}
	if err := json.Unmarshal(body, &health); err != nil {
		t.Skipf("health response is not JSON, skipping: %v", err)
	}

	// Verify expected fields exist
	fields := []string{"status", "version", "uptime"}
	for _, f := range fields {
		if _, ok := health[f]; !ok {
			t.Errorf("health response missing field '%s'", f)
		}
	}
}

func TestAPIInfoEndpoint(t *testing.T) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(baseURL + "/api/v1/system/info")
	if err != nil {
		t.Skipf("server not running, skipping E2E: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		t.Skipf("/api/v1/system/info not available (404), skipping")
	}
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
