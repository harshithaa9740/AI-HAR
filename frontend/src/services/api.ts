/**
 * AURAVISION — Unified Local-First API Service Layer
 * Connects to dynamic backend IP and seamlessly falls back to realistic offline mock data.
 */

import { BackendConfigManager } from '../config/backendConfig';
import type { 
  ExperimentProtocol, 
  ExperimentSession, 
  AuditLogItem, 
  AIModelStatus, 
  SystemSettingsData,
  ValidationAlert,
  DemoScenarioType
} from '../types';
import {
  MOCK_EXPERIMENTS_LIST,
  MOCK_EXPERIMENT_PROTOCOL,
  MOCK_ACTIVE_SESSION,
  MOCK_RECENT_SESSIONS,
  MOCK_AUDIT_LOGS,
  MOCK_MODEL_STATUS,
  MOCK_SYSTEM_SETTINGS,
  MOCK_DEMO_SCENARIOS
} from './mockData';

class ApiService {
  private timeoutMs = 3500;

  private async fetchWithTimeout(url: string, options: RequestInit = {}): Promise<Response> {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(options.headers || {})
        }
      });
      clearTimeout(id);
      return response;
    } catch (err) {
      clearTimeout(id);
      throw err;
    }
  }

  // ========================================================
  // Connection Diagnostics
  // ========================================================

  async testConnection(ip: string, port: number): Promise<{ success: boolean; data?: any; error?: string }> {
    const url = `http://${ip}:${port}/api/health`;
    try {
      const res = await this.fetchWithTimeout(url);
      if (!res.ok) {
        return { success: false, error: `Backend responded with HTTP ${res.status}` };
      }
      const data = await res.json();
      return { success: true, data };
    } catch (err: any) {
      return { 
        success: false, 
        error: err.name === 'AbortError' 
          ? 'Connection timed out. Check IP & port.' 
          : 'Failed to reach server. Verify host device is on the same Wi-Fi/LAN.'
      };
    }
  }

  async checkHealth(): Promise<{ isOnline: boolean; details?: any }> {
    try {
      const url = `${BackendConfigManager.getApiBaseUrl()}/health`;
      const res = await this.fetchWithTimeout(url);
      if (res.ok) {
        const details = await res.json();
        return { isOnline: true, details };
      }
      return { isOnline: false };
    } catch {
      return { isOnline: false };
    }
  }

  async getHealth(): Promise<{ status: string; [key: string]: any }> {
    try {
      const url = `${BackendConfigManager.getApiBaseUrl()}/health`;
      const res = await this.fetchWithTimeout(url);
      if (res.ok) return await res.json();
    } catch {}
    return { status: 'ok', offline: true };
  }

  async getSystemStatus(): Promise<any> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/system/status`);
      if (res.ok) return await res.json();
    } catch {}
    return {
      status: 'offline_preview',
      app_name: 'AURAVISION-Client',
      ai_mode: 'mock',
      offline_guarantee: true,
      database_connected: true
    };
  }

  // ========================================================
  // Experiments & Protocols
  // ========================================================

  async getExperiments(): Promise<ExperimentProtocol[]> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/experiments`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) return data;
      }
    } catch {}
    return MOCK_EXPERIMENTS_LIST;
  }

  async getExperiment(id: string): Promise<ExperimentProtocol> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/experiments/${id}`);
      if (res.ok) return await res.json();
    } catch {}
    const found = MOCK_EXPERIMENTS_LIST.find(e => e.id === id);
    return found || MOCK_EXPERIMENT_PROTOCOL;
  }

  async createExperiment(payload: Partial<ExperimentProtocol>): Promise<ExperimentProtocol> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/experiments`, {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      if (res.ok) return await res.json();
    } catch {}

    const newExp: ExperimentProtocol = {
      id: `exp-user-${Date.now().toString(36)}`,
      name: payload.name || 'Untitled Protocol',
      description: payload.description || '',
      version: payload.version || '1.0.0',
      steps_count: payload.steps?.length || 0,
      steps: payload.steps || [],
      created_at: new Date().toISOString()
    };
    MOCK_EXPERIMENTS_LIST.unshift(newExp);
    return newExp;
  }

  async updateExperiment(id: string, payload: Partial<ExperimentProtocol>): Promise<ExperimentProtocol> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/experiments/${id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      if (res.ok) return await res.json();
    } catch {}

    const idx = MOCK_EXPERIMENTS_LIST.findIndex(e => e.id === id);
    if (idx !== -1) {
      MOCK_EXPERIMENTS_LIST[idx] = { ...MOCK_EXPERIMENTS_LIST[idx], ...payload, updated_at: new Date().toISOString() };
      return MOCK_EXPERIMENTS_LIST[idx];
    }
    return MOCK_EXPERIMENT_PROTOCOL;
  }

  async deleteExperiment(id: string): Promise<boolean> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/experiments/${id}`, {
        method: 'DELETE'
      });
      if (res.ok) return true;
    } catch {}

    const idx = MOCK_EXPERIMENTS_LIST.findIndex(e => e.id === id);
    if (idx !== -1) {
      MOCK_EXPERIMENTS_LIST.splice(idx, 1);
      return true;
    }
    return false;
  }

  // ========================================================
  // Sessions & Lifecycle
  // ========================================================

  async getSessions(): Promise<ExperimentSession[]> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) return data;
      }
    } catch {}
    return MOCK_RECENT_SESSIONS;
  }

  async getSession(id: string): Promise<ExperimentSession> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${id}`);
      if (res.ok) return await res.json();
    } catch {}
    const found = MOCK_RECENT_SESSIONS.find(s => s.id === id);
    return found || MOCK_ACTIVE_SESSION;
  }

  async startSession(experimentId: string, sessionCode?: string): Promise<ExperimentSession> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/start`, {
        method: 'POST',
        body: JSON.stringify({
          experiment_id: experimentId,
          session_code: sessionCode || `EXP-${Date.now().toString(36).toUpperCase()}`
        })
      });
      if (res.ok) return await res.json();
    } catch {}

    const newSess: ExperimentSession = {
      id: `sess-${Date.now().toString(36)}`,
      experiment_id: experimentId,
      session_code: sessionCode || `EXP-LOCAL-${Date.now().toString(36).toUpperCase()}`,
      status: 'RUNNING',
      current_step_number: 1,
      current_step_code: 'STEP_01',
      expected_next_step: 'STEP_01 / Pick Tool',
      started_at: new Date().toISOString(),
      compliance_rate: 100
    };
    MOCK_RECENT_SESSIONS.unshift(newSess);
    return newSess;
  }

  async pauseSession(id: string): Promise<ExperimentSession> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${id}/pause`, { method: 'POST' });
      if (res.ok) return await res.json();
    } catch {}
    return { ...MOCK_ACTIVE_SESSION, status: 'PAUSED' };
  }

  async resumeSession(id: string): Promise<ExperimentSession> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${id}/resume`, { method: 'POST' });
      if (res.ok) return await res.json();
    } catch {}
    return { ...MOCK_ACTIVE_SESSION, status: 'RUNNING' };
  }

  async stopSession(id: string): Promise<ExperimentSession> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${id}/stop`, { method: 'POST' });
      if (res.ok) return await res.json();
    } catch {}
    return { ...MOCK_ACTIVE_SESSION, status: 'STOPPED', ended_at: new Date().toISOString() };
  }

  async resetSession(id: string): Promise<ExperimentSession> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${id}/reset`, { method: 'POST' });
      if (res.ok) return await res.json();
    } catch {}
    return { ...MOCK_ACTIVE_SESSION, current_step_number: 1, status: 'RUNNING' };
  }

  // ========================================================
  // Validation & Processing
  // ========================================================

  async validateAction(
    actionCode: string, 
    confidence: number = 0.95, 
    observedObjects: string[] = ['tool'], 
    sessionId?: string
  ): Promise<any> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/validate`, {
        method: 'POST',
        body: JSON.stringify({
          action_code: actionCode,
          confidence,
          observed_objects: observedObjects,
          session_id: sessionId
        })
      });
      if (res.ok) return await res.json();
    } catch {}

    // Mock deterministic state evaluation
    return {
      result: 'VALID',
      observed_action: actionCode,
      confidence,
      completed_step: 1,
      next_step: 2,
      next_step_name: 'Open Container',
      message: `Step action confirmed: ${actionCode}. Proceed to Step 2.`
    };
  }

  async getSessionEvents(sessionId: string): Promise<AuditLogItem[]> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${sessionId}/events`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) return data;
        if (data && Array.isArray(data.events)) {
          return data.events.map((e: any) => ({
            id: e.id ? String(e.id) : (e.event_id || `evt-${Math.random()}`),
            timestamp: e.timestamp || e.created_at || new Date().toISOString(),
            type: e.event_type || e.result || 'EVENT',
            message: e.message || e.reason || (e.action_code ? `Action: ${e.action_code}` : 'Event recorded'),
            severity: (e.severity || 'info').toLowerCase() === 'warning' ? 'warning' : (e.severity || '').toLowerCase() === 'critical' ? 'critical' : (e.result === 'VALID' ? 'valid' : 'info'),
            category: (e.component || e.category || 'all') as any
          }));
        }
      }
    } catch {}
    return [];
  }

  async getSessionAlerts(sessionId: string): Promise<ValidationAlert[]> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${sessionId}/alerts`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          return data.map((a: any) => ({
            id: String(a.id),
            timestamp: a.timestamp || a.created_at || new Date().toISOString(),
            type: a.alert_type || 'ALERT',
            title: a.alert_type || 'Alert',
            message: a.message,
            severity: (a.severity || 'warning').toLowerCase(),
            step_number: a.step_number || undefined,
            acknowledged: a.acknowledged || false
          }));
        }
      }
    } catch {}
    return [];
  }

  async acknowledgeAlert(sessionId: string, alertId: number | string): Promise<any> {
    try {
      const res = await this.fetchWithTimeout(
        `${BackendConfigManager.getApiBaseUrl()}/sessions/${sessionId}/alerts/${alertId}/acknowledge`,
        { method: 'POST' }
      );
      if (res.ok) return await res.json();
    } catch {}
    return { id: alertId, acknowledged: true };
  }

  async getSessionArtifacts(sessionId: string, artifactType?: string): Promise<any[]> {
    try {
      const query = artifactType ? `?artifact_type=${encodeURIComponent(artifactType)}` : '';
      const res = await this.fetchWithTimeout(
        `${BackendConfigManager.getApiBaseUrl()}/sessions/${sessionId}/artifacts${query}`
      );
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) return data;
      }
    } catch {}
    return [];
  }

  async getSessionSequenceEvents(sessionId: string): Promise<AuditLogItem[]> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${sessionId}/sequence-events`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) return data;
      }
    } catch {}
    return MOCK_AUDIT_LOGS.filter(e => e.category === 'sequence');
  }

  async getSessionDetections(sessionId: string): Promise<AuditLogItem[]> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${sessionId}/detections`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) return data;
      }
    } catch {}
    return MOCK_AUDIT_LOGS.filter(e => e.category === 'detections');
  }

  async getSessionSystemEvents(sessionId: string): Promise<AuditLogItem[]> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${sessionId}/system-events`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) return data;
      }
    } catch {}
    return MOCK_AUDIT_LOGS.filter(e => e.category === 'system');
  }

  // ========================================================
  // Camera & Real-Time Processing
  // ========================================================

  async startCamera(sourceType: string = 'mock'): Promise<any> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/camera/start`, {
        method: 'POST',
        body: JSON.stringify({ source_type: sourceType })
      });
      if (res.ok) return await res.json();
    } catch {}
    return { state: 'RUNNING', source: sourceType };
  }

  async stopCamera(): Promise<any> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/camera/stop`, { method: 'POST' });
      if (res.ok) return await res.json();
    } catch {}
    return { state: 'STOPPED' };
  }

  async startProcessing(sessionId: string, targetFps: number = 20): Promise<any> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${sessionId}/processing/start`, {
        method: 'POST',
        body: JSON.stringify({ target_fps: targetFps })
      });
      if (res.ok) return await res.json();
    } catch {}
    return { state: 'RUNNING', worker_active: true };
  }

  async stopProcessing(sessionId: string): Promise<any> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${sessionId}/processing/stop`, {
        method: 'POST'
      });
      if (res.ok) return await res.json();
    } catch {}
    return { state: 'STOPPED', worker_active: false };
  }

  async getProcessingMetrics(sessionId: string): Promise<any> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/sessions/${sessionId}/processing/metrics`);
      if (res.ok) return await res.json();
    } catch {}
    return {
      frames_received: 14820,
      frames_processed: 14812,
      frames_dropped: 8,
      processing_fps: 29.6,
      average_latency_ms: 18.4
    };
  }

  // ========================================================
  // AI Models
  // ========================================================

  async getModelsStatus(): Promise<AIModelStatus> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/models/status`);
      if (res.ok) return await res.json();
    } catch {}
    return MOCK_MODEL_STATUS;
  }

  async getActiveModel(): Promise<AIModelStatus> {
    return this.getModelsStatus();
  }

  // ========================================================
  // Demonstration Scenarios
  // ========================================================

  async getDemoScenarios(): Promise<any[]> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/demo/scenarios`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) return data;
      }
    } catch {}
    return MOCK_DEMO_SCENARIOS;
  }

  async startDemo(scenario: DemoScenarioType, speedMultiplier: number = 1.0): Promise<any> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/demo/start`, {
        method: 'POST',
        body: JSON.stringify({ scenario, speed_multiplier: speedMultiplier })
      });
      if (res.ok) return await res.json();
    } catch {}
    return { success: true, scenario, active: true };
  }

  async stopDemo(): Promise<any> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/demo/stop`, { method: 'POST' });
      if (res.ok) return await res.json();
    } catch {}
    return { success: true, active: false };
  }

  // ========================================================
  // Settings
  // ========================================================

  async getSettings(): Promise<SystemSettingsData> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/settings`);
      if (res.ok) return await res.json();
    } catch {}
    return MOCK_SYSTEM_SETTINGS;
  }

  async updateSettings(payload: Partial<SystemSettingsData>): Promise<SystemSettingsData> {
    try {
      const res = await this.fetchWithTimeout(`${BackendConfigManager.getApiBaseUrl()}/settings`, {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      if (res.ok) return await res.json();
    } catch {}
    return { ...MOCK_SYSTEM_SETTINGS, ...payload };
  }

  // ========================================================
  // Audit Log Export
  // ========================================================

  async downloadSessionLog(sessionId: string, format: 'txt' | 'jsonl' = 'jsonl'): Promise<string> {
    try {
      const url = `${BackendConfigManager.getApiBaseUrl()}/sessions/${sessionId}/log?format=${format}&download=false`;
      const res = await this.fetchWithTimeout(url);
      if (res.ok) return await res.text();
    } catch {}

    // Fallback export format
    if (format === 'jsonl') {
      return MOCK_AUDIT_LOGS.map(item => JSON.stringify(item)).join('\n');
    }
    return MOCK_AUDIT_LOGS.map(item => `[${item.timestamp}] [${item.type}] ${item.message}`).join('\n');
  }
}

export const api = new ApiService();
export const apiService = api;
export default api;
