package log

import (
	"bytes"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestNew_OutputsFormattedLines(t *testing.T) {
	var buf bytes.Buffer
	logger := New(LevelInfo, &buf)

	logger.Infof("server started on port %d", 8899)
	output := buf.String()

	assert.Contains(t, output, "INFO", "output should include level")
	assert.Contains(t, output, "server started on port 8899", "output should include message")
}

func TestLogger_Levels(t *testing.T) {
	tests := []struct {
		name  string
		logFn func(l *Logger)
		level string
	}{
		{"Info", func(l *Logger) { l.Infof("msg") }, "INFO"},
		{"Warn", func(l *Logger) { l.Warnf("msg") }, "WARN"},
		{"Error", func(l *Logger) { l.Errorf("msg") }, "ERROR"},
		{"Debug", func(l *Logger) { l.Debugf("msg") }, "DEBUG"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var buf bytes.Buffer
			logger := New(LevelDebug, &buf)
			tt.logFn(logger)
			assert.Contains(t, buf.String(), tt.level)
		})
	}
}

func TestLogger_EmptyMessageDoesNotPanic(t *testing.T) {
	var buf bytes.Buffer
	logger := New(LevelDebug, &buf)
	assert.NotPanics(t, func() {
		logger.Infof("")
		logger.Warnf("")
		logger.Errorf("")
		logger.Debugf("")
	})
}

func TestLogger_SpecialCharacters(t *testing.T) {
	var buf bytes.Buffer
	logger := New(LevelInfo, &buf)
	logger.Infof("user input: <script>alert(1)</script>")
	output := buf.String()
	assert.Contains(t, output, "<script>", "should not escape special characters")
}

func TestLogger_LevelFiltering(t *testing.T) {
	var buf bytes.Buffer
	logger := New(LevelWarn, &buf) // only WARN and above

	logger.Debugf("debug message")
	logger.Infof("info message")
	logger.Warnf("warn message")
	logger.Errorf("error message")

	output := buf.String()
	assert.NotContains(t, output, "debug message", "debug should be filtered")
	assert.NotContains(t, output, "info message", "info should be filtered")
	assert.Contains(t, output, "warn message")
	assert.Contains(t, output, "error message")
}

func TestLogger_Level(t *testing.T) {
	logger := New(LevelInfo, nil)
	assert.Equal(t, LevelInfo, logger.Level())

	logger.SetLevel(LevelDebug)
	assert.Equal(t, LevelDebug, logger.Level())
}

func TestLevel_String(t *testing.T) {
	assert.Equal(t, "DEBUG", LevelDebug.String())
	assert.Equal(t, "INFO", LevelInfo.String())
	assert.Equal(t, "WARN", LevelWarn.String())
	assert.Equal(t, "ERROR", LevelError.String())
}

func TestNewDefault(t *testing.T) {
	logger := NewDefault()
	assert.NotNil(t, logger)
	assert.Equal(t, LevelInfo, logger.Level())
}
