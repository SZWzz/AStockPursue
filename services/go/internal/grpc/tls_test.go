package grpc

import (
	"os"
	"testing"
)

func TestLoadTLSCredentials_Disabled(t *testing.T) {
	// When GRPC_TLS_ENABLED is not "true", this function is not called.
	// Test that the helper compiles and can be invoked.
	os.Setenv("GRPC_TLS_ENABLED", "true")
	os.Setenv("GRPC_TLS_REQUIRED", "false")
	os.Unsetenv("GRPC_CA_CERT")

	creds, err := LoadTLSCredentials()
	if err != nil {
		t.Fatalf("unexpected error loading TLS credentials: %v", err)
	}
	if creds == nil {
		t.Fatal("expected non-nil credentials")
	}
}

func TestLoadTLSCredentials_InvalidCACert_NotRequired(t *testing.T) {
	os.Setenv("GRPC_TLS_ENABLED", "true")
	os.Setenv("GRPC_TLS_REQUIRED", "false")
	os.Setenv("GRPC_CA_CERT", "/nonexistent/path/ca.pem")

	_, err := LoadTLSCredentials()
	if err == nil {
		t.Fatal("expected error for nonexistent CA cert path")
	}
}

func TestLoadTLSCredentials_InvalidCACert_Required(t *testing.T) {
	os.Setenv("GRPC_TLS_ENABLED", "true")
	os.Setenv("GRPC_TLS_REQUIRED", "true")
	os.Setenv("GRPC_CA_CERT", "/nonexistent/path/ca.pem")

	_, err := LoadTLSCredentials()
	if err == nil {
		t.Fatal("expected fatal error when GRPC_TLS_REQUIRED=true and CA cert missing")
	}
}
