package papertrade

import "sync"

// Repository persists paper trading runs.
type Repository interface {
	Save(run *Run) error
	LoadAll() ([]*Run, error)
	Delete(id string) error
}

// MemoryRepository is an in-memory implementation for development/testing.
type MemoryRepository struct {
	mu   sync.RWMutex
	runs map[string]*Run
}

// NewMemoryRepository creates a new in-memory repository.
func NewMemoryRepository() *MemoryRepository {
	return &MemoryRepository{runs: make(map[string]*Run)}
}

func (r *MemoryRepository) Save(run *Run) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.runs[run.ID] = run
	return nil
}

func (r *MemoryRepository) LoadAll() ([]*Run, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	runs := make([]*Run, 0, len(r.runs))
	for _, run := range r.runs {
		runs = append(runs, run)
	}
	return runs, nil
}

func (r *MemoryRepository) Delete(id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.runs, id)
	return nil
}
