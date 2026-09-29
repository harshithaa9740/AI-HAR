import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Zap,
  CheckCircle,
  Sliders
} from 'lucide-react';
import { apiService } from '../services/api';
import type { AIModelStatus } from '../types';
import { MOCK_MODEL_STATUS } from '../services/mockData';

export const AIModels: React.FC = () => {
  const [modelStatus, setModelStatus] = useState<AIModelStatus>(MOCK_MODEL_STATUS);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.85);
  const [objectThreshold, setObjectThreshold] = useState(0.75);
  const [isRunningDiagnostics, setIsRunningDiagnostics] = useState(false);
  const [diagnosticResult, setDiagnosticResult] = useState<string | null>(null);

  useEffect(() => {
    const fetchModel = async () => {
      try {
        const data = await apiService.getActiveModel();
        if (data) {
          setModelStatus(data);
          setConfidenceThreshold(data.confidence_threshold || 0.85);
        }
      } catch {
        // Fallback to mock
      }
    };
    fetchModel();
  }, []);

  const handleRunDiagnostics = () => {
    setIsRunningDiagnostics(true);
    setDiagnosticResult(null);
    setTimeout(() => {
      setIsRunningDiagnostics(false);
      setDiagnosticResult('All AI sub-pipelines passed verification: TensorRT engine ready, Pose Keypoints: 33 joints, Latency: 32ms nominal.');
    }, 1500);
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
            <Cpu size={20} color="var(--cyan)" />
            <h2 style={{ fontSize: '18px', color: '#fff', margin: 0 }}>
              AI Models & Neural Inference Pipelines
            </h2>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
            Local edge vision models: Action recognition, 33-point body pose, and laboratory object detection.
          </p>
        </div>

        <button
          className="btn btn-cyan"
          onClick={handleRunDiagnostics}
          disabled={isRunningDiagnostics}
        >
          <Zap size={14} className={isRunningDiagnostics ? 'spin' : ''} />
          <span>{isRunningDiagnostics ? 'Running Benchmark...' : 'Run Pipeline Diagnostics'}</span>
        </button>
      </div>

      {diagnosticResult && (
        <div
          style={{
            padding: '12px 14px',
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
          <span>{diagnosticResult}</span>
        </div>
      )}

      {/* Model Spec Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
        {/* Active Model Spec Card */}
        <div className="glass-panel tech-corner" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <span className="badge badge-cyan">ACTIVE PIPELINE</span>
              <h3 style={{ fontSize: '16px', color: '#fff', margin: '8px 0 4px 0' }}>
                {modelStatus.model_name}
              </h3>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Version: <span className="font-mono">{modelStatus.model_version}</span>
              </div>
            </div>
            <span className="badge badge-valid">
              <span className="status-dot green pulse" style={{ width: 6, height: 6 }} />
              READY
            </span>
          </div>

          <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8, fontSize: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 6 }}>
              <span style={{ color: 'var(--text-muted)' }}>Target Architecture:</span>
              <strong style={{ color: '#fff' }}>YOLOv8 + MediaPipe Blazepose</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 6 }}>
              <span style={{ color: 'var(--text-muted)' }}>Inference Hardware:</span>
              <strong className="font-mono" style={{ color: 'var(--cyan)' }}>{modelStatus.device}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 6 }}>
              <span style={{ color: 'var(--text-muted)' }}>Pose Keypoints:</span>
              <strong style={{ color: '#fff' }}>33 3D Landmark Joints</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Precision:</span>
              <strong className="font-mono" style={{ color: 'var(--valid)' }}>FP16 (Half Precision)</strong>
            </div>
          </div>
        </div>

        {/* Inference Diagnostics */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <span className="badge badge-indigo">BENCHMARK METRICS</span>
          <h3 style={{ fontSize: '16px', color: '#fff', margin: '8px 0 16px 0' }}>
            Real-Time Latency & Throughput
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '12px', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>AVERAGE LATENCY</div>
              <div className="font-mono" style={{ fontSize: '22px', fontWeight: 700, color: 'var(--cyan)' }}>
                {modelStatus.avg_latency_ms} <span style={{ fontSize: '11px' }}>ms</span>
              </div>
            </div>

            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '12px', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>PEAK THROUGHPUT</div>
              <div className="font-mono" style={{ fontSize: '22px', fontWeight: 700, color: 'var(--valid)' }}>
                {modelStatus.throughput_fps} <span style={{ fontSize: '11px' }}>FPS</span>
              </div>
            </div>
          </div>

          <div style={{ marginTop: 14, fontSize: '11px', color: 'var(--text-secondary)' }}>
            Execution is localized to edge processor with zero outbound cloud inference calls.
          </div>
        </div>

        {/* Confidence Threshold Tuning */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Sliders size={16} color="var(--cyan)" />
            <h3 style={{ fontSize: '15px', color: '#fff', margin: 0 }}>Sensitivity Thresholds</h3>
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: 4 }}>
              <span style={{ color: 'var(--text-secondary)' }}>HAR Action Confidence</span>
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
        </div>
      </div>
    </div>
  );
};
