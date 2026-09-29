import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Pause,
  Square,
  RotateCcw,
  CheckCircle,
  AlertTriangle,
  AlertOctagon,
  Clock,
  Shield,
  Activity,
  Crosshair,
  Volume2,
  VolumeX,
  Sparkles
} from 'lucide-react';
import { BackendConfigManager } from '../config/backendConfig';
import { apiService } from '../services/api';
import { wsService } from '../services/websocketService';
import type {
  ExperimentProtocol,
  ExperimentSession,
  LiveTelemetry,
  ValidationAlert,
  ProtocolStep
} from '../types';
import { MOCK_PROTOCOL, MOCK_SESSION, MOCK_TELEMETRY, MOCK_ALERTS } from '../services/mockData';

export const LiveMission: React.FC = () => {
  const [protocol, setProtocol] = useState<ExperimentProtocol>(MOCK_PROTOCOL);
  const [session, setSession] = useState<ExperimentSession>(MOCK_SESSION);
  const [telemetry, setTelemetry] = useState<LiveTelemetry>(MOCK_TELEMETRY);
  const [alerts, setAlerts] = useState<ValidationAlert[]>(MOCK_ALERTS);
  const [elapsedSeconds, setElapsedSeconds] = useState(148);
  const [videoFeedError, setVideoFeedError] = useState(false);
  const [showSkeleton, setShowSkeleton] = useState(true);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const videoFeedUrl = BackendConfigManager.getVideoFeedUrl();

  // Load initial data from API or fall back to mock
  useEffect(() => {
    let mounted = true;

    const loadData = async () => {
      try {
        const protocols = await apiService.getExperiments();
        if (mounted && protocols.length > 0) {
          setProtocol(protocols[0]);
        }

        const sessions = await apiService.getSessions();
        if (mounted && sessions.length > 0) {
          setSession(sessions[0]);
        }
      } catch (err) {
        console.warn('Using offline mock dataset for mission view:', err);
      }
    };

    loadData();

    // Subscribe to WebSocket events
    const unsubWs = wsService.onMessage((msg) => {
      if (!mounted) return;

      if (msg.type === 'VALIDATION_ALERT' || msg.type === 'ALERT') {
        const newAlert: ValidationAlert = {
          id: 'alert-' + Date.now(),
          timestamp: new Date().toTimeString().split(' ')[0],
          type: msg.alert_type || msg.status || 'STEP_VALIDATED',
          title: msg.title || 'Protocol Event',
          message: msg.message || 'Action sequence updated',
          severity: msg.severity || 'valid',
          step_number: msg.step_number,
          observed_action: msg.observed_action,
          expected_action: msg.expected_action,
          confidence: msg.confidence
        };
        setAlerts((prev) => [newAlert, ...prev.slice(0, 19)]);
      }

      if (msg.type === 'TELEMETRY' && msg.data) {
        setTelemetry((prev) => ({ ...prev, ...msg.data }));
      }

      if (msg.type === 'SESSION_UPDATE' && msg.session) {
        setSession(msg.session);
      }
    });

    return () => {
      mounted = false;
      unsubWs();
    };
  }, []);

  // Elapsed time counter
  useEffect(() => {
    if (session.status !== 'RUNNING') return;

    const interval = window.setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => window.clearInterval(interval);
  }, [session.status]);

  // Fallback synthetic video feed renderer on canvas if live MJPEG is unavailable or during mock demo
  useEffect(() => {
    if (!videoFeedError) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let t = 0;

    const render = () => {
      t += 0.03;
      ctx.fillStyle = '#050a17';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Render subtle perspective grid (laboratory work bench)
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.12)';
      ctx.lineWidth = 1;
      for (let x = 0; x < canvas.width; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let y = 0; y < canvas.height; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      // Container ROI
      ctx.strokeStyle = 'rgba(0, 229, 255, 0.7)';
      ctx.fillStyle = 'rgba(0, 229, 255, 0.05)';
      ctx.lineWidth = 2;
      const boxX = 380 + Math.sin(t * 0.2) * 4;
      const boxY = 220;
      ctx.strokeRect(boxX, boxY, 180, 160);
      ctx.fillRect(boxX, boxY, 180, 160);
      ctx.fillStyle = 'var(--cyan)';
      ctx.font = '11px JetBrains Mono, monospace';
      ctx.fillText('TARGET CONTAINER ROI [98.2%]', boxX + 6, boxY - 8);

      // Tool ROI
      ctx.strokeStyle = 'rgba(16, 185, 129, 0.8)';
      ctx.fillStyle = 'rgba(16, 185, 129, 0.05)';
      const toolX = 140 + Math.cos(t * 0.4) * 8;
      const toolY = 180 + Math.sin(t * 0.4) * 6;
      ctx.strokeRect(toolX, toolY, 110, 130);
      ctx.fillRect(toolX, toolY, 110, 130);
      ctx.fillStyle = 'var(--valid)';
      ctx.fillText('STERILE TOOL [94.5%]', toolX + 6, toolY - 8);

      // Synthetic Pose Skeleton
      if (showSkeleton) {
        const headX = 260 + Math.sin(t * 0.5) * 5;
        const headY = 120 + Math.cos(t * 0.5) * 3;
        const shoulderX = headX;
        const shoulderY = headY + 50;
        const elbowX = shoulderX - 70 + Math.cos(t) * 15;
        const elbowY = shoulderY + 40 + Math.sin(t) * 10;
        const wristX = elbowX - 40 + Math.cos(t * 1.5) * 12;
        const wristY = elbowY + 45 + Math.sin(t * 1.5) * 8;

        ctx.strokeStyle = '#00e5ff';
        ctx.lineWidth = 3;
        ctx.beginPath();
        // Spine
        ctx.moveTo(headX, headY);
        ctx.lineTo(shoulderX, shoulderY);
        // Left Arm
        ctx.lineTo(elbowX, elbowY);
        ctx.lineTo(wristX, wristY);
        ctx.stroke();

        // Joint nodes
        [
          [headX, headY],
          [shoulderX, shoulderY],
          [elbowX, elbowY],
          [wristX, wristY]
        ].forEach(([x, y]) => {
          ctx.beginPath();
          ctx.arc(x, y, 5, 0, Math.PI * 2);
          ctx.fillStyle = '#00e5ff';
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        });

        // Astronaut Head Circle
        ctx.beginPath();
        ctx.arc(headX, headY, 18, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(0, 229, 255, 0.8)';
        ctx.stroke();
      }

      // Crosshairs in center
      ctx.strokeStyle = 'rgba(0, 229, 255, 0.3)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(canvas.width / 2 - 20, canvas.height / 2);
      ctx.lineTo(canvas.width / 2 + 20, canvas.height / 2);
      ctx.moveTo(canvas.width / 2, canvas.height / 2 - 20);
      ctx.lineTo(canvas.width / 2, canvas.height / 2 + 20);
      ctx.stroke();

      animId = requestAnimationFrame(render);
    };

    render();

    return () => cancelAnimationFrame(animId);
  }, [videoFeedError, showSkeleton]);

  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Session Control Handlers
  const handleStartSession = async () => {
    setActionInProgress('start');
    try {
      const updated = await apiService.startSession(session.id);
      setSession(updated);
    } catch {
      setSession((prev) => ({ ...prev, status: 'RUNNING' }));
    } finally {
      setActionInProgress(null);
    }
  };

  const handlePauseSession = async () => {
    setActionInProgress('pause');
    try {
      const updated = await apiService.pauseSession(session.id);
      setSession(updated);
    } catch {
      setSession((prev) => ({ ...prev, status: 'PAUSED' }));
    } finally {
      setActionInProgress(null);
    }
  };

  const handleResumeSession = async () => {
    setActionInProgress('resume');
    try {
      const updated = await apiService.resumeSession(session.id);
      setSession(updated);
    } catch {
      setSession((prev) => ({ ...prev, status: 'RUNNING' }));
    } finally {
      setActionInProgress(null);
    }
  };

  const handleStopSession = async () => {
    setActionInProgress('stop');
    try {
      const updated = await apiService.stopSession(session.id);
      setSession(updated);
    } catch {
      setSession((prev) => ({ ...prev, status: 'STOPPED' }));
    } finally {
      setActionInProgress(null);
    }
  };

  const handleResetSession = async () => {
    setActionInProgress('reset');
    try {
      const updated = await apiService.resetSession(session.id);
      setSession(updated);
      setElapsedSeconds(0);
    } catch {
      setSession((prev) => ({
        ...prev,
        status: 'RUNNING',
        current_step_number: 1,
        violations_count: 0,
        compliance_rate: 100
      }));
      setElapsedSeconds(0);
    } finally {
      setActionInProgress(null);
    }
  };

  // Helper to determine step status
  const getStepStatus = (step: ProtocolStep) => {
    if (step.step_number < session.current_step_number) {
      return 'completed';
    } else if (step.step_number === session.current_step_number) {
      return 'current';
    } else {
      return 'upcoming';
    }
  };

  const currentStepObj = protocol.steps.find((s) => s.step_number === session.current_step_number);
  const nextStepObj = protocol.steps.find((s) => s.step_number === session.current_step_number + 1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 1. TOP MISSION HEADER BAR */}
      <div
        className="glass-panel"
        style={{
          padding: '14px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 'var(--radius-md)',
              background: 'rgba(0, 229, 255, 0.1)',
              border: '1px solid var(--cyan)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--cyan)',
            }}
          >
            <Shield size={24} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h2 style={{ fontSize: '16px', color: '#fff', margin: 0 }}>{protocol.name}</h2>
              <span className="badge badge-cyan">{session.session_code}</span>
              <span
                className={`badge ${
                  session.status === 'RUNNING'
                    ? 'badge-valid'
                    : session.status === 'PAUSED'
                    ? 'badge-warning'
                    : 'badge-muted'
                }`}
              >
                <span
                  className={`status-dot ${
                    session.status === 'RUNNING' ? 'green pulse' : session.status === 'PAUSED' ? 'amber' : 'gray'
                  }`}
                  style={{ width: 6, height: 6 }}
                />
                {session.status}
              </span>
            </div>

            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', gap: 16, marginTop: 4 }}>
              <span>Operator: <strong>{session.operator_id || 'Astronaut Specialist 1'}</strong></span>
              <span>Protocol ID: <strong className="font-mono">{protocol.id}</strong></span>
              <span>Compliance: <strong style={{ color: 'var(--valid)' }}>{session.compliance_rate || 96.5}%</strong></span>
            </div>
          </div>
        </div>

        {/* Timer & Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div
            style={{
              background: 'rgba(0, 0, 0, 0.4)',
              border: '1px solid var(--border-subtle)',
              padding: '6px 14px',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Clock size={16} color="var(--cyan)" />
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                SESSION ELAPSED
              </span>
              <span className="font-mono" style={{ fontSize: '18px', fontWeight: 700, color: 'var(--cyan)' }}>
                {formatTime(elapsedSeconds)}
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            {session.status !== 'RUNNING' ? (
              <button
                className="btn btn-primary"
                onClick={session.status === 'PAUSED' ? handleResumeSession : handleStartSession}
                disabled={actionInProgress !== null}
              >
                <Play size={14} />
                <span>{session.status === 'PAUSED' ? 'Resume' : 'Start'}</span>
              </button>
            ) : (
              <button
                className="btn btn-secondary"
                onClick={handlePauseSession}
                disabled={actionInProgress !== null}
              >
                <Pause size={14} />
                <span>Pause</span>
              </button>
            )}

            <button
              className="btn btn-danger"
              onClick={handleStopSession}
              disabled={actionInProgress !== null || session.status === 'STOPPED'}
            >
              <Square size={14} />
              <span>Stop</span>
            </button>

            <button
              className="btn btn-ghost"
              onClick={handleResetSession}
              disabled={actionInProgress !== null}
              title="Reset procedure stepper to Step 1"
            >
              <RotateCcw size={14} />
              <span>Reset</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. MAIN WORKSPACE: 2-COLUMN GRID (CAMERA + TELEMETRY | STEPPER + ALERTS) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.8fr) minmax(0, 1.2fr)', gap: 16 }}>
        {/* LEFT COLUMN: CAMERA FEED + HUD OVERLAY + METRICS */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* CAMERA FEED CONTAINER */}
          <div className="camera-container glass-panel tech-corner" style={{ height: '420px' }}>
            {/* Top HUD Overlay */}
            <div className="camera-overlay-top">
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <div className="camera-hud-badge">
                  <span className="status-dot green pulse" style={{ width: 8, height: 8 }} />
                  <span style={{ fontWeight: 700, color: '#fff' }}>CAM-01 • AIRLOCK OVERHEAD</span>
                </div>
                <div className="camera-hud-badge">
                  <span>{telemetry.processingFps.toFixed(1)} FPS</span>
                </div>
                <div className="camera-hud-badge">
                  <span>LATENCY: {telemetry.latencyMs}ms</span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 6, pointerEvents: 'auto' }}>
                <button
                  className={`btn btn-icon ${showSkeleton ? 'btn-cyan' : 'btn-secondary'}`}
                  style={{ width: 30, height: 30 }}
                  onClick={() => setShowSkeleton(!showSkeleton)}
                  title="Toggle Pose Skeleton"
                >
                  <Activity size={14} />
                </button>
                <button
                  className={`btn btn-icon ${showBoundingBoxes ? 'btn-cyan' : 'btn-secondary'}`}
                  style={{ width: 30, height: 30 }}
                  onClick={() => setShowBoundingBoxes(!showBoundingBoxes)}
                  title="Toggle Bounding Boxes"
                >
                  <Crosshair size={14} />
                </button>
                <button
                  className="btn btn-icon btn-secondary"
                  style={{ width: 30, height: 30 }}
                  onClick={() => setAudioEnabled(!audioEnabled)}
                  title={audioEnabled ? 'Mute Voice Alerts' : 'Unmute Voice Alerts'}
                >
                  {audioEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
                </button>
              </div>
            </div>

            {/* MJPEG Live Stream or Synthetic Fallback */}
            {!videoFeedError ? (
              <img
                src={videoFeedUrl}
                alt="AURAVISION Live Camera Feed"
                className="camera-feed"
                onError={() => {
                  console.warn('MJPEG stream unreachable, falling back to synthetic simulator canvas');
                  setVideoFeedError(true);
                }}
              />
            ) : (
              <canvas
                ref={canvasRef}
                width={720}
                height={420}
                style={{ width: '100%', height: '100%', display: 'block' }}
              />
            )}

            {/* Bottom HUD Overlay */}
            <div className="camera-overlay-bottom">
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <div
                  className="camera-hud-badge"
                  style={{
                    background: 'rgba(0, 229, 255, 0.15)',
                    border: '1px solid var(--cyan)',
                    color: 'var(--cyan)',
                    fontWeight: 700,
                  }}
                >
                  <span>ACTION: {telemetry.currentAction.replace(/_/g, ' ')}</span>
                  <span style={{ color: '#fff' }}>({(telemetry.harConfidence * 100).toFixed(1)}%)</span>
                </div>

                <div className="camera-hud-badge">
                  <span>DETECTED: {telemetry.detectedObjects.join(', ')}</span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                {telemetry.isRecording && (
                  <div
                    className="camera-hud-badge"
                    style={{ background: 'rgba(244, 63, 94, 0.2)', border: '1px solid var(--critical)', color: 'var(--critical)' }}
                  >
                    <span className="status-dot red pulse" style={{ width: 8, height: 8 }} />
                    <span>REC {telemetry.recordingDuration}</span>
                  </div>
                )}
                <div className="camera-hud-badge">
                  <span>JOINTS: {telemetry.jointCount}</span>
                </div>
              </div>
            </div>
          </div>

          {/* REAL-TIME METRICS & TELEMETRY GRID */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
              gap: 12,
            }}
          >
            <div className="glass-panel" style={{ padding: '12px 14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>PROCESSING FPS</div>
              <div className="font-mono" style={{ fontSize: '18px', fontWeight: 700, color: 'var(--cyan)' }}>
                {telemetry.processingFps.toFixed(1)} <span style={{ fontSize: '11px' }}>FPS</span>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Ingest: {telemetry.ingestionFps} FPS</div>
            </div>

            <div className="glass-panel" style={{ padding: '12px 14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>INFERENCE LATENCY</div>
              <div className="font-mono" style={{ fontSize: '18px', fontWeight: 700, color: '#a5b4fc' }}>
                {telemetry.latencyMs} <span style={{ fontSize: '11px' }}>ms</span>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--valid)' }}>Target: &lt; 50ms</div>
            </div>

            <div className="glass-panel" style={{ padding: '12px 14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>FRAMES PROCESSED</div>
              <div className="font-mono" style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc' }}>
                {telemetry.framesProcessed.toLocaleString()}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Dropped: {telemetry.framesDropped}</div>
            </div>

            <div className="glass-panel" style={{ padding: '12px 14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>CAMERA HEALTH</div>
              <div className="font-mono" style={{ fontSize: '16px', fontWeight: 700, color: 'var(--valid)', display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                <span className="status-dot green" />
                <span>ONLINE</span>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>USB 3.0 / MJPEG</div>
            </div>

            <div className="glass-panel" style={{ padding: '12px 14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>AI HAR ENGINE</div>
              <div className="font-mono" style={{ fontSize: '14px', fontWeight: 700, color: 'var(--cyan)', marginTop: 2 }}>
                YOLOv8 + POSE
              </div>
              <div style={{ fontSize: '10px', color: 'var(--valid)' }}>Inference Active</div>
            </div>
          </div>

          {/* RECENT ALERTS FEED */}
          <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 style={{ fontSize: '14px', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertTriangle size={15} color="var(--cyan)" />
                <span>Live Action Verification & Alerts</span>
              </h3>
              <span className="badge badge-muted font-mono">{alerts.length} events</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: '200px', overflowY: 'auto' }}>
              {alerts.map((al) => {
                const isCrit = al.severity === 'critical';
                const isWarn = al.severity === 'warning';
                const isValid = al.severity === 'valid';

                return (
                  <div
                    key={al.id}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-md)',
                      background: isValid
                        ? 'var(--valid-bg)'
                        : isWarn
                        ? 'var(--warning-bg)'
                        : isCrit
                        ? 'var(--critical-bg)'
                        : 'rgba(255, 255, 255, 0.03)',
                      border: `1px solid ${
                        isValid ? 'rgba(16, 185, 129, 0.4)' : isWarn ? 'rgba(245, 158, 11, 0.4)' : 'rgba(244, 63, 94, 0.4)'
                      }`,
                    }}
                  >
                    {isValid ? (
                      <CheckCircle size={16} color="var(--valid)" style={{ flexShrink: 0, marginTop: 2 }} />
                    ) : isWarn ? (
                      <AlertTriangle size={16} color="var(--warning)" style={{ flexShrink: 0, marginTop: 2 }} />
                    ) : (
                      <AlertOctagon size={16} color="var(--critical)" style={{ flexShrink: 0, marginTop: 2 }} />
                    )}

                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontWeight: 600, fontSize: '12px', color: '#fff' }}>{al.title}</span>
                        <span className="font-mono" style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                          {al.timestamp}
                        </span>
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: 2 }}>
                        {al.message}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: PROCEDURE VALIDATION STEPPER & GUIDANCE */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* PROMINENT NEXT-STEP GUIDANCE BOX */}
          <div
            className="glass-panel"
            style={{
              padding: '16px',
              border: '1px solid var(--border-bright)',
              background: 'linear-gradient(135deg, rgba(0, 229, 255, 0.08) 0%, rgba(99, 102, 241, 0.1) 100%)',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Sparkles size={16} color="var(--cyan)" />
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  letterSpacing: '0.1em',
                  color: 'var(--cyan)',
                  textTransform: 'uppercase',
                }}
              >
                EXPECTED NEXT INSTRUCTION
              </span>
            </div>

            <div style={{ fontSize: '16px', fontWeight: 700, color: '#ffffff', marginBottom: 4 }}>
              Step {session.current_step_number}: {currentStepObj?.display_name || 'Verify Action'}
            </div>

            <div style={{ fontSize: '12px', color: '#cbd5e1', lineHeight: 1.5, marginBottom: 12 }}>
              {currentStepObj?.description}
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 8,
                background: 'rgba(0, 0, 0, 0.35)',
                padding: '10px',
                borderRadius: 'var(--radius-md)',
                fontSize: '11px',
              }}
            >
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Expected Objects:</span>
                <div style={{ fontWeight: 600, color: 'var(--cyan)' }}>
                  {currentStepObj?.expected_objects.join(', ') || 'None'}
                </div>
              </div>

              <div>
                <span style={{ color: 'var(--text-muted)' }}>Upcoming Action:</span>
                <div style={{ fontWeight: 600, color: '#a5b4fc' }}>
                  {nextStepObj ? `Step ${nextStepObj.step_number}: ${nextStepObj.display_name}` : 'Protocol Completion'}
                </div>
              </div>
            </div>
          </div>

          {/* PROCEDURE STEPPER CARD */}
          <div className="glass-panel" style={{ padding: '20px', flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
              <div>
                <h3 style={{ fontSize: '15px', color: '#fff', margin: 0 }}>BAS Protocol Validation Stepper</h3>
                <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
                  Sequential execution enforcement • Zero skipped steps permitted
                </p>
              </div>
              <span className="badge badge-cyan font-mono">
                {session.current_step_number - 1} / {protocol.steps_count} Completed
              </span>
            </div>

            {/* Stepper items */}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {protocol.steps.map((st, index) => {
                const status = getStepStatus(st);
                const isLast = index === protocol.steps.length - 1;

                return (
                  <div key={st.step_number} className="procedure-step-item">
                    {/* Vertical connecting line */}
                    {!isLast && (
                      <div
                        className={`procedure-line ${
                          session.current_step_number > st.step_number ? 'completed' : ''
                        }`}
                      />
                    )}

                    {/* Step Node Circle */}
                    <div className={`step-node ${status}`}>
                      {status === 'completed' ? (
                        <CheckCircle size={16} />
                      ) : (
                        <span>{st.step_number}</span>
                      )}
                    </div>

                    {/* Step Content */}
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span
                          style={{
                            fontWeight: status === 'current' ? 700 : 600,
                            fontSize: '13px',
                            color:
                              status === 'completed'
                                ? 'var(--valid)'
                                : status === 'current'
                                ? 'var(--cyan)'
                                : 'var(--text-muted)',
                          }}
                        >
                          {st.display_name}
                        </span>

                        <span
                          className={`badge ${
                            status === 'completed'
                              ? 'badge-valid'
                              : status === 'current'
                              ? 'badge-cyan'
                              : 'badge-muted'
                          }`}
                          style={{ fontSize: '10px' }}
                        >
                          {status === 'completed'
                            ? 'VALIDATED'
                            : status === 'current'
                            ? 'IN PROGRESS'
                            : 'PENDING'}
                        </span>
                      </div>

                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: 2 }}>
                        {st.description}
                      </div>

                      <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                        {st.expected_objects.map((obj) => (
                          <span
                            key={obj}
                            style={{
                              fontSize: '10px',
                              padding: '2px 6px',
                              borderRadius: 'var(--radius-sm)',
                              background: 'rgba(255, 255, 255, 0.05)',
                              color: 'var(--text-muted)',
                              fontFamily: 'var(--font-mono)',
                            }}
                          >
                            {obj}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
