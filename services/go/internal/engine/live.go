package engine

import (
	"log"
	"sync"
	"time"
)

type TradingStatus string

const (
	TradingStopped TradingStatus = "stopped"
	TradingRunning TradingStatus = "running"
	TradingPaused  TradingStatus = "paused"
)

type LiveTradingRunner struct {
	mu       sync.RWMutex
	status   TradingStatus
	pipeline *Pipeline
	interval time.Duration
	stopCh   chan struct{}
}

func NewLiveTradingRunner(pipeline *Pipeline, interval time.Duration) *LiveTradingRunner {
	return &LiveTradingRunner{
		status:   TradingStopped,
		pipeline: pipeline,
		interval: interval,
	}
}

func (l *LiveTradingRunner) Start() error {
	l.mu.Lock()
	defer l.mu.Unlock()

	if l.status == TradingRunning {
		return nil
	}

	l.status = TradingRunning
	l.stopCh = make(chan struct{})
	go l.loop()
	log.Printf("live trading started (interval=%s)", l.interval)
	return nil
}

func (l *LiveTradingRunner) Stop() error {
	l.mu.Lock()
	defer l.mu.Unlock()

	if l.status != TradingRunning {
		return nil
	}

	l.status = TradingStopped
	close(l.stopCh)
	log.Print("live trading stopped")
	return nil
}

func (l *LiveTradingRunner) Status() TradingStatus {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.status
}

func (l *LiveTradingRunner) Portfolio() *Portfolio {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.pipeline.Portfolio
}

func (l *LiveTradingRunner) loop() {
	ticker := time.NewTicker(l.interval)
	defer ticker.Stop()

	for {
		select {
		case <-l.stopCh:
			return
		case <-ticker.C:
			l.mu.Lock()
			l.tick()
			l.mu.Unlock()
		}
	}
}

func (l *LiveTradingRunner) tick() {
	log.Print("live trading tick")
}
