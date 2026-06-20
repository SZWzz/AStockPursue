package broker

import (
	"fmt"
	"sync"
)

// BrokerFactory creates Broker instances by name.
// Brokers self-register via Register() in their init() functions.
type BrokerFactory struct {
	mu       sync.RWMutex
	creators map[string]func(cfg BrokerConfig) (Broker, error)
}

// BrokerConfig holds common configuration for creating a broker connection.
type BrokerConfig struct {
	Name    string
	APIKey  string
	Secret  string
	Passphrase string // OKX-specific
	Testnet bool
	Host    string // Futu-specific
	Port    int    // Futu-specific
}

var defaultFactory = &BrokerFactory{
	creators: make(map[string]func(cfg BrokerConfig) (Broker, error)),
}

// Register registers a broker constructor for the given name.
// Called automatically by broker implementations in their init().
func Register(name string, creator func(cfg BrokerConfig) (Broker, error)) {
	defaultFactory.mu.Lock()
	defer defaultFactory.mu.Unlock()
	defaultFactory.creators[name] = creator
}

// New creates a new Broker instance by name with the given configuration.
func New(name string, cfg BrokerConfig) (Broker, error) {
	defaultFactory.mu.RLock()
	creator, ok := defaultFactory.creators[name]
	defaultFactory.mu.RUnlock()
	if !ok {
		return nil, fmt.Errorf("broker: unknown exchange %q (available: %v)", name, List())
	}
	cfg.Name = name
	return creator(cfg)
}

// List returns the names of all registered brokers.
func List() []string {
	defaultFactory.mu.RLock()
	defer defaultFactory.mu.RUnlock()
	names := make([]string, 0, len(defaultFactory.creators))
	for name := range defaultFactory.creators {
		names = append(names, name)
	}
	return names
}
