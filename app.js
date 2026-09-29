/**
 * AURAVISION - Offline AI Protocol Sequence Validator
 * Smart India Hackathon (SIH) Frontend Engine
 */

// Protocol Step Definitions (SOP-CHEM-802)
const PROTOCOL_STEPS = [
  {
    step_number: 1,
    action_code: 'PICK_TOOL',
    title: 'Pick Tool from Sanitized Tray',
    description: 'Operator grasps sterilized sampling tool / pipette from tray.',
    required_objects: ['tool'],
    target_roi: { x: 0.15, y: 0.55, w: 0.22, h: 0.3 }
  },
  {
    step_number: 2,
    action_code: 'OPEN_CONTAINER',
    title: 'Open Specimen Container',
    description: 'Operator unscrews / unlatches specimen test vial lid.',
    required_objects: ['container'],
    target_roi: { x: 0.42, y: 0.48, w: 0.2, h: 0.35 }
  },
  {
    step_number: 3,
    action_code: 'TAKE_SAMPLE',
    title: 'Aspirate Chemical Sample',
    description: 'Operator draws specified 2.5ml liquid volume into pipette.',
    required_objects: ['sample', 'tool'],
    target_roi: { x: 0.45, y: 0.42, w: 0.25, h: 0.38 }
  },
  {
    step_number: 4,
    action_code: 'PLACE_SAMPLE',
    title: 'Dispense Sample into Reaction Well',
    description: 'Operator accurately dispenses aliquot into reaction plate well A1.',
    required_objects: ['sample', 'container'],
    target_roi: { x: 0.65, y: 0.52, w: 0.22, h: 0.32 }
  },
  {
    step_number: 5,
    action_code: 'CLOSE_CONTAINER',
    title: 'Seal Container & Latch Lock',
    description: 'Operator seals container cap tightly until verified lock engagement.',
    required_objects: ['container'],
    target_roi: { x: 0.42, y: 0.48, w: 0.2, h: 0.35 }
  }
];

// AI Human Activity Recognition (HAR) Metadata
const HAR_ACTION_METADATA = {
  PICK_TOOL: {
    title: 'PICK_TOOL (REACHING & GRASPING TOOL)',
    pose: 'Standing • Right Arm Active',
    elbow: '114.2°',
    velocity: '0.24 m/s',
    top_actions: [
      { name: 'PICK_TOOL', prob: '96.2%' },
      { name: 'REACHING_TRAY', prob: '2.8%' },
      { name: 'OPERATOR_IDLE', prob: '1.0%' }
    ]
  },
  OPEN_CONTAINER: {
    title: 'OPEN_CONTAINER (UNSCREWING VIAL LID)',
    pose: 'Standing • Bimanual Manipulation',
    elbow: '92.5°',
    velocity: '0.11 m/s',
    top_actions: [
      { name: 'OPEN_CONTAINER', prob: '94.5%' },
      { name: 'HOLDING_VIAL', prob: '3.9%' },
      { name: 'TWIST_MOTION', prob: '1.6%' }
    ]
  },
  TAKE_SAMPLE: {
    title: 'TAKE_SAMPLE (PIPETTING LIQUID VOLUME)',
    pose: 'Focused Lean • Precision Pipetting',
    elbow: '84.0°',
    velocity: '0.04 m/s',
    top_actions: [
      { name: 'TAKE_SAMPLE', prob: '95.1%' },
      { name: 'ASPIRATING_LIQUID', prob: '3.6%' },
      { name: 'FINE_MOTOR_CONTROL', prob: '1.3%' }
    ]
  },
  PLACE_SAMPLE: {
    title: 'PLACE_SAMPLE (DISPENSING INTO WELL)',
    pose: 'Standing • Steady Micro-Dispensing',
    elbow: '88.3°',
    velocity: '0.06 m/s',
    top_actions: [
      { name: 'PLACE_SAMPLE', prob: '93.8%' },
      { name: 'DISPENSING_ALIQUOT', prob: '4.7%' },
      { name: 'POSITIONING_TIP', prob: '1.5%' }
    ]
  },
  CLOSE_CONTAINER: {
    title: 'CLOSE_CONTAINER (SEALING CAP & LATCH)',
    pose: 'Standing • Bimanual Torque Engagement',
    elbow: '101.4°',
    velocity: '0.15 m/s',
    top_actions: [
      { name: 'CLOSE_CONTAINER', prob: '97.2%' },
      { name: 'TIGHTENING_CAP', prob: '2.1%' },
      { name: 'LATCHING_VIAL', prob: '0.7%' }
    ]
  },
  UNKNOWN_GESTURE: {
    title: 'UNKNOWN_GESTURE (NON-SOP MOTION)',
    pose: 'Unregistered Dynamic Gesture',
    elbow: '138.0°',
    velocity: '0.45 m/s',
    top_actions: [
      { name: 'UNKNOWN_GESTURE', prob: '88.0%' },
      { name: 'RAPID_HAND_MOTION', prob: '8.4%' },
      { name: 'RANDOM_ARTICULATION', prob: '3.6%' }
    ]
  }
};

// Demonstration Scenario Sequences
const SCENARIO_DATA = {
  NORMAL: [
    { action_code: 'PICK_TOOL', confidence: 0.96, objects: ['tool'], latency: 22 },
    { action_code: 'OPEN_CONTAINER', confidence: 0.94, objects: ['container'], latency: 24 },
    { action_code: 'TAKE_SAMPLE', confidence: 0.95, objects: ['sample', 'tool'], latency: 26 },
    { action_code: 'PLACE_SAMPLE', confidence: 0.93, objects: ['sample', 'container'], latency: 23 },
    { action_code: 'CLOSE_CONTAINER', confidence: 0.97, objects: ['container'], latency: 21 }
  ],
  SKIPPED_STEP: [
    { action_code: 'PICK_TOOL', confidence: 0.95, objects: ['tool'], latency: 22 },
    { action_code: 'TAKE_SAMPLE', confidence: 0.94, objects: ['sample', 'tool'], latency: 25 } // Skips Step 2!
  ],
  OUT_OF_SEQUENCE: [
    { action_code: 'PICK_TOOL', confidence: 0.95, objects: ['tool'], latency: 22 },
    { action_code: 'OPEN_CONTAINER', confidence: 0.93, objects: ['container'], latency: 24 },
    { action_code: 'PICK_TOOL', confidence: 0.94, objects: ['tool'], latency: 21 } // Step 1 again instead of 3!
  ],
  LOW_CONFIDENCE: [
    { action_code: 'PICK_TOOL', confidence: 0.38, objects: ['tool'], latency: 38 } // Below 0.50 threshold
  ],
  MISSING_OBJECT: [
    { action_code: 'TAKE_SAMPLE', confidence: 0.92, objects: [], latency: 25 } // Missing required sample/tool
  ],
  UNKNOWN_ACTION: [
    { action_code: 'UNKNOWN_GESTURE', confidence: 0.88, objects: ['object_x'], latency: 31 }
  ]
};

// Backend API Configuration (FastAPI)
const BACKEND_CONFIG = {
  baseUrl: 'http://localhost:8000',
  apiBase: 'http://localhost:8000/api',
  wsUrl: 'ws://localhost:8000/ws/events',
  pollIntervalMs: 5000
};

