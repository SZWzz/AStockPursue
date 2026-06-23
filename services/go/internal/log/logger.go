package log

import (
	"log"
	"os"
)

// Logger is a lightweight structured logging wrapper around the standard library's log.Logger.
// It provides leveled logging methods (Info, Error, Warn, Debug) without external dependencies.
type Logger struct {
	*log.Logger
}

// New creates a new Logger that writes to stderr with standard log flags.
func New() *Logger {
	return &Logger{log.New(os.Stderr, "", log.LstdFlags)}
}

// Info logs an informational message.
func (l *Logger) Info(format string, v ...any) {
	l.Printf("[INFO] "+format, v...)
}

// Error logs an error message.
func (l *Logger) Error(format string, v ...any) {
	l.Printf("[ERROR] "+format, v...)
}

// Warn logs a warning message.
func (l *Logger) Warn(format string, v ...any) {
	l.Printf("[WARN] "+format, v...)
}

// Debug logs a debug message. Only logs when GO_ENV is "development".
func (l *Logger) Debug(format string, v ...any) {
	if os.Getenv("GO_ENV") == "development" {
		l.Printf("[DEBUG] "+format, v...)
	}
}
