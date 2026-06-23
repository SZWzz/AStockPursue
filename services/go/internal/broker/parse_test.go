package broker

import (
	"testing"
)

func TestSafeParseFloat_Valid(t *testing.T) {
	v, err := safeParseFloat("123.45")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if v != 123.45 {
		t.Fatalf("expected 123.45, got %v", v)
	}
}

func TestSafeParseFloat_Negative(t *testing.T) {
	v, err := safeParseFloat("-0.005")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if v != -0.005 {
		t.Fatalf("expected -0.005, got %v", v)
	}
}

func TestSafeParseFloat_EmptyString(t *testing.T) {
	_, err := safeParseFloat("")
	if err == nil {
		t.Fatal("expected error for empty string")
	}
}

func TestSafeParseFloat_Invalid(t *testing.T) {
	_, err := safeParseFloat("not-a-number")
	if err == nil {
		t.Fatal("expected error for invalid input")
	}
}

func TestSafeParseFloat_Whitespace(t *testing.T) {
	v, err := safeParseFloat("  42  ")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if v != 42 {
		t.Fatalf("expected 42, got %v", v)
	}
}
