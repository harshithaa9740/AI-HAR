import React, { useState, useEffect } from 'react';
import {
  Activity,
  ShieldCheck,
  Cpu,
  Video,
  AlertTriangle,
  Clock,
  ArrowRight,
  TrendingUp,
  Server,
  PlaySquare,
  FlaskConical
} from 'lucide-react';
import { apiService } from '../services/api';
import type { ExperimentSession, ValidationAlert, AIModelStatus } from '../types';
import { MOCK_SESSION, MOCK_ALERTS, MOCK_MODEL_STATUS } from '../services/mockData';

interface OverviewProps {
  onNavigate: (page: any) => void;
}

export const Overview: React.FC<OverviewProps> = ({ onNavigate }) => {
  const [session, setSession] = useState<ExperimentSession>(MOCK_SESSION);
  const [alerts, setAlerts] = useState<ValidationAlert[]>(MOCK_ALERTS);
  const [modelStatus, setModelStatus] = useState<AIModelStatus>(MOCK_MODEL_STATUS);
  const [recentSessions, setRecentSessions] = useState<ExperimentSession[]>([MOCK_SESSION]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const sessions = await apiService.getSessions();
        if (sessions.length > 0) {
          setRecentSessions(sessions);
          setSession(sessions[0]);
        }
        const model = await apiService.getActiveModel();
        if (model) setModelStatus(model);
      } catch {
        // Fallback to mock
      }
    };
    fetchData();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Top Welcome & Mission Status Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '24px',
          background: 'linear-gradient(135deg, rgba(6, 11, 24, 0.95) 0%, rgba(13, 27, 62, 0.8) 100%)',
          border: '1px solid var(--border-bright)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span className="badge badge-cyan">MISSION CONTROL READY</span>
            <span className="badge badge-indigo">OFFLINE LAN DEPLOYMENT</span>
          </div>
          <h1 style={{ fontSize: '24px', color: '#fff', margin: '0 0 6px 0' }}>
            AURAVISION Operational Command
          </h1>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '640px', fontSize: '13px', margin: 0 }}>
            Automated Human Activity Recognition & Bio-Astronautics (BAS) Experiment Protocol Verification for zero-error space science workflows.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-cyan" onClick={() => onNavigate('live-mission')}>
            <Activity size={16} />
            <span>Open Live Mission Feed</span>
          </button>
          <button className="btn btn-secondary" onClick={() => onNavigate('demo-mode')}>
            <PlaySquare size={16} />
            <span>Launch Demo Simulation</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
        {/* Compliance Rate Card */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>PROTOCOL COMPLIANCE</div>
              <div className="font-mono" style={{ fontSize: '28px', fontWeight: 700, color: 'var(--valid)', marginTop: 4 }}>
                {session.compliance_rate || 96.5}%
              </div>
            </div>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                background: 'var(--valid-bg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--valid)',
              }}
            >
              <ShieldCheck size={20} />
            </div>
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: 8 }}>
            0 Critical sequence violations in active run
          </div>
        </div>

        {/* Active Session Status */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>ACTIVE SESSION</div>
              <div className="font-mono" style={{ fontSize: '20px', fontWeight: 700, color: '#fff', marginTop: 6 }}>
                {session.session_code}
              </div>
            </div>
            <span className="badge badge-valid">
              <span className="status-dot green pulse" style={{ width: 6, height: 6 }} />
              {session.status}
            </span>
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: 8 }}>
            Step {session.current_step_number} of 6 in progress
          </div>
        </div>

        {/* AI Model Health */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>AI INFERENCE ENGINE</div>
              <div className="font-mono" style={{ fontSize: '18px', fontWeight: 700, color: 'var(--cyan)', marginTop: 6 }}>
                {modelStatus.model_name}
              </div>
            </div>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                background: 'rgba(0, 229, 255, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--cyan)',
              }}
            >
              <Cpu size={20} />
            </div>
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: 8 }}>
            Device: <strong style={{ color: '#fff' }}>{modelStatus.device}</strong> • Latency: {modelStatus.avg_latency_ms}ms
          </div>
        </div>

        {/* Camera Sensor Health */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>OPTICAL SENSORS</div>
              <div className="font-mono" style={{ fontSize: '18px', fontWeight: 700, color: '#a5b4fc', marginTop: 6 }}>
                CAM-01 / CAM-02
              </div>
            </div>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                background: 'var(--indigo-bg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--indigo)',
              }}
            >
              <Video size={20} />
            </div>
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: 8 }}>
            30.0 FPS Ingestion • Low-noise laboratory lens
          </div>
        </div>
      </div>

      {/* Charts & Activity Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.8fr) minmax(0, 1.2fr)', gap: 16 }}>
        {/* Telemetry Real-Time Mini Chart (SVG based) */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ fontSize: '15px', color: '#fff', margin: 0 }}>System Telemetry & Latency Profile</h3>
              <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
                Offline inference latency and frame delivery consistency
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <span className="badge badge-cyan">FPS: 29.8</span>
              <span className="badge badge-indigo">LATENCY: 34ms</span>
            </div>
          </div>

          {/* SVG Telemetry Line Chart */}
          <div
            style={{
              height: '140px',
              width: '100%',
              background: 'rgba(0, 0, 0, 0.4)',
              borderRadius: 'var(--radius-md)',
              padding: '10px',
              position: 'relative',
            }}
          >
            <svg viewBox="0 0 500 120" style={{ width: '100%', height: '100%', overflow: 'visible' }}>
              <defs>
                <linearGradient id="cyanGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00e5ff" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#00e5ff" stopOpacity="0.0" />
                </linearGradient>
              </defs>
              {/* Grid lines */}
              <line x1="0" y1="30" x2="500" y2="30" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
              <line x1="0" y1="60" x2="500" y2="60" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
              <line x1="0" y1="90" x2="500" y2="90" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />

              {/* Area */}
              <polygon
                points="0,100 30,85 70,88 110,65 150,70 190,45 230,50 270,40 310,48 350,38 390,42 430,35 470,36 500,32 500,120 0,120"
                fill="url(#cyanGrad)"
              />
              {/* Line */}
              <polyline
                fill="none"
                stroke="#00e5ff"
                strokeWidth="2.5"
                points="0,100 30,85 70,88 110,65 150,70 190,45 230,50 270,40 310,48 350,38 390,42 430,35 470,36 500,32"
              />
            </svg>
            <div
              style={{
                position: 'absolute',
                bottom: '6px',
                right: '12px',
                fontSize: '10px',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              Continuous 60s window • 0 frame jitter
            </div>
          </div>

          {/* Quick Actions */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginTop: 4 }}>
            <button className="btn btn-secondary" onClick={() => onNavigate('experiments')}>
              <FlaskConical size={14} />
              <span>Protocol Builder</span>
            </button>
            <button className="btn btn-secondary" onClick={() => onNavigate('sessions-audit')}>
              <Clock size={14} />
              <span>Audit Records</span>
            </button>
            <button className="btn btn-secondary" onClick={() => onNavigate('settings')}>
              <Server size={14} />
              <span>LAN Settings</span>
            </button>
          </div>
        </div>

        {/* Recent Protocol Events */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '15px', color: '#fff', margin: 0 }}>Recent Protocol Events</h3>
            <button
              className="btn btn-ghost"
              style={{ padding: '4px 8px', fontSize: '11px' }}
              onClick={() => onNavigate('sessions-audit')}
            >
              <span>View All</span>
              <ArrowRight size={12} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: '220px', overflowY: 'auto' }}>
            {alerts.slice(0, 4).map((al) => (
              <div
                key={al.id}
                style={{
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                  <strong style={{ color: '#fff' }}>{al.title}</strong>
                  <span className="font-mono" style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                    {al.timestamp}
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: 4 }}>
                  {al.message}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
