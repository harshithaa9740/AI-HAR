import React, { useState, useEffect } from 'react';
import { Wifi, WifiOff, Radio, Settings, Clock, Server, ShieldCheck } from 'lucide-react';
import { BackendConfigManager } from '../config/backendConfig';
import { wsService, type WSConnectionStatus } from '../services/websocketService';
import { apiService } from '../services/api';

interface HeaderProps {
  onOpenConnectModal: () => void;
  onNavigateToSettings: () => void;
  activeSessionDuration?: string;
}

export const Header: React.FC<HeaderProps> = ({
  onOpenConnectModal,
  onNavigateToSettings,
  activeSessionDuration
}) => {
  const [config, setConfig] = useState(BackendConfigManager.getConfig());
  const [wsStatus, setWsStatus] = useState<WSConnectionStatus>('disconnected');
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const [currentTime, setCurrentTime] = useState<string>('');

  useEffect(() => {
    // Subscribe to config changes
    const unsubConfig = BackendConfigManager.subscribe((newConfig) => {
      setConfig(newConfig);
      checkHealth();
    });

    // Subscribe to WebSocket status
    const unsubWs = wsService.onStatusChange((status) => {
      setWsStatus(status);
    });

    // Check health periodically
    const checkHealth = async () => {
      try {
        const res = await apiService.getHealth();
        setIsBackendHealthy(res.status === 'ok' || res.status === 'healthy');
      } catch {
        setIsBackendHealthy(false);
      }
    };
    checkHealth();
    const healthInterval = window.setInterval(checkHealth, 10000);

    // Clock
    const timer = window.setInterval(() => {
      const now = new Date();
      setCurrentTime(now.toTimeString().split(' ')[0] + ' IST');
    }, 1000);

    return () => {
      unsubConfig();
      unsubWs();
      window.clearInterval(healthInterval);
      window.clearInterval(timer);
    };
  }, []);

  return (
    <header className="app-header">
      {/* Left: Branding & Offline Badge */}
      <div className="header-left">
        <div className="brand-link" style={{ cursor: 'pointer' }}>
          <img src="/orbital-logo.svg" alt="AURAVISION" className="brand-logo-img" />
          <div>
            <div className="brand-title">AURAVISION</div>
            <div className="brand-subtitle">ISRO • BAS EXPERIMENT VALIDATION</div>
          </div>
        </div>

        {/* Offline / LAN Badge */}
        <div className="badge badge-indigo" title="Zero cloud dependencies — strictly operational on local Wi-Fi / LAN">
          <ShieldCheck size={12} color="#818cf8" />
          <span>OFFLINE / LAN MODE</span>
        </div>
      </div>

      {/* Right: Telemetry Indicators & Settings */}
      <div className="header-right">
        {/* Time / MET */}
        <div className="badge badge-muted" style={{ padding: '4px 10px', fontSize: '12px' }}>
          <Clock size={13} style={{ marginRight: '4px' }} />
          <span>{activeSessionDuration ? `MET: ${activeSessionDuration}` : currentTime}</span>
        </div>

        {/* Backend IP Status (Clickable to change IP) */}
        <button
          onClick={onOpenConnectModal}
          className={`badge ${isBackendHealthy ? 'badge-cyan' : 'badge-warning'}`}
          style={{ cursor: 'pointer', padding: '5px 10px', border: '1px solid currentColor' }}
          title="Click to configure or test Backend Server IP address"
        >
          <Server size={12} />
          <span style={{ fontFamily: 'var(--font-mono)' }}>
            {config.ip}:{config.port}
          </span>
          <span
            className={`status-dot ${isBackendHealthy ? 'green' : 'amber'}`}
            style={{ width: 6, height: 6, marginLeft: 2 }}
          />
        </button>

        {/* WebSocket Status Indicator */}
        <div
          className={`badge ${
            wsStatus === 'connected' ? 'badge-valid' : wsStatus === 'connecting' ? 'badge-warning' : 'badge-muted'
          }`}
          title={
            wsStatus === 'connected'
              ? 'Real-time WebSocket event bus active'
              : wsStatus === 'connecting'
              ? 'Reconnecting to LAN WebSocket...'
              : 'WebSocket disconnected (Mock preview mode)'
          }
        >
          {wsStatus === 'connected' ? (
            <>
              <Radio size={12} className="pulse" />
              <span>WS LIVE</span>
            </>
          ) : wsStatus === 'connecting' ? (
            <>
              <Wifi size={12} />
              <span>WS SYNC...</span>
            </>
          ) : (
            <>
              <WifiOff size={12} />
              <span>WS OFFLINE</span>
            </>
          )}
        </div>

        {/* Settings Shortcut */}
        <button
          className="btn btn-secondary btn-icon"
          onClick={onNavigateToSettings}
          title="System Settings & LAN Configuration"
        >
          <Settings size={16} />
        </button>
      </div>
    </header>
  );
};
