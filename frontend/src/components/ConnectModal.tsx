import React, { useState } from 'react';
import { Server, CheckCircle2, AlertTriangle, XCircle, RefreshCw, HelpCircle, X } from 'lucide-react';
import { BackendConfigManager } from '../config/backendConfig';

interface ConnectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConnected?: () => void;
}

export const ConnectModal: React.FC<ConnectModalProps> = ({
  isOpen,
  onClose,
  onConnected
}) => {
  const currentConfig = BackendConfigManager.getConfig();
  const [ip, setIp] = useState(currentConfig.ip);
  const [port, setPort] = useState(currentConfig.port.toString());
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    status: 'idle' | 'success' | 'error';
    message: string;
    details?: any;
  }>({
    status: 'idle',
    message: ''
  });
  const [showTroubleshooting, setShowTroubleshooting] = useState(false);

  if (!isOpen) return null;

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult({ status: 'idle', message: 'Pinging backend on local LAN...' });

    const portNum = parseInt(port, 10) || 8000;
    const testUrl = `http://${ip.trim()}:${portNum}/api/health`;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);

      const response = await fetch(testUrl, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json().catch(() => ({ status: 'ok' }));
        setTestResult({
          status: 'success',
          message: `Connection Verified! Backend active at ${testUrl}`,
          details: data
        });
      } else {
        setTestResult({
          status: 'error',
          message: `Backend responded with HTTP status ${response.status} (${response.statusText}).`,
          details: null
        });
      }
    } catch (err: any) {
      setTestResult({
        status: 'error',
        message: err.name === 'AbortError'
          ? `Connection timed out after 4 seconds to ${testUrl}.`
          : `Cannot reach ${testUrl}. Host is unreachable on this network.`,
        details: err.message
      });
      setShowTroubleshooting(true);
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveAndConnect = () => {
    const portNum = parseInt(port, 10) || 8000;
    BackendConfigManager.setConfig({
      ip: ip.trim(),
      port: portNum,
      protocol: 'http',
      isConfigured: true
    });

    if (onConnected) {
      onConnected();
    }
    onClose();
  };

  const handleUseMockMode = () => {
    BackendConfigManager.setConfig({
      ip: ip.trim() || '127.0.0.1',
      port: parseInt(port, 10) || 8000,
      protocol: 'http',
      isConfigured: true
    });
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content tech-corner" onClick={(e) => e.stopPropagation()} style={{ padding: '28px' }}>
        {/* Close Button */}
        <button
          onClick={onClose}
          className="btn-ghost"
          style={{ position: 'absolute', top: 18, right: 18, padding: 6, borderRadius: '50%' }}
        >
          <X size={18} />
        </button>

        {/* Modal Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 'var(--radius-md)',
              background: 'rgba(0, 229, 255, 0.1)',
              border: '1px solid var(--cyan)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--cyan)',
            }}
          >
            <Server size={22} />
          </div>
          <div>
            <h2 style={{ fontSize: '18px', color: '#fff', margin: 0 }}>Connect to AURAVISION Backend</h2>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
              Offline Local Area Network (Wi-Fi / LAN) Configuration
            </p>
          </div>
        </div>

        {/* Informational description */}
        <div
          style={{
            margin: '16px 0',
            padding: '12px 14px',
            background: 'rgba(99, 102, 241, 0.08)',
            border: '1px solid rgba(99, 102, 241, 0.25)',
            borderRadius: 'var(--radius-md)',
            fontSize: '12px',
            color: '#c7d2fe',
            lineHeight: 1.5,
          }}
        >
          AURAVISION runs 100% offline. Enter the IP address of the laptop or edge device running the FastAPI server on your local Wi-Fi.
        </div>

        {/* Form Fields */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
              Backend IPv4 Address
            </label>
            <input
              type="text"
              className="input-field font-mono"
              placeholder="e.g. 192.168.1.25"
              value={ip}
              onChange={(e) => setIp(e.target.value)}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
              Port
            </label>
            <input
              type="number"
              className="input-field font-mono"
              placeholder="8000"
              value={port}
              onChange={(e) => setPort(e.target.value)}
            />
          </div>
        </div>

        {/* Quick IP Presets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Presets:</span>
          {['127.0.0.1', '192.168.1.25', '192.168.0.100', '10.0.0.15'].map((preset) => (
            <button
              key={preset}
              type="button"
              className="badge badge-muted"
              style={{ cursor: 'pointer', background: 'rgba(255, 255, 255, 0.04)' }}
              onClick={() => setIp(preset)}
            >
              {preset}
            </button>
          ))}
        </div>

        {/* Computed Preview */}
        <div
          style={{
            padding: '10px 14px',
            background: 'rgba(0, 0, 0, 0.35)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: 'var(--text-secondary)',
            marginBottom: 18,
          }}
        >
          <div><strong style={{ color: 'var(--cyan)' }}>REST Base:</strong> http://{ip}:{port}</div>
          <div><strong style={{ color: '#818cf8' }}>WebSocket:</strong> ws://{ip}:{port}/ws/events</div>
          <div><strong style={{ color: '#34d399' }}>Video Feed:</strong> http://{ip}:{port}/api/video/feed</div>
        </div>

        {/* Test Result Banner */}
        {testResult.status !== 'idle' && (
          <div
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              marginBottom: 18,
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
              fontSize: '12px',
              background:
                testResult.status === 'success'
                  ? 'var(--valid-bg)'
                  : 'var(--critical-bg)',
              border: `1px solid ${
                testResult.status === 'success' ? 'var(--valid)' : 'var(--critical)'
              }`,
              color: testResult.status === 'success' ? '#34d399' : '#fb7185',
            }}
          >
            {testResult.status === 'success' ? (
              <CheckCircle2 size={18} style={{ flexShrink: 0, marginTop: 1 }} />
            ) : (
              <XCircle size={18} style={{ flexShrink: 0, marginTop: 1 }} />
            )}
            <div>
              <div style={{ fontWeight: 600 }}>{testResult.message}</div>
              {testResult.status === 'error' && (
                <button
                  type="button"
                  onClick={() => setShowTroubleshooting(!showTroubleshooting)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--cyan)',
                    cursor: 'pointer',
                    fontSize: '11px',
                    padding: '4px 0 0 0',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <HelpCircle size={12} />
                  {showTroubleshooting ? 'Hide local network tips' : 'Show LAN troubleshooting steps'}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Troubleshooting Accordion */}
        {showTroubleshooting && (
          <div
            style={{
              background: 'rgba(15, 23, 42, 0.85)',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
              marginBottom: 18,
              fontSize: '12px',
              color: 'var(--text-secondary)',
            }}
          >
            <div style={{ fontWeight: 600, color: 'var(--warning)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertTriangle size={14} />
              <span>Offline LAN Troubleshooting Checklist</span>
            </div>
            <ol style={{ paddingLeft: '18px', margin: 0, lineHeight: '1.6' }}>
              <li><strong>Same Local Network:</strong> Confirm this device and the backend laptop are on the same Wi-Fi or router subnet.</li>
              <li><strong>Verify IP Address:</strong> Open Command Prompt on the backend laptop and run <code style={{ color: 'var(--cyan)' }}>ipconfig</code> to confirm its IPv4 address.</li>
              <li><strong>Backend Running:</strong> Verify the backend is listening on 0.0.0.0, e.g.: <code style={{ color: 'var(--cyan)' }}>uvicorn app.main:app --host 0.0.0.0 --port 8000</code>.</li>
              <li><strong>Windows Firewall:</strong> Ensure Windows Firewall on the backend laptop permits incoming connections on TCP port 8000.</li>
              <li><strong>Fallback Preview:</strong> You can continue in Offline Preview Mode with high-fidelity mock data at any time.</li>
            </ol>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleTestConnection}
            disabled={isTesting}
          >
            <RefreshCw size={14} className={isTesting ? 'spin' : ''} />
            {isTesting ? 'Testing...' : 'Test Connection (GET /api/health)'}
          </button>

          <div style={{ display: 'flex', gap: 10 }}>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={handleUseMockMode}
              title="Use offline mock data for evaluation/demo"
            >
              Offline Preview Mode
            </button>
            <button
              type="button"
              className="btn btn-cyan"
              onClick={handleSaveAndConnect}
            >
              Save & Connect
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
