import React, { useState, useEffect } from 'react';
import {
  PlaySquare,
  Play,
  Square,
  CheckCircle,
  AlertTriangle,
  AlertOctagon,
  HelpCircle,
  Sparkles,
  Gauge,
  RotateCcw,
  Zap
} from 'lucide-react';
import { apiService } from '../services/api';
import type { DemoScenarioType, DemoScenarioDefinition } from '../types';
import { MOCK_DEMO_SCENARIOS } from '../services/mockData';

export const DemoMode: React.FC = () => {
  const [selectedScenario, setSelectedScenario] = useState<DemoScenarioType>('NORMAL');
  const [isRunning, setIsRunning] = useState(false);
  const [speedMultiplier, setSpeedMultiplier] = useState<number>(1);
  const [demoEvents, setDemoEvents] = useState<{ id: string; time: string; text: string; type: string }[]>([]);
  const [progressStep, setProgressStep] = useState(1);

  useEffect(() => {
    let timer: number;
    if (isRunning) {
      const intervalMs = Math.max(1200 / speedMultiplier, 400);

      timer = window.setInterval(() => {
        setProgressStep((prev) => {
          const next = prev + 1;
          const timestamp = new Date().toTimeString().split(' ')[0];

          if (selectedScenario === 'NORMAL') {
            if (next <= 6) {
              setDemoEvents((e) => [
                {
                  id: 'sim-' + Date.now(),
                  time: timestamp,
                  type: 'valid',
                  text: `Step ${next} Validated: Compliant action recognized.`,
                },
                ...e.slice(0, 15),
              ]);
            } else {
              setDemoEvents((e) => [
                {
                  id: 'sim-' + Date.now(),
                  time: timestamp,
                  type: 'valid',
                  text: 'EXPERIMENT COMPLETE: All 6 protocol steps successfully verified!',
                },
                ...e.slice(0, 15),
              ]);
              setIsRunning(false);
            }
          } else if (selectedScenario === 'SKIPPED_STEP') {
            if (next === 3) {
              setDemoEvents((e) => [
                {
                  id: 'sim-' + Date.now(),
                  time: timestamp,
                  type: 'critical',
                  text: 'STEP_SKIPPED: Astronaut initiated Step 4 (Place Sample) skipping Step 3 (Take Sample)!',
                },
                ...e.slice(0, 15),
              ]);
            } else {
              setDemoEvents((e) => [
                {
                  id: 'sim-' + Date.now(),
                  time: timestamp,
                  type: 'info',
                  text: `Step ${next} sequence check.`,
                },
                ...e.slice(0, 15),
              ]);
            }
          } else if (selectedScenario === 'OUT_OF_SEQUENCE') {
            if (next === 2) {
              setDemoEvents((e) => [
                {
                  id: 'sim-' + Date.now(),
                  time: timestamp,
                  type: 'critical',
                  text: 'OUT_OF_SEQUENCE: Attempted SEAL_CONTAINER prior to sample deposit!',
                },
                ...e.slice(0, 15),
              ]);
            }
          } else if (selectedScenario === 'LOW_CONFIDENCE') {
            setDemoEvents((e) => [
              {
                id: 'sim-' + Date.now(),
                time: timestamp,
                type: 'warning',
                text: 'VERIFY_REQUIRED: Hand motion obscured (confidence 58.2% < 85% threshold). Verification needed.',
              },
              ...e.slice(0, 15),
            ]);
          } else if (selectedScenario === 'UNKNOWN_OBJECT') {
            setDemoEvents((e) => [
              {
                id: 'sim-' + Date.now(),
                time: timestamp,
                type: 'critical',
                text: 'UNKNOWN_OBJECT: Foreign unverified item detected in sterile test chamber.',
              },
              ...e.slice(0, 15),
            ]);
          }

          return next > 6 ? 6 : next;
        });
      }, intervalMs);
    }

    return () => window.clearInterval(timer);
  }, [isRunning, selectedScenario, speedMultiplier]);

  const handleStartDemo = async () => {
    setIsRunning(true);
    setProgressStep(1);
    setDemoEvents([
      {
        id: 'start-' + Date.now(),
        time: new Date().toTimeString().split(' ')[0],
        type: 'info',
        text: `Starting demo simulation: scenario [${selectedScenario}] at ${speedMultiplier}x speed.`,
      },
    ]);

    try {
      await apiService.startDemo(selectedScenario);
    } catch {
      // Local client-side simulation continues seamlessly
    }
  };

  const handleStopDemo = async () => {
    setIsRunning(false);
    try {
      await apiService.stopDemo();
    } catch {
      // Local fallback
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Page Header */}
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
            <PlaySquare size={20} color="var(--cyan)" />
            <h2 style={{ fontSize: '18px', color: '#fff', margin: 0 }}>
              Judges Demo Mode & Protocol Fault Injection
            </h2>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
            Simulate realistic astronaut behavior, test sequence compliance engines, and demonstrate error alerts.
          </p>
        </div>

        {/* Global Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Speed Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '12px', color: 'var(--text-secondary)' }}>
            <Gauge size={14} />
            <span>Speed:</span>
            {[1, 2, 5].map((speed) => (
              <button
                key={speed}
                className={`btn ${speedMultiplier === speed ? 'btn-cyan' : 'btn-ghost'}`}
                style={{ padding: '4px 8px', fontSize: '11px' }}
                onClick={() => setSpeedMultiplier(speed)}
              >
                {speed}x
              </button>
            ))}
          </div>

          {!isRunning ? (
            <button className="btn btn-primary" onClick={handleStartDemo}>
              <Play size={14} />
              <span>Start Simulation</span>
            </button>
          ) : (
            <button className="btn btn-danger" onClick={handleStopDemo}>
              <Square size={14} />
              <span>Stop Simulation</span>
            </button>
          )}
        </div>
      </div>

      {/* Scenarios Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
        {MOCK_DEMO_SCENARIOS.map((sc) => {
          const isSelected = selectedScenario === sc.id;
          return (
            <div
              key={sc.id}
              onClick={() => {
                if (!isRunning) setSelectedScenario(sc.id);
              }}
              className="glass-panel"
              style={{
                padding: '16px',
                cursor: isRunning ? 'not-allowed' : 'pointer',
                border: isSelected ? '1px solid var(--cyan)' : '1px solid var(--border-subtle)',
                background: isSelected ? 'rgba(0, 229, 255, 0.08)' : 'rgba(12, 21, 46, 0.6)',
                transition: 'all 0.2s ease',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span className={`badge ${sc.badgeColor}`} style={{ fontSize: '10px' }}>
                  {sc.id}
                </span>
                {isSelected && <Zap size={14} color="var(--cyan)" />}
              </div>

              <h4 style={{ fontSize: '14px', color: '#fff', margin: '10px 0 4px 0' }}>{sc.title}</h4>
              <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: 0, minHeight: '34px' }}>
                {sc.description}
              </p>

              <div
                style={{
                  marginTop: 12,
                  padding: '6px 8px',
                  background: 'rgba(0, 0, 0, 0.3)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '10px',
                  color: 'var(--cyan)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                Expected: {sc.expectedResult}
              </div>
            </div>
          );
        })}
      </div>

      {/* Live Event Stream Panel */}
      <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '14px', color: '#fff', margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Sparkles size={16} color="var(--cyan)" />
            <span>Simulation Event Stream (Real-Time Output)</span>
          </h3>

          {isRunning && (
            <div className="badge badge-valid">
              <span className="status-dot green pulse" style={{ width: 6, height: 6 }} />
              SIMULATING STEP {progressStep} OF 6
            </div>
          )}
        </div>

        <div
          style={{
            background: 'rgba(0, 0, 0, 0.45)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '14px',
            minHeight: '180px',
            maxHeight: '260px',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          {demoEvents.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '12px', textAlign: 'center', marginTop: 40 }}>
              Select a scenario above and click &quot;Start Simulation&quot; to test protocol execution.
            </div>
          ) : (
            demoEvents.map((evt) => (
              <div
                key={evt.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  fontSize: '12px',
                  fontFamily: 'var(--font-mono)',
                  color:
                    evt.type === 'valid'
                      ? 'var(--valid)'
                      : evt.type === 'critical'
                      ? 'var(--critical)'
                      : evt.type === 'warning'
                      ? 'var(--warning)'
                      : 'var(--text-primary)',
                }}
              >
                <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>[{evt.time}]</span>
                <span>{evt.text}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