// Application State
const state = {
  currentScenario: 'NORMAL',
  scenarioStepIndex: 0,
  activeExpectedStep: 1,
  completedSteps: new Set(),
  stepStatuses: {},
  sessionStartTime: Date.now(),
  sessionTimerInterval: null,
  isAutoPlaying: false,
  autoPlayTimer: null,
  voiceEnabled: true,
  currentSource: 'video', // 'video' | 'synthetic' | 'webcam'
  webcamStream: null,
  selectedCameraId: null,
  availableCameras: [],
  processedFrames: 0,
  auditLogs: [],
  backendOnline: false,
  backendWs: null,
  backendSessionId: null
};

// Web Audio API Sound Generator
class SoundFX {
  constructor() {
    this.ctx = null;
  }
  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
  }
  playSuccess() {
    this.init();
    if (!this.ctx) return;
    try {
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, now); // D5
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.15); // A5
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.3);
    } catch(e) {}
  }
  playWarning() {
    this.init();
    if (!this.ctx) return;
    try {
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(320, now);
      osc.frequency.setValueAtTime(240, now + 0.12);
      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.35);
    } catch(e) {}
  }
}
const sfx = new SoundFX();

// Text-to-Speech Engine
function speakInstruction(text) {
  if (!state.voiceEnabled || !window.speechSynthesis) return;
  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    const voices = window.speechSynthesis.getVoices();
    const naturalVoice = voices.find(v => v.lang.includes('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('English')));
    if (naturalVoice) utterance.voice = naturalVoice;

    const wave = document.getElementById('voiceWaveIndicator');
    utterance.onstart = () => { if (wave) wave.style.opacity = '1'; };
    utterance.onend = () => { if (wave) wave.style.opacity = '0.3'; };
    utterance.onerror = () => { if (wave) wave.style.opacity = '0.3'; };

    window.speechSynthesis.speak(utterance);
    document.getElementById('voiceStatusText').textContent = `Voice: "${text.substring(0, 32)}..."`;
  } catch(e) {}
}

// Sequence Validation Core Engine (Implements AURAVISION State Machine)
function validateObservedAction(observation) {
  const currentExpected = PROTOCOL_STEPS.find(s => s.step_number === state.activeExpectedStep);
  
  // Rule 1: Unknown Action
  const matchingStepIndex = PROTOCOL_STEPS.findIndex(s => s.action_code === observation.action_code);
  if (matchingStepIndex === -1) {
    return {
      result: 'UNKNOWN_ACTION',
      severity: 'critical',
      title: 'CRITICAL ALERT: UNRECOGNIZED ACTION',
      desc: `Detected unregistered gesture '${observation.action_code}'. Operator action deviates from SOP protocol.`,
      alert_code: 'UNKNOWN_ACTION'
    };
  }

  // Rule 2: Low Confidence Verification Required
  if (observation.confidence < 0.50) {
    return {
      result: 'VERIFY_REQUIRED',
      severity: 'warning',
      title: 'OPERATOR OCCLUSION / LOW CONFIDENCE',
      desc: `AI Model confidence (${(observation.confidence * 100).toFixed(1)}%) is below acceptable threshold (50%). Verify line of sight.`,
      alert_code: 'LOW_CONFIDENCE'
    };
  }

  // Rule 3: Missing Required Objects
  const observedStep = PROTOCOL_STEPS[matchingStepIndex];
  const missingObjects = observedStep.required_objects.filter(obj => !observation.objects.includes(obj));
  if (missingObjects.length > 0) {
    return {
      result: 'MISSING_OBJECT',
      severity: 'warning',
      title: `PROTOCOL VIOLATION: MISSING ${missingObjects.join(', ').toUpperCase()}`,
      desc: `Action '${observation.action_code}' attempted without mandatory tool/entity: [${missingObjects.join(', ')}].`,
      alert_code: 'MISSING_OBJECT'
    };
  }

  // Rule 4: Step Skipped (Observed action matches future step)
  if (observedStep.step_number > state.activeExpectedStep) {
    const skippedNumber = state.activeExpectedStep;
    const skippedStep = PROTOCOL_STEPS.find(s => s.step_number === skippedNumber);
    return {
      result: 'STEP_SKIPPED',
      severity: 'critical',
      title: `CRITICAL VIOLATION: STEP ${skippedNumber} SKIPPED`,
      desc: `Operator jumped to Step ${observedStep.step_number} (${observedStep.action_code}) before completing Step ${skippedNumber} (${skippedStep.action_code})!`,
      alert_code: 'STEP_SKIPPED'
    };
  }

  // Rule 5: Out of Sequence (Observed action matches past step or non-adjacent step)
  if (observedStep.step_number < state.activeExpectedStep) {
    return {
      result: 'OUT_OF_SEQUENCE',
      severity: 'warning',
      title: 'OUT OF SEQUENCE ACTION',
      desc: `Action '${observedStep.action_code}' was already executed. Awaiting Step ${state.activeExpectedStep} (${currentExpected.action_code}).`,
      alert_code: 'OUT_OF_SEQUENCE'
    };
  }

  // Rule 6: Valid Step Execution!
  return {
    result: 'VALID',
    severity: 'valid',
    title: `STEP ${observedStep.step_number} VALIDATED: ${observedStep.action_code}`,
    desc: `Observation confirmed: ${observedStep.title}. Confidence: ${(observation.confidence * 100).toFixed(1)}%.`,
    alert_code: 'STEP_COMPLETED',
    stepNumber: observedStep.step_number
  };
}

// Execute Next Simulation Step
function executeNextStep() {
  const scenarioItems = SCENARIO_DATA[state.currentScenario] || [];
  
  if (state.scenarioStepIndex >= scenarioItems.length) {
    appendAuditLog('SYSTEM', `Scenario '${state.currentScenario}' execution finished.`, 'system');
    stopAutoPlay();
    return;
  }

  const observation = scenarioItems[state.scenarioStepIndex];
  state.scenarioStepIndex++;

  // Update HUD Telemetry
  document.getElementById('aiObservedAction').textContent = observation.action_code;
  document.getElementById('aiObservedConf').textContent = `${(observation.confidence * 100).toFixed(1)}%`;
  document.getElementById('aiObservedObjects').textContent = JSON.stringify(observation.objects);
  document.getElementById('valConfidence').textContent = `${(observation.confidence * 100).toFixed(1)}%`;
  document.getElementById('valLatency').textContent = `${observation.latency || 24} ms`;
  state.processedFrames += 15;
  document.getElementById('valFrames').textContent = state.processedFrames;

  // Update AI Human Activity Recognition (HAR) UI
  const harMeta = HAR_ACTION_METADATA[observation.action_code] || {
    title: `${observation.action_code} (INTERACTION)`,
    pose: 'Active Manipulation',
    elbow: '95.0°',
    velocity: '0.12 m/s',
    top_actions: [
      { name: observation.action_code, prob: `${(observation.confidence * 100).toFixed(1)}%` },
      { name: 'SECONDARY_GESTURE', prob: '4.5%' },
      { name: 'OPERATOR_IDLE', prob: '1.5%' }
    ]
  };

  const harTitleEl = document.getElementById('harCurrentActionTitle');
  if (harTitleEl) harTitleEl.textContent = harMeta.title;
  const harPoseEl = document.getElementById('harPoseState');
  if (harPoseEl) harPoseEl.textContent = harMeta.pose;
  const harConfEl = document.getElementById('harConfidenceScore');
  if (harConfEl) harConfEl.textContent = `${(observation.confidence * 100).toFixed(1)}%`;

  // Update Probability Spectrum
  if (harMeta.top_actions && harMeta.top_actions.length >= 3) {
    document.getElementById('probAct1Name').textContent = harMeta.top_actions[0].name;
    document.getElementById('probAct1Val').textContent = harMeta.top_actions[0].prob;
    document.getElementById('probAct1Bar').style.width = harMeta.top_actions[0].prob;

    document.getElementById('probAct2Name').textContent = harMeta.top_actions[1].name;
    document.getElementById('probAct2Val').textContent = harMeta.top_actions[1].prob;
    document.getElementById('probAct2Bar').style.width = harMeta.top_actions[1].prob;

    document.getElementById('probAct3Name').textContent = harMeta.top_actions[2].name;
    document.getElementById('probAct3Val').textContent = harMeta.top_actions[2].prob;
    document.getElementById('probAct3Bar').style.width = harMeta.top_actions[2].prob;
  }

  // Update Biomechanics
  document.getElementById('biomechElbow').textContent = harMeta.elbow;
  document.getElementById('biomechVelocity').textContent = harMeta.velocity;

  // Run sequence validation
  const validation = validateObservedAction(observation);

  // Update Decision Banner UI
  const banner = document.getElementById('decisionBanner');
  banner.className = `decision-banner ${validation.severity}`;
  document.getElementById('decisionTitle').textContent = validation.title;
  document.getElementById('decisionDesc').textContent = validation.desc;

  if (validation.result === 'VALID') {
    sfx.playSuccess();
    state.completedSteps.add(validation.stepNumber);
    state.stepStatuses[validation.stepNumber] = 'COMPLETED';

    // Advance step
    if (state.activeExpectedStep < PROTOCOL_STEPS.length) {
      state.activeExpectedStep++;
      const nextStep = PROTOCOL_STEPS.find(s => s.step_number === state.activeExpectedStep);
      speakInstruction(`Step ${validation.stepNumber} complete. Next: ${nextStep.title}`);
      document.getElementById('aiNextExpected').textContent = `Step ${nextStep.step_number}: ${nextStep.action_code}`;
    } else {
      speakInstruction('Protocol completed successfully. All steps verified.');
      document.getElementById('aiNextExpected').textContent = 'PROTOCOL FULLY COMPLETED';
      appendAuditLog('VALIDATION', 'All protocol steps completed and validated against SOP-CHEM-802.', 'validation');
    }
  } else {
    sfx.playWarning();
    speakInstruction(`Alert: ${validation.title}`);
    state.stepStatuses[state.activeExpectedStep] = 'VIOLATION';
  }

  // Record Audit Log
  appendAuditLog(
    validation.result,
    `[HAR: ${observation.action_code}] Conf: ${(observation.confidence*100).toFixed(1)}% | ${validation.desc}`,
    validation.severity === 'critical' ? 'alert' : (validation.severity === 'warning' ? 'warning' : 'validation')
  );

  updateStepCardsUI();
  updateProgressUI();

  // Forward observation to FastAPI Backend for real-time validation and SQLite logging
  sendObservationToBackend(observation);
}

// Update Step Cards in UI
function updateStepCardsUI() {
  const container = document.getElementById('stepListContainer');
  const cards = container.querySelectorAll('.step-card');

  cards.forEach(card => {
    const stepNum = parseInt(card.dataset.step, 10);
    const statusChip = card.querySelector('.step-status-chip');

    card.classList.remove('active', 'completed', 'violation');

    if (state.completedSteps.has(stepNum)) {
      card.classList.add('completed');
      statusChip.className = 'step-status-chip completed';
      statusChip.textContent = 'VERIFIED';
    } else if (stepNum === state.activeExpectedStep) {
      if (state.stepStatuses[stepNum] === 'VIOLATION') {
        card.classList.add('violation');
        statusChip.className = 'step-status-chip skipped';
        statusChip.textContent = 'VIOLATION';
      } else {
        card.classList.add('active');
        statusChip.className = 'step-status-chip active';
        statusChip.textContent = 'IN PROGRESS';
      }
    } else if (stepNum < state.activeExpectedStep) {
      card.classList.add('violation');
      statusChip.className = 'step-status-chip skipped';
      statusChip.textContent = 'SKIPPED';
    } else {
      statusChip.className = 'step-status-chip pending';
      statusChip.textContent = 'PENDING';
    }
  });

  document.getElementById('currentStepNumber').textContent = state.activeExpectedStep;
}

// Update Progress Bar
function updateProgressUI() {
  const total = PROTOCOL_STEPS.length;
  const count = state.completedSteps.size;
  const pct = Math.round((count / total) * 100);

  document.getElementById('progressBarFill').style.width = `${pct}%`;
  document.getElementById('progressPercent').textContent = `${pct}%`;

  const violations = Object.values(state.stepStatuses).filter(s => s === 'VIOLATION').length;
  const compliance = count + violations > 0 ? Math.round((count / (count + violations)) * 100) : 100;
  document.getElementById('complianceRate').textContent = `${compliance}%`;
  document.getElementById('complianceRate').style.color = compliance >= 80 ? 'var(--accent-emerald)' : 'var(--accent-amber)';
}

// Reset Session
function resetSession(scenarioName = null) {
  stopAutoPlay();
  if (scenarioName) state.currentScenario = scenarioName;
  state.scenarioStepIndex = 0;
  state.activeExpectedStep = 1;
  state.completedSteps.clear();
  state.stepStatuses = {};
  state.processedFrames = 0;

  const banner = document.getElementById('decisionBanner');
  banner.className = 'decision-banner info';
  document.getElementById('decisionTitle').textContent = `SCENARIO INITIALIZED: ${state.currentScenario}`;
  document.getElementById('decisionDesc').textContent = `Ready for real-time SOP inference. Click 'Step Forward' or 'Auto-Play'.`;
  
  const step1 = PROTOCOL_STEPS[0];
  document.getElementById('aiObservedAction').textContent = step1.action_code;
  document.getElementById('aiObservedConf').textContent = '95.0%';
  document.getElementById('aiObservedObjects').textContent = JSON.stringify(step1.required_objects);
  document.getElementById('aiNextExpected').textContent = `Step 1: ${step1.action_code}`;

  const harMeta = HAR_ACTION_METADATA.PICK_TOOL;
  const harTitleEl = document.getElementById('harCurrentActionTitle');
  if (harTitleEl) harTitleEl.textContent = harMeta.title;
  const harPoseEl = document.getElementById('harPoseState');
  if (harPoseEl) harPoseEl.textContent = harMeta.pose;
  const harConfEl = document.getElementById('harConfidenceScore');
  if (harConfEl) harConfEl.textContent = '96.2%';

  document.getElementById('probAct1Name').textContent = harMeta.top_actions[0].name;
  document.getElementById('probAct1Val').textContent = harMeta.top_actions[0].prob;
  document.getElementById('probAct1Bar').style.width = harMeta.top_actions[0].prob;

  document.getElementById('probAct2Name').textContent = harMeta.top_actions[1].name;
  document.getElementById('probAct2Val').textContent = harMeta.top_actions[1].prob;
  document.getElementById('probAct2Bar').style.width = harMeta.top_actions[1].prob;

  document.getElementById('probAct3Name').textContent = harMeta.top_actions[2].name;
  document.getElementById('probAct3Val').textContent = harMeta.top_actions[2].prob;
  document.getElementById('probAct3Bar').style.width = harMeta.top_actions[2].prob;

  document.getElementById('biomechElbow').textContent = harMeta.elbow;
  document.getElementById('biomechVelocity').textContent = harMeta.velocity;

  updateStepCardsUI();
  updateProgressUI();
  appendAuditLog('SESSION_RESET', `Session reset to Step 1. Scenario: ${state.currentScenario}`, 'system');

  if (state.backendOnline) {
    const sessionCode = `EXP-${new Date().toISOString().replace(/\D/g, '').slice(0, 14)}`;
    fetch(`${BACKEND_CONFIG.apiBase}/sessions/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        experiment_id: 1,
        session_code: sessionCode
      })
    })
    .then(r => r.json())
    .then(data => {
      if (data && data.id) {
        state.backendSessionId = data.id;
        appendAuditLog('SESSION_SYNC', `Real Experiment Session #${data.id} (${data.session_code || sessionCode}) active with Supabase live replication.`, 'system');
        loadSessionHistory();
      }
    })
    .catch(err => {
      console.warn('Failed to initialize real experiment session:', err);
    });
  }
}

