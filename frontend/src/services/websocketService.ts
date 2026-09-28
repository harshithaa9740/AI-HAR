/**
 * AURAVISION — WebSocket Client
 * Real-time event streaming over Local Area Network (ws://<IP>:8000/ws/events)
 * Fully offline-capable with auto-reconnection and event dispatching.
 */

import { BackendConfigManager } from '../config/backendConfig';

export type WSConnectionStatus = 'connected' | 'connecting' | 'disconnected';

export interface WSEventMessage {
  type: string;
  session_id?: string;
  timestamp?: string;
  data?: any;
  [key: string]: any;
}

type MessageListener = (event: WSEventMessage) => void;
type StatusListener = (status: WSConnectionStatus) => void;

class WebSocketService {
  private socket: WebSocket | null = null;
  private status: WSConnectionStatus = 'disconnected';
  private messageListeners: Set<MessageListener> = new Set();
  private statusListeners: Set<StatusListener> = new Set();
  private reconnectTimer: number | null = null;
  private reconnectAttempts = 0;
  private maxReconnectDelay = 8000;
  private isIntentionallyClosed = false;

  constructor() {
    // Listen for config changes to reconnect if IP/port updates
    BackendConfigManager.subscribe(() => {
      this.reconnect();
    });
  }

  public getStatus(): WSConnectionStatus {
    return this.status;
  }

  public connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isIntentionallyClosed = false;
    this.setStatus('connecting');

    const wsUrl = BackendConfigManager.getWebSocketUrl();

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.setStatus('connected');
        this.reconnectAttempts = 0;
        if (this.reconnectTimer) {
          window.clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.socket.onmessage = (event: MessageEvent) => {
        try {
          const parsed: WSEventMessage = JSON.parse(event.data);
          this.notifyMessageListeners(parsed);
        } catch (err) {
          console.warn('[AURAVISION WS] Non-JSON message received:', event.data);
          this.notifyMessageListeners({ type: 'RAW_TEXT', data: event.data });
        }
      };

      this.socket.onerror = () => {
        // WebSocket error in offline/LAN setup: log quietly and attempt reconnect
        console.warn('[AURAVISION WS] Connection notice: ws unreachable on LAN');
      };

      this.socket.onclose = () => {
        this.setStatus('disconnected');
        this.socket = null;
        if (!this.isIntentionallyClosed) {
          this.scheduleReconnect();
        }
      };
    } catch (err) {
      this.setStatus('disconnected');
      if (!this.isIntentionallyClosed) {
        this.scheduleReconnect();
      }
    }
  }

  public disconnect(): void {
    this.isIntentionallyClosed = true;
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.setStatus('disconnected');
  }

  public reconnect(): void {
    this.disconnect();
    this.reconnectAttempts = 0;
    this.connect();
  }

  public send(data: any): boolean {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(typeof data === 'string' ? data : JSON.stringify(data));
      return true;
    }
    return false;
  }

  public onMessage(listener: MessageListener): () => void {
    this.messageListeners.add(listener);
    return () => this.messageListeners.delete(listener);
  }

  public onStatusChange(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    listener(this.status);
    return () => this.statusListeners.delete(listener);
  }

  private setStatus(newStatus: WSConnectionStatus): void {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.statusListeners.forEach((listener) => {
        try {
          listener(newStatus);
        } catch (e) {
          console.error('[AURAVISION WS] Listener error:', e);
        }
      });
    }
  }

  private notifyMessageListeners(message: WSEventMessage): void {
    this.messageListeners.forEach((listener) => {
      try {
        listener(message);
      } catch (e) {
        console.error('[AURAVISION WS] Event dispatch error:', e);
      }
    });
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;

    // Exponential backoff: 1s, 2s, 4s, 8s max
    const delay = Math.min(1000 * Math.pow(1.8, this.reconnectAttempts), this.maxReconnectDelay);
    this.reconnectAttempts++;

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }
}

export const wsService = new WebSocketService();
