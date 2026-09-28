/**
 * AURAVISION — High-Fidelity Local Offline Mock Data
 * Provides realistic astronaut/operator data when backend is unreachable or in preview mode.
 */

import type { 
  ExperimentProtocol, 
  ExperimentSession, 
  LiveTelemetry, 
  AuditLogItem, 
  AIModelStatus, 
  DemoScenarioDefinition,
  SystemSettingsData,
  ValidationAlert
} from '../types';

export const MOCK_EXPERIMENT_PROTOCOL: ExperimentProtocol = {
  id: 'exp-bas-chem-802',
  name: 'BAS-CHEM-802: Chemical Specimen Extraction Protocol',
  description: 'Fixed-payload camera procedure for astronaut hazardous reagent extraction & reaction plate dispensing.',
  version: '1.2.0',
  steps_count: 6,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-28T08:30:00Z',
  steps: [
    {
      step_number: 1,
      action_code: 'PICK_TOOL',
      display_name: 'Pick Pipette from Sanitized Tray',
      description: 'Operator grasps calibrated precision pipette from the magnetic rack.',
      expected_objects: ['tool'],
      required: true,
      target_roi: { x: 0.15, y: 0.55, w: 0.22, h: 0.3 }
    },
    {
      step_number: 2,
      action_code: 'OPEN_CONTAINER',
      display_name: 'Unlatch & Open Specimen Container',
      description: 'Operator removes hermetic seal lid from containment chamber.',
      expected_objects: ['container'],
      required: true,
      target_roi: { x: 0.42, y: 0.48, w: 0.2, h: 0.35 }
    },
    {
      step_number: 3,
      action_code: 'TAKE_SAMPLE',
      display_name: 'Aspirate Chemical Sample (2.5 ml)',
      description: 'Operator draws specified 2.5ml fluid volume into pipette chamber.',
      expected_objects: ['sample', 'tool'],
      required: true,
      target_roi: { x: 0.45, y: 0.42, w: 0.25, h: 0.38 }
    },
    {
      step_number: 4,
      action_code: 'PLACE_SAMPLE',
      display_name: 'Dispense Sample into Reaction Well A1',
      description: 'Operator transfers and dispenses aliquot into reaction plate well.',
      expected_objects: ['sample', 'container'],
      required: true,
      target_roi: { x: 0.65, y: 0.52, w: 0.22, h: 0.32 }
    },
    {
      step_number: 5,
      action_code: 'SEAL_CONTAINER',
      display_name: 'Fasten & Seal Specimen Lid',
      description: 'Operator replaces and locks secondary seal cap to prevent volatile degassing.',
      expected_objects: ['container'],
      required: true,
      target_roi: { x: 0.42, y: 0.48, w: 0.2, h: 0.35 }
    },
    {
      step_number: 6,
      action_code: 'RETURN_TOOL',
      display_name: 'Return Pipette to Sanitized Rack',
      description: 'Operator replaces precision instrument back into magnetic UV fixture.',
      expected_objects: ['tool'],
      required: true,
      target_roi: { x: 0.15, y: 0.55, w: 0.22, h: 0.3 }
    }
  ]
};

export const MOCK_PROTOCOL = MOCK_EXPERIMENT_PROTOCOL;

export const MOCK_EXPERIMENTS_LIST: ExperimentProtocol[] = [
  MOCK_EXPERIMENT_PROTOCOL,
  {
    id: 'exp-bio-304',
    name: 'BAS-BIO-304: Cellular Fixation in Microgravity',
    description: 'Autonomous protocol for fixing cell cultures inside centrifuge cassette B.',
    version: '2.0.1',
    steps_count: 4,
    created_at: '2026-09-12T08:00:00Z',
    steps: []
  },
  {
    id: 'exp-mat-112',
    name: 'BAS-MAT-112: Zero-Gravity Crystal Nucleation',
    description: 'High-vacuum solvent extraction and micro-gravity crystallization assay.',
    version: '1.0.0',
    steps_count: 5,
    created_at: '2026-09-01T14:30:00Z',
    steps: []
  }
];

export const MOCK_ACTIVE_SESSION: ExperimentSession = {
  id: 'sess-isro-2026-042',
  experiment_id: 'exp-bas-chem-802',
  session_code: 'EXP-ISRO-2026-042',
  status: 'RUNNING',
  current_step_number: 3,
  current_step_code: 'STEP_03',
  expected_next_step: 'STEP_03 / Aspirate Chemical Sample',
  started_at: new Date(Date.now() - 14 * 60 * 1000 - 28 * 1000).toISOString(),
  operator_id: 'ASTRO-OP-04',
  compliance_rate: 100,
  violations_count: 0
};