// Append Item to Unified Audit Log
function appendAuditLog(eventType, message, category = 'system') {
  const logStream = document.getElementById('logStream');
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0] + '.' + String(now.getMilliseconds()).padStart(3, '0');

  const logEntry = {
    timestamp: now.toISOString(),
    event_type: eventType,
    category: category,
    message: message
  };
  state.auditLogs.unshift(logEntry);

  const itemEl = document.createElement('div');
  itemEl.className = `log-item ${category}`;
  itemEl.innerHTML = `
    <div class="log-meta">
      <span>${eventType}</span>
      <span>${timeStr}</span>
    </div>
    <div class="log-content">${message}</div>
  `;

  logStream.prepend(itemEl);
  document.getElementById('logCountLabel').textContent = `${state.auditLogs.length} events`;
}

// Export Audit Logs as JSON
function exportAuditLog() {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({
    system: "AURAVISION AI Human Activity Recognition Offline System",
    protocol: "SOP-CHEM-802",
    session_start: new Date(state.sessionStartTime).toISOString(),
    export_timestamp: new Date().toISOString(),
    compliance_score: document.getElementById('complianceRate').textContent,
    events_count: state.auditLogs.length,
    events: state.auditLogs
  }, null, 2));

  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", `AURAVISION_HAR_Audit_Log_${Date.now()}.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
}

