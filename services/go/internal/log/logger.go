package log

import (
	"fmt"
	"io"
	stdlog "log"
	"os"
	"strings"
)

// Level represents log severity.
type Level int

const (
	LevelDebug Level = iota
	LevelInfo
	LevelWarn
	LevelError
)

func (l Level) String() string {
	switch l {
	case LevelDebug:
		return "DEBUG"
	case LevelInfo:
		return "INFO"
	case LevelWarn:
		return "WARN"
	case LevelError:
		return "ERROR"
	default:
		return "UNKNOWN"
	}
}

// Logger is a structured logger that wraps the standard log package.
type Logger struct {
	level  Level
	output *stdlog.Logger
}

// DefaultLogger is the package-level logger used by convenience functions.
// It writes to os.Stderr at LevelInfo by default.
var DefaultLogger = New(LevelInfo, os.Stderr)

// New creates a new Logger with the given level and writer.
func New(level Level, w io.Writer) *Logger {
	return &Logger{
		level:  level,
		output: stdlog.New(w, "", stdlog.LstdFlags),
	}
}

// NewDefault creates a new Logger at LevelInfo writing to os.Stderr.
// This is the zero-arg convenience constructor used by existing packages.
func NewDefault() *Logger {
	return New(LevelInfo, os.Stderr)
}

// SetLevel changes the minimum log level.
func (l *Logger) SetLevel(level Level) {
	l.level = level
}

// Level returns the current minimum log level.
func (l *Logger) Level() Level {
	return l.level
}

func (l *Logger) logf(level Level, format string, args ...interface{}) {
	if level < l.level {
		return
	}
	msg := fmt.Sprintf(format, args...)
	l.output.Printf("[%s] %s", level.String(), msg)
}

func (l *Logger) Debugf(format string, args ...interface{}) { l.logf(LevelDebug, format, args...) }
func (l *Logger) Infof(format string, args ...interface{})  { l.logf(LevelInfo, format, args...) }
func (l *Logger) Warnf(format string, args ...interface{})  { l.logf(LevelWarn, format, args...) }
func (l *Logger) Errorf(format string, args ...interface{}) { l.logf(LevelError, format, args...) }

// Convenience methods without the 'f' suffix for compatibility with
// existing callers that use logger.Info / logger.Warn / logger.Error.
func (l *Logger) Debug(format string, args ...interface{}) { l.logf(LevelDebug, format, args...) }
func (l *Logger) Info(format string, args ...interface{})  { l.logf(LevelInfo, format, args...) }
func (l *Logger) Warn(format string, args ...interface{})  { l.logf(LevelWarn, format, args...) }
func (l *Logger) Error(format string, args ...interface{}) { l.logf(LevelError, format, args...) }

// Package-level convenience functions that use DefaultLogger.

// Debugf logs a debug message using DefaultLogger.
func Debugf(format string, args ...interface{}) {
	DefaultLogger.Debugf(format, args...)
}

// Infof logs an info message using DefaultLogger.
func Infof(format string, args ...interface{}) {
	DefaultLogger.Infof(format, args...)
}

// Warnf logs a warning message using DefaultLogger.
func Warnf(format string, args ...interface{}) {
	DefaultLogger.Warnf(format, args...)
}

// Errorf logs an error message using DefaultLogger.
func Errorf(format string, args ...interface{}) {
	DefaultLogger.Errorf(format, args...)
}

// Printf is a convenience wrapper that logs at Info level.
// It replaces standard log.Printf usage.
func Printf(format string, args ...interface{}) {
	DefaultLogger.Infof(strings.TrimSpace(format), args...)
}
