package notify

// Level represents the severity of a notification message.
type Level string

const (
	LevelInfo    Level = "info"
	LevelWarning Level = "warning"
	LevelError   Level = "error"
)

// Message is an in-memory notification to be dispatched to registered notifiers
// and persisted to the database.
type Message struct {
	Level    Level
	Title    string
	Body     string
	Metadata map[string]string
}

// Notification represents a persisted notification record.
type Notification struct {
	ID        string
	Level     Level
	Title     string
	Body      string
	Metadata  string // JSON-encoded map
	IsRead    bool
	CreatedAt string // RFC3339 format
}

// Notifier is the interface that must be implemented by notification channels
// (e.g., Telegram, email, webhook).
type Notifier interface {
	// Name returns a human-readable identifier for this notifier.
	Name() string
	// Send delivers the message through this notification channel.
	Send(msg *Message) error
	// IsAvailable reports whether this notifier is properly configured and
	// ready to send messages.
	IsAvailable() bool
}
