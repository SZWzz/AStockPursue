package notify

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"
)

// TelegramNotifier sends notifications through the Telegram Bot API.
type TelegramNotifier struct {
	botToken string
	chatID   string
	client   *http.Client
}

// NewTelegramNotifier creates a TelegramNotifier from environment variables.
// Returns nil if either TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is empty.
func NewTelegramNotifier() *TelegramNotifier {
	token := os.Getenv("TELEGRAM_BOT_TOKEN")
	chatID := os.Getenv("TELEGRAM_CHAT_ID")
	if token == "" || chatID == "" {
		return nil
	}
	return &TelegramNotifier{
		botToken: token,
		chatID:   chatID,
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// Name returns the notifier identifier.
func (t *TelegramNotifier) Name() string {
	return "telegram"
}

// IsAvailable reports whether both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
// environment variables are set.
func (t *TelegramNotifier) IsAvailable() bool {
	return t != nil && t.botToken != "" && t.chatID != ""
}

// telegramPayload is the JSON body sent to the Telegram API.
type telegramPayload struct {
	ChatID    string `json:"chat_id"`
	Text      string `json:"text"`
	ParseMode string `json:"parse_mode,omitempty"`
}

// Send delivers the message via the Telegram Bot API's sendMessage method.
func (t *TelegramNotifier) Send(msg *Message) error {
	if !t.IsAvailable() {
		return fmt.Errorf("telegram notifier not configured")
	}

	text := formatTelegramMessage(msg)
	payload := telegramPayload{
		ChatID:    t.chatID,
		Text:      text,
		ParseMode: "HTML",
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal payload: %w", err)
	}

	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", t.botToken)
	resp, err := t.client.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("telegram API request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("telegram API error: status %d", resp.StatusCode)
	}
	return nil
}

// formatTelegramMessage builds an HTML-formatted message string from a Message.
func formatTelegramMessage(msg *Message) string {
	icon := map[Level]string{
		LevelInfo:    "ℹ️",  // ℹ️
		LevelWarning: "⚠️",  // ⚠️
		LevelError:   "❌",        // ❌
	}

	txt := fmt.Sprintf("%s <b>%s</b>\n%s", icon[msg.Level], msg.Title, msg.Body)
	// Truncate to Telegram's 4096-byte limit.
	if len(txt) > 4000 {
		txt = txt[:4000] + "..."
	}
	return txt
}
