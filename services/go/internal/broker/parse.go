package broker

import (
	"fmt"
	"strconv"
	"strings"
)

// safeParseFloat parses a string to float64 with proper error handling.
// Returns an error for empty strings and parse failures.
func safeParseFloat(s string) (float64, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return 0, fmt.Errorf("cannot parse empty string as float64")
	}
	v, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return 0, fmt.Errorf("cannot parse %q as float64: %w", s, err)
	}
	return v, nil
}