export const MOCK_SESSION = MOCK_ACTIVE_SESSION;

export const MOCK_TELEMETRY: LiveTelemetry = {
  ingestionFps: 29.8,
  processingFps: 29.6,
  latencyMs: 18.4,
  totalFrames: 14820,
  framesProcessed: 14812,
  framesDropped: 8,
  harConfidence: 0.948,
  currentAction: 'TAKE_SAMPLE',
  detectedObjects: ['sample', 'tool'],
  poseName: 'Standing • Right Arm Active',
  jointCount: 33,
  elbowAngle: '112.5°',
  handVelocity: '0.24 m/s',
  cameraStatus: 'ACTIVE',
  aiEngineStatus: 'INFERENCE_ACTIVE',
  isRecording: true,
  recordingDuration: '00:14:28'
};

export const MOCK_AUDIT_LOGS: AuditLogItem[] = [
  {
    id: 'evt-001',
    timestamp: '14:02:10.120',
    type: 'SYSTEM_BOOT',
    message: 'AURAVISION Edge Node online. SQLite database initialized (auravision.db).',
    severity: 'info',
    category: 'system'
  },
  {
    id: 'evt-002',
    timestamp: '14:02:11.450',
    type: 'PROTOCOL_LOADED',
    message: 'Loaded SOP-CHEM-802: Chemical Specimen Extraction Protocol (6 verification checkpoints).',
    severity: 'info',
    category: 'sequence'
  },
  {
    id: 'evt-003',
    timestamp: '14:03:00.000',
    type: 'SESSION_START',
    message: 'Mission Session EXP-ISRO-2026-042 initiated. Ingestion camera active at 30 FPS.',
    severity: 'info',
    category: 'system'
  },
  {
    id: 'evt-004',
    timestamp: '14:04:15.340',
    type: 'STEP_VALIDATED',
    message: 'Step 1 (PICK_TOOL) validated. Operator successfully acquired sterilized pipette.',
    severity: 'valid',
    category: 'sequence',
    metadata: { step: 1, action: 'PICK_TOOL', confidence: 0.96 }
  },
  {
    id: 'evt-005',
    timestamp: '14:06:40.810',
    type: 'STEP_VALIDATED',
    message: 'Step 2 (OPEN_CONTAINER) validated. Hermetic vessel lid unlocked.',
    severity: 'valid',
    category: 'sequence',
    metadata: { step: 2, action: 'OPEN_CONTAINER', confidence: 0.93 }
  },
  {
    id: 'evt-006',
    timestamp: '14:09:12.180',
    type: 'DETECTION',
    message: 'AI Detector tracked 2 primary entities: [tool (pipette), container (vial)] with 94.8% confidence.',
    severity: 'info',
    category: 'detections'
  },
  {
    id: 'evt-007',
    timestamp: '14:11:05.900',
    type: 'INFERENCE_FEED',
    message: 'Current operator gesture matches TAKE_SAMPLE (elbow 112.5°, hand velocity 0.24 m/s).',
    severity: 'info',
    category: 'detections'
  }
];

export const MOCK_ALERTS: ValidationAlert[] = [
  {
    id: 'al-01',
    timestamp: '14:04:15',
    type: 'VALID',
    title: 'Step 1 Validated',
    message: 'Action PICK_TOOL confirmed with 96.2% confidence. Correct sterile pipette acquired.',
    severity: 'valid',
    step_number: 1,
    observed_action: 'PICK_TOOL',
    expected_action: 'PICK_TOOL',
    confidence: 0.962
  },
  {
    id: 'al-02',
    timestamp: '14:06:40',
    type: 'VALID',
    title: 'Step 2 Validated',
    message: 'Action OPEN_CONTAINER confirmed with 93.4% confidence. Lid seal removed.',
    severity: 'valid',
    step_number: 2,
    observed_action: 'OPEN_CONTAINER',
    expected_action: 'OPEN_CONTAINER',
    confidence: 0.934
  },
  {
    id: 'al-03',
    timestamp: '14:11:05',
    type: 'VERIFY_REQUIRED',
    title: 'Aspiration Verification',
    message: 'Step 3 in progress: Maintain steady hand velocity during 2.5ml draw.',
    severity: 'info',
    step_number: 3,
    observed_action: 'TAKE_SAMPLE',
    expected_action: 'TAKE_SAMPLE',
    confidence: 0.948
  }
];