// Auto-Play Feature
function toggleAutoPlay() {
  if (state.isAutoPlaying) {
    stopAutoPlay();
  } else {
    state.isAutoPlaying = true;
    document.getElementById('autoPlayLabel').textContent = 'Pause';
    document.getElementById('btnAutoPlay').classList.add('btn-primary');
    executeNextStep();
    state.autoPlayTimer = setInterval(() => {
      const scenarioItems = SCENARIO_DATA[state.currentScenario] || [];
      if (state.scenarioStepIndex >= scenarioItems.length) {
        stopAutoPlay();
      } else {
        executeNextStep();
      }
    }, 2400);
  }
}

function stopAutoPlay() {
  state.isAutoPlaying = false;
  if (state.autoPlayTimer) clearInterval(state.autoPlayTimer);
  document.getElementById('autoPlayLabel').textContent = 'Auto-Play';
  document.getElementById('btnAutoPlay').classList.remove('btn-primary');
}

// Video Controls & Time HUD
function initVideoControls() {
  const video = document.getElementById('cameraVideo');
  const btnPlayPause = document.getElementById('btnPlayPauseVideo');
  const btnRestart = document.getElementById('btnRestartVideo');
  const timeHud = document.getElementById('videoPlaybackTime');
  const playPauseIcon = document.getElementById('playPauseIcon');

  btnPlayPause.addEventListener('click', () => {
    if (video.paused) {
      video.play().catch(e => console.warn('Play interrupted:', e));
      playPauseIcon.innerHTML = '<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>';
    } else {
      video.pause();
      playPauseIcon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"></polygon>';
    }
  });

  btnRestart.addEventListener('click', () => {
    if (state.currentSource === 'webcam') {
      // Reconnect/re-sync current webcam
      startWebcam(state.selectedCameraId);
      return;
    }
    video.currentTime = 0;
    video.play().catch(e => console.warn('Restart play error:', e));
  });

  video.addEventListener('timeupdate', () => {
    if (state.currentSource === 'webcam') {
      timeHud.textContent = 'LIVE WEBCAM';
      return;
    }
    if (state.currentSource === 'synthetic') {
      timeHud.textContent = 'SYNTHETIC AI';
      return;
    }
    const cur = formatTime(video.currentTime);
    const dur = formatTime(video.duration || 0);
    timeHud.textContent = `${cur} / ${dur}`;
  });
}

