package engine

import "time"

type NoopSignalAdapter struct{}

func NewNoopSignalAdapter() *NoopSignalAdapter {
	return &NoopSignalAdapter{}
}

func (n *NoopSignalAdapter) Generate(bars []interface{}, ts time.Time) (map[string]float64, error) {
	return nil, nil
}
