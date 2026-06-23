package notify

import (
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
)

// AlertManager handles alert rule evaluation and notification delivery.
type AlertManager struct {
	mu         sync.Mutex
	lastAlerts map[string]time.Time // key: "strategyID:alertLevel", last sent time
	notifier   *Manager
}

// NewAlertManager creates a new AlertManager with the given notification manager.
func NewAlertManager(notifier *Manager) *AlertManager {
	return &AlertManager{
		lastAlerts: make(map[string]time.Time),
		notifier:   notifier,
	}
}

// CheckAndAlert evaluates drift result against rules and sends alerts.
func (a *AlertManager) CheckAndAlert(drift *engine.DriftResult) {
	if drift.AlertLevel == "OK" {
		return
	}

	// Rate limit: only one alert per strategy per level per hour
	key := fmt.Sprintf("%d:%s", drift.StrategyID, drift.AlertLevel)
	a.mu.Lock()
	lastTime, exists := a.lastAlerts[key]
	if exists && time.Since(lastTime) < time.Hour {
		a.mu.Unlock()
		return
	}
	a.lastAlerts[key] = time.Now()
	a.mu.Unlock()

	alertMsg := formatAlert(drift)
	log.Printf("ALERT [%s]: %s", drift.AlertLevel, alertMsg)

	// Deliver via notification manager
	if a.notifier != nil {
		level := LevelWarning
		switch drift.AlertLevel {
		case "CRITICAL":
			level = LevelError
		case "EMERGENCY":
			level = LevelError
		}
		msg := &Message{
			Level: level,
			Title: fmt.Sprintf("Strategy %d — %s", drift.StrategyID, drift.AlertLevel),
			Body:  alertMsg,
		}
		a.notifier.Send(msg)
	}
}

// GetAlertHistory returns recent alerts (placeholder; in production queries DB).
func (a *AlertManager) GetAlertHistory(strategyID int, limit int) []AlertRecord {
	return nil // DB-backed in production
}

// AlertRecord represents a persisted alert record.
type AlertRecord struct {
	StrategyID int
	Level      string
	Message    string
	CreatedAt  time.Time
}

func formatAlert(d *engine.DriftResult) string {
	icons := map[string]string{
		"WARNING":   "[WARN]",
		"CRITICAL":  "[CRIT]",
		"EMERGENCY": "[EMRG]",
	}
	icon := icons[d.AlertLevel]
	if icon == "" {
		icon = "[ALERT]"
	}

	return fmt.Sprintf(
		"%s Strategy %d | Drift: %.1f%% | Slippage: %.1fx | Drawdown: %.1f%% vs historical %.1f%% | IC: %.3f (%d days < 0.01)",
		icon,
		d.StrategyID,
		d.DriftPct*100,
		d.SlippageRatio,
		d.MaxDrawdownCurrent*100,
		d.MaxDrawdownHistorical*100,
		d.FactorICCurrent,
		d.FactorICDaysBelowThreshold,
	)
}
