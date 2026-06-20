package loader

import (
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
)

type Loader interface {
	Name() string
	IsAvailable() bool
	FetchBars(symbol string, start, end time.Time) ([]*commonv1.Bar, error)
}
