package papertrade

import "fmt"

// RunStatus represents the lifecycle state of a paper trading run.
type RunStatus string

const (
	StatusCreated RunStatus = "created"
	StatusRunning RunStatus = "running"
	StatusPaused  RunStatus = "paused"
	StatusStopped RunStatus = "stopped"
	StatusError   RunStatus = "error"
)

// validTransitions defines allowed state transitions.
var validTransitions = map[RunStatus][]RunStatus{
	StatusCreated: {StatusRunning},
	StatusRunning: {StatusPaused, StatusStopped, StatusError},
	StatusPaused:  {StatusRunning, StatusStopped},
	StatusError:   {StatusStopped},
}

// canTransition returns true if the state transition is allowed.
func canTransition(from, to RunStatus) bool {
	targets, ok := validTransitions[from]
	if !ok {
		return false
	}
	for _, t := range targets {
		if t == to {
			return true
		}
	}
	return false
}

// transition attempts to change the run status, returning an error if invalid.
func (r *Run) transition(to RunStatus) error {
	if !canTransition(r.Status, to) {
		return fmt.Errorf("papertrade: invalid transition %s→%s", r.Status, to)
	}
	r.Status = to
	return nil
}