export const MOCK_RECENT_SESSIONS: ExperimentSession[] = [
  MOCK_ACTIVE_SESSION,
  {
    id: 'sess-isro-2026-041',
    experiment_id: 'exp-bas-chem-802',
    session_code: 'EXP-ISRO-2026-041',
    status: 'COMPLETED',
    current_step_number: 6,
    started_at: '2026-09-28T09:15:00Z',
    ended_at: '2026-09-28T09:32:15Z',
    operator_id: 'ASTRO-OP-02',
    compliance_rate: 100,
    violations_count: 0
  },
  {
    id: 'sess-isro-2026-040',
    experiment_id: 'exp-bas-chem-802',
    session_code: 'EXP-ISRO-2026-040',
    status: 'STOPPED',
    current_step_number: 4,
    started_at: '2026-09-27T16:20:00Z',
    ended_at: '2026-09-27T16:29:40Z',
    operator_id: 'ASTRO-OP-01',
    compliance_rate: 80,
    violations_count: 1
  }
];

export const MOCK_MODEL_STATUS: AIModelStatus = {
  model_name: 'AURAVISION-Spatiotemporal-HAR-v1',
  model_version: '1.4.0-edge',
  provider: 'Edge Fusion Engine (YOLO + MediaPipe)',
  task: 'Fixed-Camera Space Experiment Human Action Recognition',
  status: 'ONLINE & HEALTHY',
  device: 'Local Intel Edge CPU / Integrated GPU',
  is_ready: true,
  confidence_threshold: 0.70,
  active_scenario: 'NORMAL',
  avg_latency_ms: 18.4,
  throughput_fps: 32.5
};

export const MOCK_DEMO_SCENARIOS: DemoScenarioDefinition[] = [
  {
    id: 'NORMAL',
    title: 'Nominal Execution',
    subtitle: 'Standard Sequential Order',
    description: 'Operator executes all protocol steps in strictly expected sequential progression (1 → 2 → 3 → 4 → 5 → 6).',
    expectedResult: 'All 6 steps VALIDATED with green flags and compliance at 100%.',
    badgeColor: 'badge-valid'
  },
  {
    id: 'SKIPPED_STEP',
    title: 'Skipped Checkpoint',
    subtitle: 'Step Omission Violation',
    description: 'Operator picks tool and jumps directly to taking sample without opening container lid first.',
    expectedResult: 'Raises immediate STEP_SKIPPED warning & voice alert: "Step 2 Open Container was omitted."',
    badgeColor: 'badge-critical'
  },
  {
    id: 'OUT_OF_SEQUENCE',
    title: 'Out of Sequence Action',
    subtitle: 'Premature Step Transition',
    description: 'Operator attempts dispensing sample before completing aspiration and container validation.',
    expectedResult: 'Triggers OUT_OF_SEQUENCE intervention alert & guidance prompt.',
    badgeColor: 'badge-warning'
  },
  {
    id: 'LOW_CONFIDENCE',
    title: 'Occlusion / Low Confidence',
    subtitle: 'Perception Obscuration',
    description: 'Operator body or glove partially occludes the reaction vessel, dropping model confidence below 50%.',
    expectedResult: 'Issues VERIFY_REQUIRED prompt asking astronaut to clear optical line-of-sight.',
    badgeColor: 'badge-indigo'
  },
  {
    id: 'UNKNOWN_OBJECT',
    title: 'Unregistered Motion',
    subtitle: 'Extraneous Interaction',
    description: 'Operator introduces an unauthorized non-protocol item or makes an uncalibrated gesture in the ROI.',
    expectedResult: 'Flags UNKNOWN_ACTION security warning and freezes protocol step progression.',
    badgeColor: 'badge-critical'
  }
];

export const MOCK_SYSTEM_SETTINGS: SystemSettingsData = {
  backend_ip: '127.0.0.1',
  backend_port: 8000,
  confidence_threshold: 0.70,
  object_confidence_threshold: 0.65,
  video_source: 'mock',
  recording_enabled: true,
  voice_enabled: true,
  log_level: 'INFO',
  streaming_ip: '0.0.0.0',
  streaming_port: 8080
};
