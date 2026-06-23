package research

import (
	"context"
	"time"
)

// ResearchParams is a named type alias for the analysis parameters map
// passed to a service's Analyze method. It is map[string]any under the hood
// and is fully interchangeable with that type. The alias exists only for
// readability and to provide a migration anchor for a future structured
// configuration type.
type ResearchParams = map[string]any

// ResearchResult is a named type alias for the results map returned by a
// service's Analyze method, keyed by result field name. Like ResearchParams
// it is map[string]any and fully interchangeable; the alias is for
// readability and future migration.
type ResearchResult = map[string]any

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
	Analyze(ctx context.Context, symbol string, params ResearchParams) (ResearchResult, error)
	History(ctx context.Context, symbol string, days int) ([]DataPoint, error)
	IsAvailable() bool
}
