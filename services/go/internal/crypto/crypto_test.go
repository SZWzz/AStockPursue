package crypto

import (
	"testing"
)

func TestEncryptDecryptRoundtrip(t *testing.T) {
	key, err := GenerateKey()
	if err != nil {
		t.Fatalf("GenerateKey failed: %v", err)
	}
	if err := Init(key); err != nil {
		t.Fatalf("Init failed: %v", err)
	}
	plaintext := "my-super-secret-api-key-12345"
	cipher, err := Encrypt(plaintext)
	if err != nil {
		t.Fatalf("Encrypt failed: %v", err)
	}
	if cipher == "" || cipher == plaintext {
		t.Fatal("Encrypt should produce different output from input")
	}
	decrypted, err := Decrypt(cipher)
	if err != nil {
		t.Fatalf("Decrypt failed: %v", err)
	}
	if decrypted != plaintext {
		t.Fatalf("Roundtrip failed: got %q, want %q", decrypted, plaintext)
	}
}

func TestEncryptWithoutInit(t *testing.T) {
	key = nil
	_, err := Encrypt("test")
	if err == nil {
		t.Fatal("Expected error when not initialized")
	}
}

func TestInitInvalidKey(t *testing.T) {
	if err := Init("not-valid-base64!!"); err == nil {
		t.Fatal("Expected error for invalid base64 key")
	}
	if err := Init("dG9vLXNob3J0"); err == nil {
		t.Fatal("Expected error for short key")
	}
}