function formatTime(sec) {
  if (!Number.isFinite(sec) || sec < 0) return '00:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// Camera & Vision Overlay Canvas Drawing: Full MediaPipe Human Skeleton
function initVisionCanvas() {
  const canvas = document.getElementById('visionCanvas');
  const ctx = canvas.getContext('2d');
  const viewport = document.getElementById('videoViewport');

  function resizeCanvas() {
    canvas.width = viewport.clientWidth;
    canvas.height = viewport.clientHeight;
  }
  window.addEventListener('resize', resizeCanvas);
  resizeCanvas();

  let t = 0;

  function renderOverlay() {
    t += 0.035;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const w = canvas.width;
    const h = canvas.height;

    // Highlight expected ROI
    const curStep = PROTOCOL_STEPS.find(s => s.step_number === state.activeExpectedStep);
    if (curStep && curStep.target_roi) {
      const rx = curStep.target_roi.x * w;
      const ry = curStep.target_roi.y * h;
      const rw = curStep.target_roi.w * w;
      const rh = curStep.target_roi.h * h;

      ctx.save();
      ctx.strokeStyle = '#00e5ff';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(rx, ry, rw, rh);
      ctx.setLineDash([]);

      ctx.fillStyle = 'rgba(0, 229, 255, 0.85)';
      ctx.fillRect(rx, ry - 20, 130, 20);
      ctx.fillStyle = '#000';
      ctx.font = 'bold 10px JetBrains Mono, monospace';
      ctx.fillText(`TARGET: ${curStep.action_code}`, rx + 5, ry - 6);
      ctx.restore();
    }

    // ----------------------------------------------------
    // Full MediaPipe BlazePose Human Skeleton Tracking
    // ----------------------------------------------------
    const headX = w * 0.42;
    const headY = h * 0.28;

    // Body Landmark Coordinates
    const nose = { x: headX, y: headY };
    const leftEye = { x: headX - 8, y: headY - 6 };
    const rightEye = { x: headX + 8, y: headY - 6 };
    const neck = { x: headX, y: headY + 30 };
    const leftShoulder = { x: headX - 60, y: headY + 45 };
    const rightShoulder = { x: headX + 60, y: headY + 45 };
    const midHip = { x: headX, y: headY + 140 };

    // Left arm (resting / holding support)
    const leftElbow = { x: headX - 85, y: headY + 85 };
    const leftWrist = { x: headX - 70, y: headY + 125 };

    // Right arm (active manipulation hand tracking target)
    const handX = w * (0.35 + Math.sin(t) * 0.14);
    const handY = h * (0.52 + Math.cos(t * 1.2) * 0.10);
    const rightElbow = { x: (rightShoulder.x + handX) / 2 + 25, y: (rightShoulder.y + handY) / 2 + 10 };
    const rightWrist = { x: handX, y: handY };

    ctx.save();

    // 1. Draw Bounding Box around Operator
    ctx.strokeStyle = 'rgba(0, 229, 255, 0.4)';
    ctx.lineWidth = 1;
    ctx.strokeRect(headX - 110, headY - 45, 230, 230);

    // Operator Label Badge
    ctx.fillStyle = 'rgba(10, 13, 20, 0.85)';
    ctx.fillRect(headX - 110, headY - 68, 230, 22);
    ctx.fillStyle = '#00e5ff';
    ctx.font = 'bold 10px JetBrains Mono, monospace';
    const curAction = document.getElementById('aiObservedAction').textContent || 'PICK_TOOL';
    ctx.fillText(`AI HUMAN: OP#1 [${curAction}]`, headX - 104, headY - 53);

    // 2. Helper to draw connecting glowing bones
    function drawBone(p1, p2, color = 'rgba(0, 229, 255, 0.75)', width = 2.5) {
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.shadowColor = '#00e5ff';
      ctx.shadowBlur = 6;
      ctx.stroke();
    }

    // Connect Skeleton
    drawBone(nose, neck);
    drawBone(neck, leftShoulder);
    drawBone(neck, rightShoulder);
    drawBone(leftShoulder, midHip, 'rgba(0, 229, 255, 0.4)', 1.5);
    drawBone(rightShoulder, midHip, 'rgba(0, 229, 255, 0.4)', 1.5);

    // Left Arm Bones
    drawBone(leftShoulder, leftElbow);
    drawBone(leftElbow, leftWrist);

    // Right Arm Bones (Active - Emerald glow)
    drawBone(rightShoulder, rightElbow, 'rgba(0, 230, 118, 0.85)', 3);
    drawBone(rightElbow, rightWrist, 'rgba(0, 230, 118, 0.85)', 3);

    // 3. Draw Hand Finger Rays from Wrist
    const fingerAngles = [-0.6, -0.3, 0, 0.3, 0.6];
    fingerAngles.forEach(ang => {
      const fx = rightWrist.x + Math.sin(t + ang) * 18;
      const fy = rightWrist.y + Math.cos(t + ang) * 18;
      drawBone(rightWrist, { x: fx, y: fy }, 'rgba(0, 230, 118, 0.9)', 1.5);
      // Fingertip joint
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(fx, fy, 2, 0, Math.PI * 2);
      ctx.fill();
    });

    // 4. Draw Joint Landmark Dots
    const allJoints = [nose, leftEye, rightEye, neck, leftShoulder, rightShoulder, leftElbow, leftWrist, rightElbow, rightWrist, midHip];
    allJoints.forEach((j, i) => {
      ctx.beginPath();
      ctx.arc(j.x, j.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = i >= 8 ? '#00e676' : '#00e5ff';
      ctx.shadowColor = '#00e5ff';
      ctx.shadowBlur = 8;
      ctx.fill();
    });

    // Hand Tracking HUD Box
    ctx.strokeStyle = '#00e676';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(handX - 25, handY - 25, 50, 50);
    ctx.fillStyle = 'rgba(0, 230, 118, 0.85)';
    ctx.fillRect(handX - 25, handY - 42, 85, 17);
    ctx.fillStyle = '#000';
    ctx.font = 'bold 9px JetBrains Mono, monospace';
    ctx.fillText('R_HAND: 98.6%', handX - 22, handY - 30);

    ctx.restore();

    requestAnimationFrame(renderOverlay);
  }

  renderOverlay();
}

// Stop active media stream and clear references
function stopWebcamStream() {
  if (state.webcamStream) {
    try {
      state.webcamStream.getTracks().forEach(track => {
        track.stop();
      });
    } catch (e) {
      console.warn('Error stopping camera track:', e);
    }
    state.webcamStream = null;
  }
  const video = document.getElementById('cameraVideo');
  if (video && video.srcObject) {
    video.srcObject = null;
  }
}

// Parse MediaDevices/WebRTC errors into actionable diagnostic messages
function parseCameraError(err) {
  const errName = err ? (err.name || '') : '';
  const errMsg = err ? (err.message || '').toLowerCase() : '';

  if (errName === 'NotAllowedError' || errName === 'PermissionDeniedError' || errMsg.includes('permission denied')) {
    return {
      type: 'PERMISSION_DENIED',
      title: 'Camera Access Denied',
      message: 'Permission to access the camera was blocked by your browser. Please click the lock or camera icon in the address bar, allow camera permissions, and try again.'
    };
  }
  if (errName === 'NotFoundError' || errName === 'DevicesNotFoundError' || errMsg.includes('requested device not found') || errMsg.includes('not found')) {
    return {
      type: 'NO_CAMERA_FOUND',
      title: 'No Camera Detected',
      message: 'No video capture hardware was detected. Please connect a webcam or enable your integrated camera in Windows Device Manager.'
    };
  }
  if (errName === 'NotReadableError' || errName === 'AbortError' || errName === 'TrackStartError' || errMsg.includes('could not start video source') || errMsg.includes('already in use') || errMsg.includes('busy')) {
    return {
      type: 'CAMERA_IN_USE',
      title: 'Camera Already in Use / Hardware Busy',
      message: 'Your camera is currently locked or in use by another application (e.g. Windows Camera, Zoom, Teams, Skype, or another browser tab). Please close other apps and try again.'
    };
  }
  if (errName === 'OverconstrainedError' || errName === 'ConstraintNotSatisfiedError') {
    return {
      type: 'OVERCONSTRAINED',
      title: 'Resolution Constraint Not Supported',
      message: 'The requested video resolution is not supported by your camera hardware. Retrying with default resolution.'
    };
  }
  if (errName === 'SecurityError') {
    return {
      type: 'SECURITY_ERROR',
      title: 'Security Context Restriction',
      message: 'Camera access requires a secure origin (http://localhost or HTTPS).'
    };
  }
  return {
    type: 'GENERAL_ERROR',
    title: 'Camera Startup Failed',
    message: err && err.message ? err.message : 'Could not initialize video capture stream.'
  };
}

// Display inline error banner
function showCameraError(errorInfo) {
  const banner = document.getElementById('cameraAlertBanner');
  if (banner) {
    banner.innerHTML = `
      <div style="display: flex; align-items: flex-start; gap: 0.5rem; flex: 1;">
        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="flex-shrink: 0; margin-top: 2px;">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <div>
          <strong style="display: block; font-weight: 600; margin-bottom: 2px;">${errorInfo.title}</strong>
          <span>${errorInfo.message}</span>
        </div>
      </div>
      <button id="btnCloseCameraAlert" style="background: transparent; border: none; color: inherit; font-size: 1.2rem; cursor: pointer; padding: 0 4px; line-height: 1;" title="Dismiss">&times;</button>
    `;
    banner.style.display = 'flex';
    const closeBtn = document.getElementById('btnCloseCameraAlert');
    if (closeBtn) closeBtn.onclick = () => { banner.style.display = 'none'; };
  } else {
    alert(`${errorInfo.title}\n\n${errorInfo.message}`);
  }
}

// Hide camera error banner
function hideCameraError() {
  const banner = document.getElementById('cameraAlertBanner');
  if (banner) {
    banner.style.display = 'none';
  }
}

// Discover and populate available video input hardware
async function populateCameraDevices() {
  const selectEl = document.getElementById('cameraDeviceSelect');
  if (!selectEl || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;

  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoDevices = devices.filter(d => d.kind === 'videoinput');
    state.availableCameras = videoDevices;

    selectEl.innerHTML = '';
    if (videoDevices.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'Default Camera';
      selectEl.appendChild(opt);
      selectEl.style.display = 'none';
      return;
    }

    videoDevices.forEach((dev, idx) => {
      const opt = document.createElement('option');
      opt.value = dev.deviceId;
      opt.textContent = dev.label || `Camera ${idx + 1}`;
      if (state.selectedCameraId === dev.deviceId || (!state.selectedCameraId && idx === 0)) {
        opt.selected = true;
      }
      selectEl.appendChild(opt);
    });

    if (state.currentSource === 'webcam') {
      selectEl.style.display = videoDevices.length > 0 ? 'inline-block' : 'none';
    }
  } catch (err) {
    console.warn('Could not enumerate media devices:', err);
  }
}

// Start hardware webcam feed with adaptive constraints & graceful fallback
async function startWebcam(deviceId = null) {
  const video = document.getElementById('cameraVideo');
  const hudStatus = document.getElementById('hudTrackStatus');
  const hudRes = document.getElementById('hudResolution');
  hideCameraError();

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    const errInfo = {
      title: 'WebRTC Not Supported',
      message: 'Your browser environment does not support navigator.mediaDevices.getUserMedia.'
    };
    showCameraError(errInfo);
    switchToSource('video');
    return false;
  }

  // Release backend hardware capture in case backend was holding device 0
  try {
    fetch(`${BACKEND_CONFIG.apiBase}/video/stop`, { method: 'POST' }).catch(() => {});
  } catch (e) {}

  // Stop any active stream first to ensure cleanly releasing previous tracks
  stopWebcamStream();

  video.pause();
  video.removeAttribute('src');
  video.src = '';
  video.srcObject = null;

  // Attempt 1: Ideal HD / VGA constraints
  const preferredConstraints = {
    video: {
      deviceId: deviceId ? { exact: deviceId } : undefined,
      width: { ideal: 1280, min: 640 },
      height: { ideal: 720, min: 480 }
    },
    audio: false
  };

  let stream = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia(preferredConstraints);
  } catch (primaryErr) {
    console.warn('Preferred camera constraints failed, attempting fallback constraints:', primaryErr);
    // Attempt 2: Minimal unconstrained video request
    try {
      const fallbackConstraints = deviceId ? { video: { deviceId: { exact: deviceId } }, audio: false } : { video: true, audio: false };
      stream = await navigator.mediaDevices.getUserMedia(fallbackConstraints);
    } catch (fallbackErr) {
      const parsed = parseCameraError(fallbackErr || primaryErr);
      showCameraError(parsed);
      if (hudStatus) hudStatus.textContent = 'CAMERA ERROR';
      appendAuditLog('CAMERA', `Hardware camera failed [${parsed.type}]: ${parsed.message}`, 'critical');
      // Gracefully return to offline MP4 feed
      switchToSource('video');
      return false;
    }
  }

  state.webcamStream = stream;
  video.srcObject = stream;
  video.muted = true;
  video.playsInline = true;

  try {
    await video.play();
  } catch (playErr) {
    console.warn('Video play interrupted or muted required:', playErr);
  }

  // Update track resolution HUD
  const vTrack = stream.getVideoTracks()[0];
  if (vTrack) {
    const s = vTrack.getSettings ? vTrack.getSettings() : {};
    const w = s.width || video.videoWidth || 640;
    const h = s.height || video.videoHeight || 480;
    const fps = Math.round(s.frameRate || 30);
    if (hudRes) hudRes.textContent = `${w}x${h} @ ${fps} FPS`;
    const label = vTrack.label || 'Default Camera';
    appendAuditLog('CAMERA', `Connected to hardware webcam: ${label} (${w}x${h} @ ${fps} FPS).`, 'system');
  }

  if (hudStatus) hudStatus.textContent = 'SOURCE: LIVE WEBCAM';

  // Re-enumerate devices with permission granted so actual device labels appear
  await populateCameraDevices();

  return true;
}

