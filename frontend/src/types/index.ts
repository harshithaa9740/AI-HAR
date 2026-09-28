/**
 * AURAVISION — Mission Control Core Types & Interfaces
 * Designed for ISRO / Smart India Hackathon BAS Experiment Protocol Validation
 */

export type ConnectionState = 'connected' | 'connecting' | 'offline' | 'error';

export interface BackendConfig {
  ip: string;
  port: number;
  protocol: 'http' | 'https';
  isConfigured: boolean;
}

export interface ProtocolStep {
  id?: string;
  step_number: number;
  action_code: string;
  display_name: string;
  description: string;
  expected_objects: string[];
  required: boolean;
  target_roi?: { x: number; y: number; w: number; h: number };
}

export interface ExperimentProtocol {
  id: string;
  name: string;
  description: string;
  version: string;
  steps_count: number;
  steps: ProtocolStep[];
  created_at?: string;
  updated_at?: string;
}

export type SessionState = 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'STOPPED' | 'INITIALIZING';

export interface ExperimentSession {
  id: string;
  experiment_id: string;
  session_code: string;
  status: SessionState;
  current_step_number: number;
  current_step_code?: string;
  expected_next_step?: string;
  started_at: string;
  ended_at?: string;
  operator_id?: string;
  compliance_rate?: number;
  violations_count?: number;
}

export type ValidationStatus = 
  | 'VALID' 
  | 'STEP_SKIPPED' 
  | 'OUT_OF_SEQUENCE' 
  | 'VERIFY_REQUIRED' 
  | 'LOW_CONFIDENCE' 
  | 'MISSING_OBJECT' 
  | 'UNKNOWN_ACTION' 
  | 'EXPERIMENT_COMPLETE';

export interface ValidationAlert {
  id: string;
  timestamp: string;
  type: ValidationStatus;
  title: string;
  message: string;
  severity: 'valid' | 'warning' | 'critical' | 'info';
  step_number?: number;
  observed_action?: string;
  expected_action?: string;
  confidence?: number;
}

export interface LiveTelemetry {
  ingestionFps: number;
  processingFps: number;
  latencyMs: number;
  totalFrames: number;
  framesProcessed: number;
  framesDropped: number;
  harConfidence: number;
  currentAction: string;
  detectedObjects: string[];
  poseName: string;
  jointCount: number;
  elbowAngle: string;
  handVelocity: string;
  cameraStatus: 'ACTIVE' | 'PAUSED' | 'OFFLINE' | 'ERROR';
  aiEngineStatus: 'INFERENCE_ACTIVE' | 'STANDALONE_SIM' | 'IDLE';
  isRecording: boolean;
  recordingDuration: string;
}

export interface AuditLogItem {
  id: string;
  timestamp: string;
  type: string;
  message: string;
  severity: 'info' | 'valid' | 'warning' | 'critical';
  category: 'all' | 'sequence' | 'detections' | 'alerts' | 'system';
  metadata?: Record<string, any>;
}

export interface AIModelStatus {
  model_name: string;
  model_version: string;
  provider: string;
  task: string;
  status: string;
  device: string;
  is_ready: boolean;
  confidence_threshold: number;
  active_scenario?: string;
  avg_latency_ms: number;
  throughput_fps: number;
}

export type DemoScenarioType = 
  | 'NORMAL' 
  | 'SKIPPED_STEP' 
  | 'OUT_OF_SEQUENCE' 
  | 'LOW_CONFIDENCE' 
  | 'UNKNOWN_OBJECT';

export interface DemoScenarioDefinition {
  id: DemoScenarioType;
  title: string;
  subtitle: string;
  description: string;
  expectedResult: string;
  badgeColor: string;
}

export interface SystemSettingsData {
  backend_ip: string;
  backend_port: number;
  confidence_threshold: number;
  object_confidence_threshold: number;
  video_source: 'mock' | 'file' | 'webcam';
  recording_enabled: boolean;
  voice_enabled: boolean;
  log_level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  streaming_ip: string;
  streaming_port: number;
}
