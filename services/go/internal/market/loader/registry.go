package loader

import (
	"sort"
	"sync"
)

type entry struct {
	loader   Loader
	priority int
}

var (
	mu      sync.RWMutex
	entries []entry
)

func Register(l Loader) {
	RegisterPriority(l, 10)
}

func RegisterPriority(l Loader, priority int) {
	mu.Lock()
	defer mu.Unlock()
	for _, e := range entries {
		if e.loader.Name() == l.Name() {
			return
		}
	}
	entries = append(entries, entry{loader: l, priority: priority})
	sort.Slice(entries, func(i, j int) bool {
		return entries[i].priority < entries[j].priority
	})
}

func GetAvailable() []Loader {
	mu.RLock()
	defer mu.RUnlock()
	var available []Loader
	for _, e := range entries {
		if e.loader.IsAvailable() {
			available = append(available, e.loader)
		}
	}
	return available
}

func Clear() {
	mu.Lock()
	defer mu.Unlock()
	entries = nil
}
