package research

import (
	"context"
	"time"
)

type DataPoint struct {
	Symbol   string            `json:"symbol"`
	Date     time.Time         `json:"date"`
	Category string            `json:"category"`
	Key      string            `json:"key"`
	Value    float64           `json:"value"`
	Metadata map[string]string `json:"metadata,omitempty"`
}

type Service interface {
	Name() string
	Analyze(ctx context.Context, symbol string, params map[string]any) (map[string]any, error)
	History(ctx context.Context, symbol string, days int) ([]DataPoint, error)
	IsAvailable() bool
}