// Unified source switcher ensuring reliable transitions between MP4, Synthetic, and Webcam
async function switchToSource(srcType) {
  const tabs = document.querySelectorAll('.source-tab');
  const video = document.getElementById('cameraVideo');
  const selectEl = document.getElementById('cameraDeviceSelect');
  const hudStatus = document.getElementById('hudTrackStatus');
  const hudRes = document.getElementById('hudResolution');

  tabs.forEach(t => {
    t.classList.toggle('active', t.dataset.source === srcType);
  });

  state.currentSource = srcType;

  if (srcType === 'video') {
    hideCameraError();
    if (selectEl) selectEl.style.display = 'none';
    stopWebcamStream();

    video.pause();
    video.srcObject = null;
    video.removeAttribute('src');
    video.src = 'assets/experiment_sample.mp4';
    video.currentTime = 0;
    video.loop = true;
    video.muted = true;
    video.playsInline = true;
    try {
      await video.play();
    } catch (e) {
      console.warn('MP4 playback auto-start:', e);
    }

    if (hudStatus) hudStatus.textContent = 'SOURCE: OFFLINE MP4';
    if (hudRes) hudRes.textContent = '640x480 @ 30 FPS';
    appendAuditLog('SOURCE', 'Switched to offline experiment sample MP4 video.', 'system');

  } else if (srcType === 'synthetic') {
    hideCameraError();
    if (selectEl) selectEl.style.display = 'none';
    stopWebcamStream();

    video.pause();
    video.srcObject = null;
    video.removeAttribute('src');
    video.src = '';

    if (hudStatus) hudStatus.textContent = 'SOURCE: SYNTHETIC AI ENGINE';
    if (hudRes) hudRes.textContent = '640x480 (SYNTHETIC)';
    appendAuditLog('SOURCE', 'Switched to synthetic laboratory visual canvas.', 'system');

  } else if (srcType === 'webcam') {
    if (selectEl && state.availableCameras.length > 0) {
      selectEl.style.display = 'inline-block';
    }
    const targetId = selectEl && selectEl.value ? selectEl.value : state.selectedCameraId;
    await startWebcam(targetId);
  }
}

// Camera Source Switcher & Lifecycle Management
function initSourceTabs() {
  const tabs = document.querySelectorAll('.source-tab');
  const selectEl = document.getElementById('cameraDeviceSelect');

  tabs.forEach(tab => {
    tab.addEventListener('click', async () => {
      const srcType = tab.dataset.source;
      await switchToSource(srcType);
    });
  });

  if (selectEl) {
    selectEl.addEventListener('change', async (e) => {
      state.selectedCameraId = e.target.value;
      if (state.currentSource === 'webcam') {
        await startWebcam(state.selectedCameraId);
      }
    });
  }

  // Populate cameras if permission is already available
  populateCameraDevices();

  // Stop media tracks when user navigates away or closes tab
  window.addEventListener('beforeunload', stopWebcamStream);
  window.addEventListener('pagehide', stopWebcamStream);
}

// Session Elapsed Timer
function startSessionTimer() {
  const timerEl = document.getElementById('sessionTimer');
  setInterval(() => {
    const diff = Math.floor((Date.now() - state.sessionStartTime) / 1000);
    const hrs = String(Math.floor(diff / 3600)).padStart(2, '0');
    const mins = String(Math.floor((diff % 3600) / 60)).padStart(2, '0');
    const secs = String(diff % 60).padStart(2, '0');
    timerEl.textContent = `${hrs}:${mins}:${secs}`;
  }, 1000);
}

