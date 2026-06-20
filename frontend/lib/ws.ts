// frontend/lib/ws.ts
import { WS_URL } from './constants'
import { useWSStore } from '@/stores/wsStore'

type WSCallback = (channel: string, data: any) => void

class WSClient {
  private ws: WebSocket | null = null
  private token: string | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private listeners: Map<string, Set<WSCallback>> = new Map()
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null

  connect(token: string) {
    if (this.ws?.readyState === WebSocket.OPEN) return
    this.token = token
    this.ws = new WebSocket(WS_URL)

    this.ws.onopen = () => {
      useWSStore.getState().setConnected(true)
      this.ws!.send(JSON.stringify({ type: 'auth', token: this.token }))
      this.heartbeatTimer = setInterval(() => {
        this.ws?.send(JSON.stringify({ type: 'ping' }))
      }, 15000)
      // Re-subscribe after reconnect
      const subs = useWSStore.getState().subscriptions
      subs.forEach((symbols, channel) => {
        this.ws!.send(JSON.stringify({ type: 'subscribe', channel, symbols: [...symbols] }))
      })
    }

    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'pong') {
          useWSStore.getState().setHeartbeat(Date.now())
          return
        }
        const channel = msg.channel || 'unknown'
        this.listeners.get(channel)?.forEach(cb => cb(channel, msg.data || msg))
        this.listeners.get('*')?.forEach(cb => cb(channel, msg.data || msg))
      } catch { /* ignore malformed JSON */ }
    }

    this.ws.onclose = () => {
      useWSStore.getState().setConnected(false)
      if (this.heartbeatTimer) { clearInterval(this.heartbeatTimer); this.heartbeatTimer = null }
      this.reconnectTimer = setTimeout(() => this.connect(this.token!), 3000)
    }
  }

  subscribe(channel: string, symbols: string[]) {
    useWSStore.getState().addSubscription(channel, symbols)
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'subscribe', channel, symbols }))
    }
  }

  unsubscribe(channel: string, symbols: string[]) {
    useWSStore.getState().removeSubscription(channel, symbols)
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'unsubscribe', channel, symbols }))
    }
  }

  on(channel: string, cb: WSCallback) {
    if (!this.listeners.has(channel)) this.listeners.set(channel, new Set())
    this.listeners.get(channel)!.add(cb)
    return () => { this.listeners.get(channel)?.delete(cb) }
  }

  disconnect() {
    if (this.heartbeatTimer) { clearInterval(this.heartbeatTimer); this.heartbeatTimer = null }
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null }
    useWSStore.getState().clearSubscriptions()
    useWSStore.getState().setConnected(false)
    this.ws?.close()
    this.ws = null
  }
}

export const wsClient = new WSClient()
