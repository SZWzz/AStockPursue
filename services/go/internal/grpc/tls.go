package grpc

import (
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"os"

	"google.golang.org/grpc/credentials"
)

// LoadTLSCredentials returns TLS transport credentials with proper certificate
// verification. It uses the system CA pool by default, or a custom CA certificate
// if GRPC_CA_CERT environment variable is set.
//
// When GRPC_TLS_REQUIRED is "true", any credential loading failure is fatal.
// Otherwise, the error is logged but non-fatal.
func LoadTLSCredentials() (credentials.TransportCredentials, error) {
	caCertPath := os.Getenv("GRPC_CA_CERT")
	tlsRequired := os.Getenv("GRPC_TLS_REQUIRED") == "true"

	var cp *x509.CertPool
	if caCertPath != "" {
		pem, err := os.ReadFile(caCertPath)
		if err != nil {
			if tlsRequired {
				return nil, fmt.Errorf("GRPC_CA_CERT=%s cannot be read: %w", caCertPath, err)
			}
			log.Printf("WARNING: cannot read GRPC_CA_CERT=%s: %v — TLS will fail", caCertPath, err)
			return nil, err
		}
		cp = x509.NewCertPool()
		if !cp.AppendCertsFromPEM(pem) {
			if tlsRequired {
				return nil, fmt.Errorf("GRPC_CA_CERT=%s contains no valid certificates", caCertPath)
			}
			log.Printf("WARNING: GRPC_CA_CERT=%s contains no valid certificates", caCertPath)
			return nil, fmt.Errorf("no valid certificates in %s", caCertPath)
		}
		log.Printf("gRPC TLS: using custom CA cert from %s", caCertPath)
	} else {
		var err error
		cp, err = x509.SystemCertPool()
		if err != nil {
			if tlsRequired {
				return nil, fmt.Errorf("cannot load system CA pool: %w", err)
			}
			log.Printf("WARNING: cannot load system CA pool: %v — TLS will fail", err)
			return nil, err
		}
		log.Printf("gRPC TLS: using system CA pool")
	}

	return credentials.NewTLS(&tls.Config{
		RootCAs:    cp,
		MinVersion: tls.VersionTLS12,
	}), nil
}