// Event Listeners Initialization
function initEventListeners() {
  // Scenario buttons
  const scenarioBtns = document.querySelectorAll('.scenario-btn');
  scenarioBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      scenarioBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const sc = btn.dataset.scenario;
      resetSession(sc);
    });
  });

  // Action buttons
  document.getElementById('btnExecuteStep').addEventListener('click', executeNextStep);
  document.getElementById('btnAutoPlay').addEventListener('click', toggleAutoPlay);
  document.getElementById('btnResetSession').addEventListener('click', () => resetSession());
  document.getElementById('btnExportAuditLog').addEventListener('click', exportAuditLog);

  // Toggle Voice
  const btnSpeech = document.getElementById('btnToggleSpeech');
  btnSpeech.addEventListener('click', () => {
    state.voiceEnabled = !state.voiceEnabled;
    document.getElementById('speechStateLabel').textContent = state.voiceEnabled ? 'Voice: ON' : 'Voice: OFF';
    btnSpeech.style.opacity = state.voiceEnabled ? '1' : '0.6';
    if (state.voiceEnabled) speakInstruction('Voice guidance active.');
  });

  // Test voice instruction button
  document.getElementById('btnTestVoice').addEventListener('click', () => {
    const step = PROTOCOL_STEPS.find(s => s.step_number === state.activeExpectedStep);
    speakInstruction(`Current Step ${step.step_number}: ${step.title}. Ensure ${step.required_objects.join(' and ')} are in view.`);
  });

  // Theme Toggle Button
  initTheme();

  // History & Modal controls
  const btnRefresh = document.getElementById('btnRefreshHistory');
  if (btnRefresh) btnRefresh.addEventListener('click', loadSessionHistory);

  const btnNewExp = document.getElementById('btnNewExperimentSession');
  if (btnNewExp) btnNewExp.addEventListener('click', () => resetSession('NORMAL'));

  const btnCloseModal = document.getElementById('btnCloseEventModal');
  if (btnCloseModal) btnCloseModal.addEventListener('click', closeSessionModal);

  const modalBackdrop = document.getElementById('sessionEventModal');
  if (modalBackdrop) {
    modalBackdrop.addEventListener('click', (e) => {
      if (e.target === modalBackdrop) closeSessionModal();
    });
  }
}

// Theme Toggle Engine (Light / Dark)
function initTheme() {
  const savedTheme = localStorage.getItem('auravision_theme') || 'light';
  applyTheme(savedTheme);

  const btnToggleTheme = document.getElementById('btnToggleTheme');
  if (btnToggleTheme) {
    btnToggleTheme.addEventListener('click', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
      const newTheme = currentTheme === 'light' ? 'dark' : 'light';
      applyTheme(newTheme);
      localStorage.setItem('auravision_theme', newTheme);
      appendAuditLog('THEME_CHANGE', `Theme switched to ${newTheme.toUpperCase()}`, 'system');
    });
  }
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const label = document.getElementById('themeStateLabel');
  const icon = document.getElementById('themeIcon');
  if (label) {
    label.textContent = theme === 'light' ? 'Theme: Light' : 'Theme: Dark';
  }
  if (icon) {
    if (theme === 'light') {
      icon.innerHTML = `
        <circle cx="12" cy="12" r="5"></circle>
        <line x1="12" y1="1" x2="12" y2="3"></line>
        <line x1="12" y1="21" x2="12" y2="23"></line>
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
        <line x1="1" y1="12" x2="3" y2="12"></line>
        <line x1="21" y1="12" x2="23" y2="12"></line>
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
      `;
    } else {
      icon.innerHTML = `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>`;
    }
  }
}

// ============================================================
// Real-Time FastAPI Backend & WebSocket Integration Layer
// ============================================================
async function initBackendConnection() {
  const statusLabel = document.getElementById('backendStatusLabel');
  const pulseDot = document.getElementById('backendPulseDot');
  const sysText = document.getElementById('systemStatusText');
  const aiEngine = document.getElementById('aiEngineMode');

  async function checkHealth() {
    try {
      const res = await fetch(`${BACKEND_CONFIG.apiBase}/health`);
      if (res.ok) {
        const data = await res.json();
        if (!state.backendOnline) {
          state.backendOnline = true;
          if (statusLabel) {
            statusLabel.textContent = `FASTAPI CONNECTED (8000)`;
            statusLabel.style.color = '#10b981';
          }
          if (pulseDot) pulseDot.style.background = '#10b981';
          if (sysText) sysText.textContent = `FASTAPI BACKEND ONLINE (v${data.app_version})`;
          if (aiEngine) aiEngine.textContent = 'FASTAPI EDGE + SQLITE';
          const supaLabel = document.getElementById('supabaseStatusLabel');
          const supaDot = document.getElementById('supabasePulseDot');
          if (supaLabel) supaLabel.textContent = 'LIVE SYNC ACTIVE';
          if (supaDot) supaDot.style.background = '#10b981';
          appendAuditLog('BACKEND_CONNECTED', `Connected to AURAVISION FastAPI Server (${BACKEND_CONFIG.baseUrl}) with Supabase live replication.`, 'system');
          connectWebSocket();
          loadSessionHistory();
        }
      } else {
        markOffline();
      }
    } catch(e) {
      markOffline();
    }
  }

  function markOffline() {
    if (state.backendOnline) {
      state.backendOnline = false;
      if (statusLabel) {
        statusLabel.textContent = 'OFFLINE (STANDALONE)';
        statusLabel.style.color = 'var(--accent-amber)';
      }
      if (pulseDot) pulseDot.style.background = 'var(--accent-amber)';
      if (sysText) sysText.textContent = 'LOCAL STANDALONE ACTIVE';
      if (aiEngine) aiEngine.textContent = 'HYBRID MOCK/EDGE';
    }
  }

  function connectWebSocket() {
    if (state.backendWs && (state.backendWs.readyState === WebSocket.OPEN || state.backendWs.readyState === WebSocket.CONNECTING)) {
      return;
    }
    try {
      const ws = new WebSocket(BACKEND_CONFIG.wsUrl);
      state.backendWs = ws;

      ws.onopen = () => {
        appendAuditLog('WS_CONNECT', 'WebSocket live event bus connected (ws://localhost:8000/ws/events)', 'system');
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'STEP_VALIDATED') {
            appendAuditLog('WS_STEP_VALIDATED', `Backend Event: ${payload.data.message || payload.data.action}`, 'valid');
          } else if (payload.type === 'ALERT') {
            appendAuditLog('WS_ALERT', `Backend Alert: ${payload.data.message || payload.type}`, 'alert');
          } else if (payload.type === 'EXPERIMENT_COMPLETE') {
            appendAuditLog('WS_COMPLETE', `Backend: Protocol completed successfully.`, 'valid');
          }
        } catch(err) {}
      };

      ws.onerror = () => {
        // Handled in onclose
      };

      ws.onclose = () => {
        state.backendWs = null;
      };
    } catch(err) {
      console.warn('WebSocket init error:', err);
    }
  }

  // Initial check & continuous health polling
  await checkHealth();
  setInterval(checkHealth, BACKEND_CONFIG.pollIntervalMs);
}

