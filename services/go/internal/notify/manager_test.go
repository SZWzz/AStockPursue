package notify

import (
	"database/sql"
	"fmt"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

// mockNotifier records received messages for test assertions.
type mockNotifier struct {
	mu        sync.Mutex
	messages  []*Message
	available bool
	name      string
}

func newMockNotifier(name string, available bool) *mockNotifier {
	return &mockNotifier{name: name, available: available}
}

func (m *mockNotifier) Name() string      { return m.name }
func (m *mockNotifier) IsAvailable() bool { return m.available }
func (m *mockNotifier) Send(msg *Message) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.messages = append(m.messages, msg)
	return nil
}
func (m *mockNotifier) Messages() []*Message {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make([]*Message, len(m.messages))
	copy(out, m.messages)
	return out
}

// openTestDB opens an in-memory SQLite database for testing.
func openTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)
	t.Cleanup(func() { db.Close() })
	return db
}

func TestManagerRegisterSend(t *testing.T) {
	db := openTestDB(t)
	mgr := NewManager(db)

	m1 := newMockNotifier("alpha", true)
	m2 := newMockNotifier("beta", false) // not available — should be skipped

	mgr.Register(m1)
	mgr.Register(m2)

	mgr.Send(&Message{
		Level: LevelInfo,
		Title: "Test title",
		Body:  "Test body",
		Metadata: map[string]string{
			"key": "val",
		},
	})

	// Give the event goroutine time to process.
	time.Sleep(200 * time.Millisecond)

	msgs := m1.Messages()
	require.Len(t, msgs, 1)
	assert.Equal(t, LevelInfo, msgs[0].Level)
	assert.Equal(t, "Test title", msgs[0].Title)
	assert.Equal(t, "Test body", msgs[0].Body)
	assert.Equal(t, "val", msgs[0].Metadata["key"])

	// beta is unavailable so it should have zero messages.
	betaMsgs := m2.Messages()
	assert.Len(t, betaMsgs, 0)
}

func TestManagerHistory(t *testing.T) {
	db := openTestDB(t)
	mgr := NewManager(db)

	// Send two messages with a small gap to ensure ordering.
	mgr.Send(&Message{Level: LevelInfo, Title: "First", Body: "First body"})
	time.Sleep(50 * time.Millisecond)
	mgr.Send(&Message{Level: LevelError, Title: "Second", Body: "Second body"})

	// Give the event goroutine time to persist.
	time.Sleep(300 * time.Millisecond)

	// Retrieve all history.
	history, err := mgr.GetHistory(10, 0)
	require.NoError(t, err)
	require.GreaterOrEqual(t, len(history), 2)

	// Most recent first — "Second" should be at index 0.
	assert.Equal(t, "Second", history[0].Title)
	assert.Equal(t, string(LevelError), string(history[0].Level))
	assert.Equal(t, "First", history[1].Title)
	assert.Equal(t, string(LevelInfo), string(history[1].Level))
	assert.False(t, history[0].IsRead)
	assert.NotEmpty(t, history[0].CreatedAt)

	// Test MarkRead.
	err = mgr.MarkRead(history[0].ID)
	require.NoError(t, err)

	updated, err := mgr.GetHistory(10, 0)
	require.NoError(t, err)
	assert.True(t, updated[0].IsRead, "notification should be marked as read")
}

func TestManagerRegisterNilDB(t *testing.T) {
	// Manager with nil DB should still dispatch to notifiers.
	mgr := NewManager(nil)

	m := newMockNotifier("alpha", true)
	mgr.Register(m)

	mgr.Send(&Message{Level: LevelInfo, Title: "Hello", Body: "World"})
	time.Sleep(200 * time.Millisecond)

	msgs := m.Messages()
	assert.Len(t, msgs, 1)
}

func TestTelegramNotAvailable(t *testing.T) {
	// Unset the env vars to verify IsAvailable returns false.
	origToken := os.Getenv("TELEGRAM_BOT_TOKEN")
	origChat := os.Getenv("TELEGRAM_CHAT_ID")
	t.Cleanup(func() {
		os.Setenv("TELEGRAM_BOT_TOKEN", origToken)
		os.Setenv("TELEGRAM_CHAT_ID", origChat)
	})
	os.Unsetenv("TELEGRAM_BOT_TOKEN")
	os.Unsetenv("TELEGRAM_CHAT_ID")

	tn := NewTelegramNotifier()
	assert.Nil(t, tn, "NewTelegramNotifier should return nil when env vars are missing")
}

func TestTelegramNotAvailableWithEnv(t *testing.T) {
	// Set both env vars to empty strings explicitly.
	origToken := os.Getenv("TELEGRAM_BOT_TOKEN")
	origChat := os.Getenv("TELEGRAM_CHAT_ID")
	t.Cleanup(func() {
		os.Setenv("TELEGRAM_BOT_TOKEN", origToken)
		os.Setenv("TELEGRAM_CHAT_ID", origChat)
	})
	os.Setenv("TELEGRAM_BOT_TOKEN", "")
	os.Setenv("TELEGRAM_CHAT_ID", "")

	tn := NewTelegramNotifier()
	assert.Nil(t, tn)
}

func TestGetHistoryPagination(t *testing.T) {
	db := openTestDB(t)
	mgr := NewManager(db)

	for i := 0; i < 5; i++ {
		mgr.Send(&Message{
			Level: LevelInfo,
			Title: fmt.Sprintf("Msg %d", i+1),
			Body:  "body",
		})
		time.Sleep(30 * time.Millisecond)
	}
	time.Sleep(300 * time.Millisecond)

	// Page 1: limit 2, offset 0
	page1, err := mgr.GetHistory(2, 0)
	require.NoError(t, err)
	assert.Len(t, page1, 2)
	assert.Equal(t, "Msg 5", page1[0].Title)
	assert.Equal(t, "Msg 4", page1[1].Title)

	// Page 2: limit 2, offset 2
	page2, err := mgr.GetHistory(2, 2)
	require.NoError(t, err)
	assert.Len(t, page2, 2)
	assert.Equal(t, "Msg 3", page2[0].Title)
	assert.Equal(t, "Msg 2", page2[1].Title)

	// Offset beyond data.
	empty, err := mgr.GetHistory(10, 99)
	require.NoError(t, err)
	assert.Len(t, empty, 0)
}

func TestMarkReadNotFound(t *testing.T) {
	db := openTestDB(t)
	mgr := NewManager(db)

	err := mgr.MarkRead("nonexistent-id")
	assert.ErrorContains(t, err, "not found")
}

func TestFormatTelegramMessage(t *testing.T) {
	msg := &Message{
		Level: LevelError,
		Title: "Something broke",
		Body:  "Details here",
	}
	txt := formatTelegramMessage(msg)
	assert.Contains(t, txt, "Something broke")
	assert.Contains(t, txt, "Details here")
}
