package market

import "strings"

// NormalizeSymbol ensures a stock symbol has exchange suffix.
// "000001" -> "000001.SZ", "600519" -> "600519.SH".
// If the code already contains a dot, it is returned unchanged.
func NormalizeSymbol(code string) string {
	if code == "" {
		return code
	}
	if strings.Contains(code, ".") {
		return code
	}
	if len(code) < 3 {
		return code
	}

	prefix := code[:3]
	if prefix == "000" || prefix == "001" || prefix == "002" || prefix == "003" {
		return code + ".SZ"
	}
	if prefix == "600" || prefix == "601" || prefix == "603" || prefix == "605" {
		return code + ".SH"
	}

	// Unknown prefix — return as-is (could be non-A-share or crypto)
	return code
}
