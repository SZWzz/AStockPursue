package papertrade

import (
	"testing"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/stretchr/testify/assert"
)

func TestEngineCreateRun(t *testing.T) {
	cache := market.NewMemoryCache(5*time.Minute, 100)
	ds := market.NewDataStore(nil, cache)
	factory := engine.NewEngineFactory()
	e := NewEngine(ds, factory, nil)

	run, err := e.Create("test-run", []string{"000001.SZ"}, "1d", 100000)
	assert.NoError(t, err)
	assert.NotEmpty(t, run.ID, "expected non-empty ID")
	assert.Equal(t, StatusCreated, run.Status, "expected status created")
	assert.Equal(t, "test-run", run.Name)
	assert.Equal(t, []string{"000001.SZ"}, run.Symbols)
	assert.Equal(t, "1d", run.Frequency)
	assert.Equal(t, 100000.0, run.InitialCash)
}

func TestEngineStateTransitions(t *testing.T) {
	cache := market.NewMemoryCache(5*time.Minute, 100)
	ds := market.NewDataStore(nil, cache)
	factory := engine.NewEngineFactory()
	e := NewEngine(ds, factory, nil)

	run, err := e.Create("test", []string{"000001.SZ"}, "1d", 100000)
	assert.NoError(t, err)

	// created → running
	err = e.Start(run.ID)
	assert.NoError(t, err)
	assert.Equal(t, StatusRunning, run.Status, "expected running")

	// running → stopped
	err = e.Stop(run.ID)
	assert.NoError(t, err)
	assert.Equal(t, StatusStopped, run.Status, "expected stopped")
}

func TestEngineListAndGet(t *testing.T) {
	cache := market.NewMemoryCache(5*time.Minute, 100)
	ds := market.NewDataStore(nil, cache)
	factory := engine.NewEngineFactory()
	e := NewEngine(ds, factory, nil)

	_, err := e.Create("run1", []string{"000001.SZ"}, "1d", 100000)
	assert.NoError(t, err)
	_, err = e.Create("run2", []string{"000002.SZ"}, "1h", 50000)
	assert.NoError(t, err)

	runs := e.List()
	assert.Len(t, runs, 2, "expected 2 runs")

	run := e.Get(runs[0].ID)
	assert.NotNil(t, run, "Get returned nil for valid ID")
	assert.Equal(t, runs[0].ID, run.ID)
}

func TestEngineDelete(t *testing.T) {
	cache := market.NewMemoryCache(5*time.Minute, 100)
	ds := market.NewDataStore(nil, cache)
	factory := engine.NewEngineFactory()
	e := NewEngine(ds, factory, nil)

	run, err := e.Create("test", []string{"000001.SZ"}, "1d", 100000)
	assert.NoError(t, err)

	err = e.Delete(run.ID)
	assert.NoError(t, err)
	assert.Len(t, e.List(), 0, "expected 0 runs after delete")
}

func TestInvalidTransitions(t *testing.T) {
	cache := market.NewMemoryCache(5*time.Minute, 100)
	ds := market.NewDataStore(nil, cache)
	factory := engine.NewEngineFactory()
	e := NewEngine(ds, factory, nil)

	run, err := e.Create("test", []string{"000001.SZ"}, "1d", 100000)
	assert.NoError(t, err)

	// Start it
	err = e.Start(run.ID)
	assert.NoError(t, err)

	// Cannot start an already running run
	err = e.Start(run.ID)
	assert.Error(t, err, "expected error when starting already-running run")

	// Stop it
	err = e.Stop(run.ID)
	assert.NoError(t, err)

	// Cannot stop a stopped run
	err = e.Stop(run.ID)
	assert.Error(t, err, "expected error when stopping already-stopped run")
}

func TestDefaultValues(t *testing.T) {
	cache := market.NewMemoryCache(5*time.Minute, 100)
	ds := market.NewDataStore(nil, cache)
	factory := engine.NewEngineFactory()
	e := NewEngine(ds, factory, nil)

	// Empty frequency → defaults to "1d"
	run, err := e.Create("test", []string{"000001.SZ"}, "", 0)
	assert.NoError(t, err)
	assert.Equal(t, "1d", run.Frequency)
	assert.Equal(t, 100000.0, run.InitialCash)
}

func TestStateMachineValidTransitions(t *testing.T) {
	assert.True(t, canTransition(StatusCreated, StatusRunning))
	assert.True(t, canTransition(StatusRunning, StatusPaused))
	assert.True(t, canTransition(StatusRunning, StatusStopped))
	assert.True(t, canTransition(StatusRunning, StatusError))
	assert.True(t, canTransition(StatusPaused, StatusRunning))
	assert.True(t, canTransition(StatusPaused, StatusStopped))
	assert.True(t, canTransition(StatusError, StatusStopped))
}

func TestStateMachineInvalidTransitions(t *testing.T) {
	assert.False(t, canTransition(StatusCreated, StatusStopped))
	assert.False(t, canTransition(StatusCreated, StatusPaused))
	assert.False(t, canTransition(StatusStopped, StatusRunning))
	assert.False(t, canTransition(StatusStopped, StatusCreated))
	assert.False(t, canTransition(StatusError, StatusRunning))
}
