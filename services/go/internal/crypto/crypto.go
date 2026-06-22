package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
	"io"
)

var key []byte

func Init(encodedKey string) error {
	if encodedKey == "" {
		return errors.New("crypto: ENCRYPTION_KEY is required")
	}
	k, err := base64.StdEncoding.DecodeString(encodedKey)
	if err != nil {
		return fmt.Errorf("crypto: invalid ENCRYPTION_KEY: %w", err)
	}
	if len(k) != 32 {
		return errors.New("crypto: ENCRYPTION_KEY must be 32 bytes (base64 encoded)")
	}
	key = k
	return nil
}

func Encrypt(plaintext string) (string, error) {
	if key == nil {
		return "", errors.New("crypto: not initialized")
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", fmt.Errorf("crypto: %w", err)
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("crypto: %w", err)
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", fmt.Errorf("crypto: %w", err)
	}
	ciphertext := gcm.Seal(nonce, nonce, []byte(plaintext), nil)
	return base64.StdEncoding.EncodeToString(ciphertext), nil
}

func Decrypt(encoded string) (string, error) {
	if key == nil {
		return "", errors.New("crypto: not initialized")
	}
	ciphertext, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return "", fmt.Errorf("crypto: %w", err)
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", fmt.Errorf("crypto: %w", err)
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("crypto: %w", err)
	}
	nonceSize := gcm.NonceSize()
	if len(ciphertext) < nonceSize {
		return "", errors.New("crypto: ciphertext too short")
	}
	nonce, ciphertext := ciphertext[:nonceSize], ciphertext[nonceSize:]
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return "", fmt.Errorf("crypto: decryption failed: %w", err)
	}
	return string(plaintext), nil
}

func GenerateKey() string {
	k := make([]byte, 32)
	if _, err := rand.Read(k); err != nil {
		panic("crypto: failed to generate key: " + err.Error())
	}
	return base64.StdEncoding.EncodeToString(k)
}
