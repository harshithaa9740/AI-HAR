import React, { useState, useEffect } from 'react';
import {
  Settings2,
  Server,
  RefreshCw,
  Save,
  CheckCircle,
  Database,
  Sliders
} from 'lucide-react';
import { BackendConfigManager } from '../config/backendConfig';
import { apiService } from '../services/api';
import type { SystemSettingsData } from '../types';

export const SystemSettings: React.FC = () => {
  const currentConfig = BackendConfigManager.getConfig();

  const [backendIp, setBackendIp] = useState(currentConfig.ip);
  const [backendPort, setBackendPort] = useState(currentConfig.port.toString());
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.85);
  const [objectThreshold, setObjectThreshold] = useState(0.75);
  const [videoSource, setVideoSource] = useState<'mock' | 'file' | 'webcam'>('mock');
  const [recordingEnabled, setRecordingEnabled] = useState(true);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [logLevel, setLogLevel] = useState<'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'>('INFO');

  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: 'idle' | 'success' | 'error'; message: string }>({
    status: 'idle',
    message: '',
  });
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const data = await apiService.getSettings();
        if (data) {
          if (data.backend_ip) setBackendIp(data.backend_ip);
          if (data.backend_port) setBackendPort(data.backend_port.toString());
          if (data.confidence_threshold) setConfidenceThreshold(data.confidence_threshold);
          if (data.object_confidence_threshold) setObjectThreshold(data.object_confidence_threshold);
          if (data.video_source) setVideoSource(data.video_source);
          if (data.recording_enabled !== undefined) setRecordingEnabled(data.recording_enabled);
          if (data.voice_enabled !== undefined) setVoiceEnabled(data.voice_enabled);
          if (data.log_level) setLogLevel(data.log_level);
        }
      } catch {
        // Fallback to local
      }
    };
    loadSettings();
  }, []);

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult({ status: 'idle', message: 'Testing backend connection...' });

    const portNum = parseInt(backendPort, 10) || 8000;
    const testUrl = `http://${backendIp.trim()}:${portNum}/api/health`;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3500);

      const res = await fetch(testUrl, {
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (res.ok) {
        setTestResult({
          status: 'success',
          message: `Backend reachable at ${testUrl}! (Status: ${res.status})`,
        });
      } else {
        setTestResult({
          status: 'error',
          message: `Server returned error status ${res.status}.`,
        });
      }
    } catch {
      setTestResult({
        status: 'error',
        message: `Unable to connect to ${testUrl}. Check LAN / Wi-Fi IP address.`,
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveSettings = async () => {
    const portNum = parseInt(backendPort, 10) || 8000;

    // 1. Save in local config manager
    BackendConfigManager.setConfig({
      ip: backendIp.trim(),
      port: portNum,
      protocol: 'http',
      isConfigured: true,
    });

    // 2. Dispatch to backend if available
    const payload: Partial<SystemSettingsData> = {
      backend_ip: backendIp.trim(),
      backend_port: portNum,
      confidence_threshold: confidenceThreshold,
      object_confidence_threshold: objectThreshold,
      video_source: videoSource,
      recording_enabled: recordingEnabled,
      voice_enabled: voiceEnabled,
      log_level: logLevel,
      streaming_ip: backendIp.trim(),
      streaming_port: portNum,
    };

    try {
      await apiService.updateSettings(payload);
    } catch {
      // Local config updated
    }

    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header Bar */}
      <div
        className="glass-panel"
        style={{
          padding: '16px 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Settings2 size={20} color="var(--cyan)" />
            <h2 style={{ fontSize: '18px', color: '#fff', margin: 0 }}>
              System Configuration & Local Area Network Setup
            </h2>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
            Configure offline LAN endpoints, video sources, neural sensitivity thresholds, and audit logging.
          </p>
        </div>

        <button className="btn btn-cyan" onClick={handleSaveSettings}>
          <Save size={14} />
          <span>Save System Settings</span>
        </button>
      </div>

      {saveSuccess && (
        <div
          style={{
            padding: '10px 14px',
            background: 'var(--valid-bg)',
            border: '1px solid var(--valid)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--valid)',
            fontSize: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <CheckCircle size={16} />
          <span>System configuration successfully updated and saved locally!</span>
        </div>
      )}

      {/* Settings Sections Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        {/* SECTION 1: BACKEND LAN CONFIGURATION */}
        <div className="glass-panel tech-corner" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Server size={18} color="var(--cyan)" />
            <h3 style={{ fontSize: '15px', color: '#fff', margin: 0 }}>Backend LAN Server Endpoint</h3>
          </div>

          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>
            Points to the local machine hosting the FastAPI server. Never hardcoded.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 10 }}>
            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                SERVER IP ADDRESS
              </label>
              <input
                type="text"
                className="input-field font-mono"
                value={backendIp}
                onChange={(e) => setBackendIp(e.target.value)}
                placeholder="192.168.1.25"
              />
            </div>

            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                PORT
              </label>
              <input
                type="number"
                className="input-field font-mono"
                value={backendPort}
                onChange={(e) => setBackendPort(e.target.value)}
                placeholder="8000"
              />
            </div>
          </div>

          {/* Computed URLs Preview */}
          <div
            style={{
              padding: '10px',
              background: 'rgba(0, 0, 0, 0.35)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
            }}
          >
            <div>
              <span style={{ color: 'var(--cyan)' }}>REST Base:</span> http://{backendIp}:{backendPort}
            </div>
            <div>
              <span style={{ color: '#818cf8' }}>WebSocket:</span> ws://{backendIp}:{backendPort}/ws/events
            </div>
            <div>
              <span style={{ color: '#34d399' }}>Video Feed:</span> http://{backendIp}:{backendPort}/api/video/feed
            </div>
          </div>

          {/* Test Connection Button */}
          <button
            className="btn btn-secondary"
            onClick={handleTestConnection}
            disabled={isTesting}
            style={{ width: '100%' }}
          >
            <RefreshCw size={14} className={isTesting ? 'spin' : ''} />
            <span>{isTesting ? 'Pinging Server...' : 'Test Connection (GET /api/health)'}</span>
          </button>

          {testResult.status !== 'idle' && (
            <div
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                fontSize: '11px',
                background: testResult.status === 'success' ? 'var(--valid-bg)' : 'var(--critical-bg)',
                border: `1px solid ${testResult.status === 'success' ? 'var(--valid)' : 'var(--critical)'}`,
                color: testResult.status === 'success' ? 'var(--valid)' : 'var(--critical)',
              }}
            >
              {testResult.message}
            </div>
          )}
        </div>

        {/* SECTION 2: AI THRESHOLDS & VISION TUNING */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Sliders size={18} color="var(--cyan)" />
            <h3 style={{ fontSize: '15px', color: '#fff', margin: 0 }}>AI Confidence & Recognition Tuning</h3>
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: 4 }}>
              <span style={{ color: 'var(--text-secondary)' }}>Activity Recognition (HAR) Confidence</span>
              <strong className="font-mono" style={{ color: 'var(--cyan)' }}>{(confidenceThreshold * 100).toFixed(0)}%</strong>
            </div>
            <input
              type="range"
              min="0.5"
              max="0.99"
              step="0.01"
              value={confidenceThreshold}
              onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--cyan)' }}
            />
            <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
              Confidence below this threshold triggers a VERIFY_REQUIRED advisory.
            </span>
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: 4 }}>
              <span style={{ color: 'var(--text-secondary)' }}>Object Detector Confidence</span>
              <strong className="font-mono" style={{ color: '#a5b4fc' }}>{(objectThreshold * 100).toFixed(0)}%</strong>
            </div>
            <input
              type="range"
              min="0.5"
              max="0.99"
              step="0.01"
              value={objectThreshold}
              onChange={(e) => setObjectThreshold(parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: '#6366f1' }}
            />
          </div>

          <div>
            <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
              OPTICAL INGESTION SOURCE
            </label>
            <select
              className="input-field"
              value={videoSource}
              onChange={(e) => setVideoSource(e.target.value as any)}
            >
              <option value="mock">Simulated Space Station Camera Feed (Offline)</option>
              <option value="webcam">Physical USB / Integrated Camera Feed</option>
              <option value="file">Local Video Protocol File</option>
            </select>
          </div>
        </div>

        {/* SECTION 3: AUDIO, RECORDING & AUDIT */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Database size={18} color="var(--cyan)" />
            <h3 style={{ fontSize: '15px', color: '#fff', margin: 0 }}>Mission Recording & Voice Alerts</h3>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
            <div>
              <div style={{ fontSize: '13px', color: '#fff' }}>Local Video & Telemetry Recording</div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Record continuous MP4 session audit stream</div>
            </div>
            <input
              type="checkbox"
              checked={recordingEnabled}
              onChange={(e) => setRecordingEnabled(e.target.checked)}
              style={{ width: 18, height: 18, accentColor: 'var(--cyan)' }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
            <div>
              <div style={{ fontSize: '13px', color: '#fff' }}>Synthesized Voice Prompts</div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Spoken instructions for astronaut protocol steps</div>
            </div>
            <input
              type="checkbox"
              checked={voiceEnabled}
              onChange={(e) => setVoiceEnabled(e.target.checked)}
              style={{ width: 18, height: 18, accentColor: 'var(--cyan)' }}
            />
          </div>

          <div>
            <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
              MISSION AUDIT LOG LEVEL
            </label>
            <select
              className="input-field"
              value={logLevel}
              onChange={(e) => setLogLevel(e.target.value as any)}
            >
              <option value="DEBUG">DEBUG (All pose joint coordinates & frames)</option>
              <option value="INFO">INFO (Normal protocol transitions & alerts)</option>
              <option value="WARNING">WARNING (Only alerts & violations)</option>
              <option value="ERROR">ERROR (Only critical system faults)</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
};
