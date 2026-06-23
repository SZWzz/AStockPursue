package notify

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	slog "github.com/astockpursue/go-core/internal/log"
	"github.com/google/uuid"
)

// Manager coordinates notification dispatch across multiple notifiers and
// persists all notifications to a SQLite database for history retrieval.
type Manager struct {
	mu        sync.RWMutex
	notifiers []Notifier
	eventCh   chan *Message
	db        *sql.DB
	once      sync.Once
	stopCh    chan struct{}
}

// NewManager creates a notification manager backed by the given SQLite
// database. The event-processing goroutine is started lazily on the first
// Send call.
func NewManager(db *sql.DB) *Manager {
	m := &Manager{
		eventCh: make(chan *Message, 256),
		db:      db,
		stopCh:  make(chan struct{}),
	}
	m.initDB()
	return m
}

// Register adds a notifier to the dispatch list. Notifiers are tried in
// registration order; failures are logged but do not block other notifiers.
func (m *Manager) Register(n Notifier) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.notifiers = append(m.notifiers, n)
}

// Send enqueues a message for asynchronous dispatch. Returns immediately;
// the actual send happens in the event-processing goroutine.
func (m *Manager) Send(msg *Message) {
	m.once.Do(func() {
		go m.processEvents()
	})
	select {
	case m.eventCh <- msg:
	default:
		slog.Warnf("[notify] event channel full, dropping message: %s", msg.Title)
	}
}

// processEvents runs in a goroutine, reading messages from the event channel
// and dispatching them to all registered notifiers, then persisting them.
func (m *Manager) processEvents() {
	for {
		select {
		case msg := <-m.eventCh:
			m.dispatch(msg)
			m.persist(msg)
		case <-m.stopCh:
			return
		}
	}
}

// dispatch sends the message to all available notifiers concurrently.
func (m *Manager) dispatch(msg *Message) {
	m.mu.RLock()
	notifiers := make([]Notifier, len(m.notifiers))
	copy(notifiers, m.notifiers)
	m.mu.RUnlock()

	var wg sync.WaitGroup
	for _, n := range notifiers {
		if n.IsAvailable() {
			wg.Add(1)
			go func(nn Notifier) {
				defer wg.Done()
				if err := nn.Send(msg); err != nil {
					slog.Errorf("[notify] %s send failed: %v", nn.Name(), err)
				}
			}(n)
		}
	}
	wg.Wait()
}

// persist writes the message to the SQLite database.
func (m *Manager) persist(msg *Message) {
	if m.db == nil {
		return
	}
	metaJSON := "{}"
	if msg.Metadata != nil {
		b, err := json.Marshal(msg.Metadata)
		if err == nil {
			metaJSON = string(b)
		}
	}

	id := uuid.New().String()
	now := time.Now().UTC().Format(time.RFC3339Nano)

	_, err := m.db.Exec(
		`INSERT INTO notifications (id, level, title, body, metadata, is_read, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)`,
		id, string(msg.Level), msg.Title, msg.Body, metaJSON, false, now,
	)
	if err != nil {
		slog.Errorf("[notify] persist failed: %v", err)
	}
}

// GetHistory returns paginated notifications ordered by creation time
// descending.
func (m *Manager) GetHistory(limit, offset int) ([]*Notification, error) {
	if m.db == nil {
		return nil, fmt.Errorf("database not available")
	}
	if limit <= 0 {
		limit = 50
	}
	if offset < 0 {
		offset = 0
	}

	rows, err := m.db.Query(
		`SELECT id, level, title, body, metadata, is_read, created_at FROM notifications ORDER BY created_at DESC LIMIT ? OFFSET ?`,
		limit, offset,
	)
	if err != nil {
		return nil, fmt.Errorf("query notifications: %w", err)
	}
	defer rows.Close()

	var out []*Notification
	for rows.Next() {
		n := &Notification{}
		if err := rows.Scan(&n.ID, &n.Level, &n.Title, &n.Body, &n.Metadata, &n.IsRead, &n.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan notification: %w", err)
		}
		out = append(out, n)
	}
	return out, rows.Err()
}

// MarkRead sets the is_read flag to true for the given notification ID.
func (m *Manager) MarkRead(id string) error {
	if m.db == nil {
		return fmt.Errorf("database not available")
	}
	res, err := m.db.Exec(`UPDATE notifications SET is_read = 1 WHERE id = ?`, id)
	if err != nil {
		return fmt.Errorf("update notification: %w", err)
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return fmt.Errorf("notification not found: %s", id)
	}
	return nil
}

// MarkAllRead sets the is_read flag to true for all notifications.
func (m *Manager) MarkAllRead() error {
	if m.db == nil {
		return fmt.Errorf("database not available")
	}
	_, err := m.db.Exec(`UPDATE notifications SET is_read = 1`)
	if err != nil {
		return fmt.Errorf("mark all read: %w", err)
	}
	return nil
}

// Close gracefully shuts down the event-processing goroutine.
func (m *Manager) Close() {
	close(m.stopCh)
}

// initDB creates the notifications table if it does not exist.
func (m *Manager) initDB() {
	if m.db == nil {
		return
	}
	_, err := m.db.Exec(`
		CREATE TABLE IF NOT EXISTS notifications (
			id         TEXT PRIMARY KEY,
			level      TEXT NOT NULL,
			title      TEXT NOT NULL,
			body       TEXT NOT NULL DEFAULT '',
			metadata   TEXT NOT NULL DEFAULT '{}',
			is_read    INTEGER NOT NULL DEFAULT 0,
			created_at TEXT NOT NULL
		)
	`)
	if err != nil {
		slog.Errorf("[notify] initDB failed: %v", err)
	}
}