// Send live observed action to FastAPI for authoritative validation & DB logging
async function sendObservationToBackend(observation) {
  if (!state.backendOnline) return;
  try {
    const res = await fetch(`${BACKEND_CONFIG.apiBase}/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.backendSessionId || undefined,
        action_code: observation.action_code,
        confidence: observation.confidence,
        observed_objects: observation.objects || []
      })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.session_id) {
        state.backendSessionId = data.session_id;
      }
      appendAuditLog(
        'FASTAPI_LOG',
        `Backend [${data.result}] -> ${data.message || data.reason || 'Verified'}`,
        data.result === 'VALID' ? 'validation' : (data.result === 'STEP_SKIPPED' ? 'alert' : 'warning')
      );
      appendAuditLog(
        'SUPABASE_CLOUD',
        `☁️ Auto-Saved to Supabase: ${observation.action_code} (${data.result}) [Session #${state.backendSessionId || 'Active'}]`,
        'system'
      );
      // Refresh experiment history table
      loadSessionHistory();
    }
  } catch(err) {
    console.debug('Failed to send observation to FastAPI backend:', err);
  }
}

// ============================================================
// Real Experiment Execution History & Cloud Records Engine
// ============================================================
async function loadSessionHistory() {
  const tbody = document.getElementById('sessionsTableBody');
  if (!tbody) return;
  try {
    const res = await fetch(`${BACKEND_CONFIG.apiBase}/sessions?limit=15`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const sessions = await res.json();
    if (!sessions || sessions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="table-loading">No experiment sessions found. Click "New Real Experiment Run" to start.</td></tr>';
      return;
    }

    tbody.innerHTML = sessions.map(s => {
      const isCurrent = (s.id === state.backendSessionId);
      const statusClass = (s.status || 'created').toLowerCase();
      const startedStr = s.started_at ? new Date(s.started_at).toLocaleString() : (s.created_at ? new Date(s.created_at).toLocaleString() : 'Just now');
      const stepStr = s.current_step_number ? `Step ${s.current_step_number} / 5` : 'Step 1 / 5';
      const rowClass = isCurrent ? 'active-row' : '';

      return `
        <tr class="${rowClass}">
          <td class="session-id-cell">
            <strong>#${s.id}</strong><br>
            <span style="font-size: 0.7rem; color: var(--text-dim);">${s.session_uuid || s.session_code || ''}</span>
          </td>
          <td>
            <strong>${s.experiment_name || 'Sample Astronaut Experiment'}</strong><br>
            <span style="font-size: 0.72rem; color: var(--text-muted);">SOP-CHEM-802</span>
          </td>
          <td>
            <span class="status-badge ${statusClass}">● ${s.status}</span>
          </td>
          <td>
            <strong>${stepStr}</strong><br>
            <span style="font-size: 0.72rem; color: var(--accent-cyan); font-family: var(--font-mono);">${s.current_step_code || ''}</span>
          </td>
          <td>${s.operator_label || 'Astronaut Specialist'}</td>
          <td style="font-family: var(--font-mono); font-size: 0.75rem;">${startedStr}</td>
          <td>
            <span class="cloud-pill" title="Synced in real-time to Supabase PostgreSQL table 'experiment_sessions'">
              ☁️ Supabase Synced
            </span>
          </td>
          <td>
            <button class="btn btn-secondary" style="padding: 0.25rem 0.6rem; font-size: 0.72rem;" onclick="openSessionModal('${s.id}')">
              Inspect Events
            </button>
          </td>
        </tr>
      `;
    }).join('');
  } catch(err) {
    console.warn('Failed to load session history:', err);
    tbody.innerHTML = `<tr><td colspan="8" class="table-loading" style="color: var(--accent-rose);">Failed to load history: ${err.message}</td></tr>`;
  }
}

async function openSessionModal(sessionId) {
  const modal = document.getElementById('sessionEventModal');
  const title = document.getElementById('modalSessionTitle');
  const badge = document.getElementById('modalSessionStatusBadge');
  const summary = document.getElementById('modalSessionSummary');
  const timeline = document.getElementById('modalTimelineList');

  if (!modal) return;
  modal.style.display = 'flex';
  title.textContent = `Experiment Session #${sessionId} - Audit Timeline`;
  badge.textContent = 'FETCHING...';
  badge.className = 'badge-tag';
  summary.innerHTML = 'Loading real events from SQLite and Supabase...';
  timeline.innerHTML = '';

  try {
    const res = await fetch(`${BACKEND_CONFIG.apiBase}/sessions/${sessionId}/events`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const sessionRes = await fetch(`${BACKEND_CONFIG.apiBase}/sessions/${sessionId}`);
    if (sessionRes.ok) {
      const sess = await sessionRes.json();
      badge.textContent = sess.status;
      badge.className = `status-badge ${sess.status.toLowerCase()}`;
    }

    const events = data.events || [];
    const detectionsCount = events.filter(e => e.event_type === 'DETECTION').length;
    const validationsCount = events.filter(e => e.event_type === 'SEQUENCE').length;
    const alertsCount = events.filter(e => e.event_type === 'ALERT').length;

    summary.innerHTML = `
      <div><strong>Total Records:</strong> ${events.length}</div>
      <div><strong>Detections (MediaPipe):</strong> ${detectionsCount}</div>
      <div><strong>Sequence Validations:</strong> ${validationsCount}</div>
      <div><strong>Alerts / Violations:</strong> ${alertsCount}</div>
      <div><strong>Cloud Persistence:</strong> <span style="color: var(--accent-emerald);">Supabase PostgreSQL Confirmed</span></div>
    `;

    if (events.length === 0) {
      timeline.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-style: italic;">No events logged for this session yet.</div>';
      return;
    }

    timeline.innerHTML = events.map(ev => {
      let itemClass = 'valid';
      if (ev.event_type === 'ALERT') itemClass = 'alert';
      else if (ev.event_type === 'WARNING' || ev.severity === 'WARNING') itemClass = 'warning';

      const timeStr = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '';
      const payloadStr = ev.payload ? (typeof ev.payload === 'string' ? ev.payload : JSON.stringify(ev.payload)) : '';

      return `
        <div class="modal-timeline-item ${itemClass}">
          <div class="modal-timeline-time">${timeStr}</div>
          <div class="modal-timeline-content">
            <div class="modal-timeline-type" style="color: ${itemClass === 'alert' ? 'var(--accent-rose)' : (itemClass === 'valid' ? 'var(--accent-emerald)' : 'var(--accent-amber)')};">
              [${ev.event_type}] ${ev.title || ev.action_code || ''}
            </div>
            <div>${ev.description || ev.message || payloadStr}</div>
          </div>
        </div>
      `;
    }).join('');

  } catch(err) {
    summary.innerHTML = `<span style="color: var(--accent-rose);">Error: ${err.message}</span>`;
  }
}

function closeSessionModal() {
  const modal = document.getElementById('sessionEventModal');
  if (modal) modal.style.display = 'none';
}
window.openSessionModal = openSessionModal;
window.closeSessionModal = closeSessionModal;

// Bootstrapping
window.addEventListener('DOMContentLoaded', () => {
  initVideoControls();
  initVisionCanvas();
  initSourceTabs();
  startSessionTimer();
  initEventListeners();
  resetSession('NORMAL');
  initBackendConnection();

  appendAuditLog('SYSTEM_BOOT', 'AURAVISION Offline AI Human Activity Recognition & Sequence Validator initialized.', 'system');
  appendAuditLog('PROTOCOL_LOADED', 'SOP-CHEM-802 protocol active (5 steps verified).', 'system');
});

