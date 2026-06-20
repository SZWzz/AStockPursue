package market

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
)

// LocalStore provides file-based bar storage as Tier 2 of the data pipeline.
//
// Bars are stored as newline-delimited JSON (JSONL), one bar per line,
// organized by exchange/symbol/frequency. This format is human-readable,
// append-friendly, and requires no external dependencies.
type LocalStore struct {
	basePath string
}

// barJSON is the on-disk representation of a single bar.
type barJSON struct {
	Symbol    string `json:"symbol"`
	Open      float64 `json:"open"`
	High      float64 `json:"high"`
	Low       float64 `json:"low"`
	Close     float64 `json:"close"`
	Volume    int64   `json:"volume"`
	Timestamp int64   `json:"timestamp"`
	Frequency string  `json:"frequency"`
}

func NewLocalStore(basePath string) *LocalStore {
	return &LocalStore{basePath: basePath}
}

func (ls *LocalStore) Path() string {
	return ls.basePath
}

// SaveBars appends bars for a given symbol/frequency to the local store.
// Existing bars with the same timestamp are NOT overwritten (first write wins).
func (ls *LocalStore) SaveBars(symbol string, freq string, bars []*commonv1.Bar) error {
	if len(bars) == 0 {
		return nil
	}

	// Load existing bars to dedup by timestamp
	existing, err := ls.loadAll(symbol, freq)
	if err != nil {
		return err
	}
	seen := make(map[int64]bool, len(existing))
	for _, b := range existing {
		seen[b.Timestamp] = true
	}

	// Filter to only new bars
	var newBars []*commonv1.Bar
	for _, b := range bars {
		if !seen[b.Timestamp] {
			newBars = append(newBars, b)
			seen[b.Timestamp] = true
		}
	}
	if len(newBars) == 0 {
		return nil
	}

	path := ls.filePath(symbol, freq)
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return fmt.Errorf("localstore mkdir: %w", err)
	}

	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("localstore open: %w", err)
	}
	defer f.Close()

	encoder := json.NewEncoder(f)
	for _, b := range newBars {
		rec := barJSON{
			Symbol:    b.Symbol,
			Open:      b.Open,
			High:      b.High,
			Low:       b.Low,
			Close:     b.Close,
			Volume:    b.Volume,
			Timestamp: b.Timestamp,
			Frequency: b.Frequency,
		}
		if err := encoder.Encode(rec); err != nil {
			return fmt.Errorf("localstore encode: %w", err)
		}
	}
	return nil
}

// LoadBars loads bars for a symbol/frequency within the given time range.
// Returns an empty slice (not error) if no data exists.
func (ls *LocalStore) LoadBars(symbol string, start, end time.Time, freq string) ([]*commonv1.Bar, error) {
	all, err := ls.loadAll(symbol, freq)
	if err != nil {
		return nil, err
	}

	startMs := start.UnixMilli()
	endMs := end.UnixMilli()

	var result []*commonv1.Bar
	for _, b := range all {
		if b.Timestamp >= startMs && b.Timestamp <= endMs {
			result = append(result, b)
		}
	}
	return result, nil
}

// DeleteBars removes the data file for a symbol/frequency combination.
func (ls *LocalStore) DeleteBars(symbol string, freq string) error {
	path := ls.filePath(symbol, freq)
	if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("localstore delete: %w", err)
	}
	return nil
}

// loadAll reads all bars from a symbol/frequency file, returning an empty slice
// if the file does not exist.
func (ls *LocalStore) loadAll(symbol string, freq string) ([]*commonv1.Bar, error) {
	path := ls.filePath(symbol, freq)
	f, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("localstore read: %w", err)
	}
	defer f.Close()

	var bars []*commonv1.Bar
	scanner := bufio.NewScanner(f)
	// 1MB buffer per line (plenty for a single bar JSON)
	scanner.Buffer(make([]byte, 1024*1024), 1024*1024)

	for scanner.Scan() {
		var rec barJSON
		if err := json.Unmarshal(scanner.Bytes(), &rec); err != nil {
			continue // skip corrupt lines
		}
		bars = append(bars, &commonv1.Bar{
			Symbol:    rec.Symbol,
			Open:      rec.Open,
			High:      rec.High,
			Low:       rec.Low,
			Close:     rec.Close,
			Volume:    rec.Volume,
			Timestamp: rec.Timestamp,
			Frequency: rec.Frequency,
		})
	}
	return bars, scanner.Err()
}

// filePath returns the full path to the bar file for a symbol/frequency.
// Example: {basePath}/sh/600000/1d.jsonl
func (ls *LocalStore) filePath(symbol string, freq string) string {
	return filepath.Join(ls.basePath, ls.exchangeDir(symbol), symbol, freq+".jsonl")
}

// exchangeDir maps an A-share code prefix to an exchange directory name.
// 6xxxxx → sh, 0/3xxxxx → sz, 4/8/9xxxxx → bj.
func (ls *LocalStore) exchangeDir(symbol string) string {
	if len(symbol) == 0 {
		return "unknown"
	}
	switch symbol[0] {
	case '6':
		return "sh"
	case '0', '3':
		return "sz"
	case '4', '8', '9':
		return "bj"
	default:
		return "unknown"
	}
}
