package loader

import (
	"testing"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/stretchr/testify/assert"
)

type mockLoader struct{}

func (m *mockLoader) Name() string { return "mock" }
func (m *mockLoader) IsAvailable() bool { return true }
func (m *mockLoader) FetchBars(symbol string, start, end time.Time) ([]*commonv1.Bar, error) {
	return []*commonv1.Bar{{Symbol: symbol}}, nil
}

type unavailableLoader struct{}

func (u *unavailableLoader) Name() string { return "unavailable" }
func (u *unavailableLoader) IsAvailable() bool { return false }
func (u *unavailableLoader) FetchBars(symbol string, start, end time.Time) ([]*commonv1.Bar, error) {
	return nil, nil
}

func TestRegisterAndGet(t *testing.T) {
	Clear()
	Register(&mockLoader{})
	loaders := GetAvailable()
	assert.Equal(t, 1, len(loaders))
	assert.Equal(t, "mock", loaders[0].Name())
}

func TestPriorityOrder(t *testing.T) {
	Clear()
	RegisterPriority(&mockLoader{}, 2)
	RegisterPriority(&mockLoader{}, 1) // higher priority = lower number
	loaders := GetAvailable()
	assert.Equal(t, 2, len(loaders))
}

func TestIsAvailableFilter(t *testing.T) {
	Clear()
	RegisterPriority(&unavailableLoader{}, 1)
	loaders := GetAvailable()
	assert.Equal(t, 0, len(loaders))
}

func TestClearRemovesAll(t *testing.T) {
	Clear()
	Register(&mockLoader{})
	Clear()
	loaders := GetAvailable()
	assert.Equal(t, 0, len(loaders))
}
