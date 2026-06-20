package api

import (
	"encoding/json"
	"log"
	"net/http"
	"runtime"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// WSMessage is a message sent over a WebSocket channel.
type WSMessage struct {
	Channel string      `json:"channel"`
	Data    interface{} `json:"data"`
}

// WSClient represents a single WebSocket connection.
type WSClient struct {
	conn *websocket.Conn
	send chan []byte
	subs map[string]bool
}

// WSHub manages all WebSocket clients and channel subscriptions.
type WSHub struct {
	mu         sync.RWMutex
	clients    map[*WSClient]bool
	channels   map[string]map[*WSClient]bool
	register   chan *WSClient
	unregister chan *WSClient
	broadcast  chan WSMessage
	upgrader   websocket.Upgrader
}

// NewWSHub creates a new WebSocket hub and starts its run loop.
func NewWSHub() *WSHub {
	h := &WSHub{
		clients:    make(map[*WSClient]bool),
		channels:   make(map[string]map[*WSClient]bool),
		register:   make(chan *WSClient, 256),
		unregister: make(chan *WSClient, 256),
		broadcast:  make(chan WSMessage, 256),
	}
	go h.run()
	go h.heartbeat()
	return h
}

func (h *WSHub) run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
				for ch := range client.subs {
					if subs, ok := h.channels[ch]; ok {
						delete(subs, client)
					}
				}
			}
			h.mu.Unlock()

		case msg := <-h.broadcast:
			h.mu.RLock()
			if subs, ok := h.channels[msg.Channel]; ok {
				data, _ := json.Marshal(msg)
				for client := range subs {
					select {
					case client.send <- data:
					default:
					}
				}
			}
			h.mu.RUnlock()
		}
	}
}

// heartbeat pushes system stats to system channel periodically.
func (h *WSHub) heartbeat() {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		var m runtime.MemStats
		runtime.ReadMemStats(&m)
		h.Broadcast("system", map[string]interface{}{
			"goroutines": runtime.NumGoroutine(),
			"heap_mb":    m.HeapAlloc / 1024 / 1024,
			"time":       time.Now().Unix(),
		})
	}
}

// Broadcast sends a message to all clients subscribed to a channel.
func (h *WSHub) Broadcast(channel string, data interface{}) {
	h.broadcast <- WSMessage{Channel: channel, Data: data}
}

// HandleWebSocket upgrades an HTTP connection to WebSocket.
func (h *WSHub) HandleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("ws upgrade error: %v", err)
		return
	}

	client := &WSClient{
		conn: conn,
		send: make(chan []byte, 64),
		subs: make(map[string]bool),
	}

	h.register <- client

	// Write goroutine
	go func() {
		defer func() {
			conn.Close()
			h.unregister <- client
		}()
		for msg := range client.send {
			if err := conn.WriteMessage(websocket.TextMessage, msg); err != nil {
				return
			}
		}
	}()

	// Read goroutine — handles subscribe/unsubscribe messages
	go func() {
		defer conn.Close()
		for {
			_, message, err := conn.ReadMessage()
			if err != nil {
				break
			}
			var req struct {
				Action  string `json:"action"`
				Channel string `json:"channel"`
			}
			if json.Unmarshal(message, &req) != nil {
				continue
			}
			h.mu.Lock()
			switch req.Action {
			case "subscribe":
				client.subs[req.Channel] = true
				if h.channels[req.Channel] == nil {
					h.channels[req.Channel] = make(map[*WSClient]bool)
				}
				h.channels[req.Channel][client] = true
			case "unsubscribe":
				delete(client.subs, req.Channel)
				if subs, ok := h.channels[req.Channel]; ok {
					delete(subs, client)
				}
			}
			h.mu.Unlock()
		}
	}()
}

// TickerFeed pushes simulated market data to the ticker channel.
// Call this from outside to feed periodic price updates.
func (h *WSHub) TickerFeed(symbol string, price float64, change float64) {
	h.Broadcast("ticker", map[string]interface{}{
		"symbol": symbol,
		"price":  price,
		"change": change,
	})
}
