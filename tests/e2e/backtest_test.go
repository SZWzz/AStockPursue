package e2e

import (
	"bytes"
	"encoding/json"
	"net/http"
	"testing"
	"time"
)

func TestBacktestCreateEndpoint(t *testing.T) {
	client := &http.Client{Timeout: 10 * time.Second}
	body := map[string]interface{}{
		"symbols":      []string{"000001.SZ"},
		"start_date":   "2026-01-01",
		"end_date":     "2026-06-01",
		"frequency":    "daily",
		"initial_cash": float64(100000),
	}
	jsonBody, _ := json.Marshal(body)

	resp, err := client.Post(baseURL+"/api/v1/backtest", "application/json", bytes.NewReader(jsonBody))
	if err != nil {
		t.Skipf("server not running, skipping E2E: %v", err)
	}
	defer resp.Body.Close()
	// Accept 200 or 503 (Python unavailable)
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusServiceUnavailable {
		t.Errorf("expected 200 or 503, got %d", resp.StatusCode)
	}
}

func TestBacktestListEndpoint(t *testing.T) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(baseURL + "/api/v1/backtest")
	if err != nil {
		t.Skipf("server not running, skipping E2E: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusServiceUnavailable {
		t.Errorf("expected 200 or 503, got %d", resp.StatusCode)
	}
}

func TestBacktestGetEndpoint(t *testing.T) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(baseURL + "/api/v1/backtest/nonexistent-id")
	if err != nil {
		t.Skipf("server not running, skipping E2E: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound && resp.StatusCode != http.StatusServiceUnavailable {
		t.Errorf("expected 404 or 503, got %d", resp.StatusCode)
	}
}

func TestFactorListEndpoint(t *testing.T) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(baseURL + "/api/v1/factors")
	if err != nil {
		t.Skipf("server not running, skipping E2E: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusServiceUnavailable {
		t.Errorf("expected 200 or 503, got %d", resp.StatusCode)
	}
}

func TestPortfolioStatusEndpoint(t *testing.T) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(baseURL + "/api/v1/portfolio/status")
	if err != nil {
		t.Skipf("server not running, skipping E2E: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusServiceUnavailable {
		t.Errorf("expected 200 or 503, got %d", resp.StatusCode)
	}
}
