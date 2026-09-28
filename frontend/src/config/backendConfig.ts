/**
 * AURAVISION — Dynamic LAN Backend Configuration Manager
 * Persists backend IP and Port in localStorage for local Wi-Fi / subnet connectivity.
 */

import type { BackendConfig } from '../types';

const STORAGE_KEY_IP = 'auravision_backend_ip';
const STORAGE_KEY_PORT = 'auravision_backend_port';
const STORAGE_KEY_CONFIGURED = 'auravision_backend_configured';

// Default to localhost, but allow setting to any LAN IPv4 address (e.g. 192.168.1.25)
const DEFAULT_IP = '127.0.0.1';
const DEFAULT_PORT = 8000;

export class BackendConfigManager {
  private static listeners: Array<(config: BackendConfig) => void> = [];

  static getConfig(): BackendConfig {
    if (typeof window === 'undefined') {
      return {
        ip: DEFAULT_IP,
        port: DEFAULT_PORT,
        protocol: 'http',
        isConfigured: false
      };
    }

    const savedIp = localStorage.getItem(STORAGE_KEY_IP);
    const savedPort = localStorage.getItem(STORAGE_KEY_PORT);
    const isConfigured = localStorage.getItem(STORAGE_KEY_CONFIGURED) === 'true';

    return {
      ip: savedIp || DEFAULT_IP,
      port: savedPort ? parseInt(savedPort, 10) : DEFAULT_PORT,
      protocol: 'http',
      isConfigured: isConfigured || !!savedIp
    };
  }

  static saveConfig(ip: string, port: number = DEFAULT_PORT): BackendConfig {
    const cleanIp = ip.trim().replace(/^https?:\/\//, '').replace(/\/.*$/, '').replace(/:\d+$/, '');
    const cleanPort = Math.max(1, Math.min(65535, port || DEFAULT_PORT));

    localStorage.setItem(STORAGE_KEY_IP, cleanIp);
    localStorage.setItem(STORAGE_KEY_PORT, cleanPort.toString());
    localStorage.setItem(STORAGE_KEY_CONFIGURED, 'true');

    const newConfig: BackendConfig = {
      ip: cleanIp,
      port: cleanPort,
      protocol: 'http',
      isConfigured: true
    };

    this.notify(newConfig);
    return newConfig;
  }

  static setConfig(config: Partial<BackendConfig>): BackendConfig {
    return this.saveConfig(config.ip || DEFAULT_IP, config.port || DEFAULT_PORT);
  }

  static getBaseUrl(): string {
    const config = this.getConfig();
    return `http://${config.ip}:${config.port}`;
  }

  static getApiBaseUrl(): string {
    return `${this.getBaseUrl()}/api`;
  }

  static getWsUrl(): string {
    const config = this.getConfig();
    return `ws://${config.ip}:${config.port}/ws/events`;
  }

  static getWebSocketUrl(): string {
    return this.getWsUrl();
  }

  static getVideoFeedUrl(): string {
    return `${this.getApiBaseUrl()}/video/feed`;
  }

  static subscribe(listener: (config: BackendConfig) => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private static notify(config: BackendConfig) {
    this.listeners.forEach(cb => {
      try {
        cb(config);
      } catch (err) {
        console.error('Error notifying config listener:', err);
      }
    });
  }
}
