import React, { useState, useEffect } from 'react';
import {
  ClipboardList,
  Download,
  Filter,
  Search,
  CheckCircle,
  AlertTriangle,
  AlertOctagon,
  Info,
  Calendar,
  Clock,
  FileText
} from 'lucide-react';
import { apiService } from '../services/api';
import type { ExperimentSession, AuditLogItem } from '../types';
import { MOCK_SESSION, MOCK_AUDIT_LOGS } from '../services/mockData';

export const SessionsAudit: React.FC = () => {
  const [sessions, setSessions] = useState<ExperimentSession[]>([MOCK_SESSION]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>(MOCK_SESSION.id);
  const [activeTab, setActiveTab] = useState<'all' | 'sequence' | 'detections' | 'alerts' | 'system'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [logs, setLogs] = useState<AuditLogItem[]>(MOCK_AUDIT_LOGS);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const list = await apiService.getSessions();
        if (list.length > 0) {
          setSessions(list);
          setSelectedSessionId(list[0].id);
        }
      } catch {
        // Fallback to mock
      }
    };
    fetchSessions();
  }, []);

  useEffect(() => {
    const fetchLogs = async () => {
      setIsLoading(true);
      try {
        let events: AuditLogItem[] = [];
        if (activeTab === 'all') {
          events = await apiService.getSessionEvents(selectedSessionId);
        } else if (activeTab === 'sequence') {
          events = await apiService.getSessionSequenceEvents(selectedSessionId);
        } else if (activeTab === 'detections') {
          events = await apiService.getSessionDetections(selectedSessionId);
        } else if (activeTab === 'alerts') {
          const rawAlerts = await apiService.getSessionAlerts(selectedSessionId);
          events = rawAlerts.map((a) => ({
            id: a.id,
            timestamp: a.timestamp,
            type: a.type,
            message: a.message,
            severity: a.severity,
            category: 'alerts' as const,
          }));
        } else if (activeTab === 'system') {
          events = await apiService.getSessionSystemEvents(selectedSessionId);
        }
        if (events && events.length > 0) {
          setLogs(events);
        } else {
          setLogs(MOCK_AUDIT_LOGS.filter((item) => activeTab === 'all' || item.category === activeTab));
        }
      } catch {
        setLogs(MOCK_AUDIT_LOGS.filter((item) => activeTab === 'all' || item.category === activeTab));
      } finally {
        setIsLoading(false);
      }
    };
    fetchLogs();
  }, [selectedSessionId, activeTab]);

  const filteredLogs = logs.filter((log) => {
    const matchesSearch =
      log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.type.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  // Client-side local file export for air-gapped / offline mission compliance
  const exportAsFile = (content: string, filename: string, mime: string) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDownloadTxt = () => {
    let output = `=================================================================\n`;
    output += `AURAVISION ISRO MISSION AUDIT LOG — SESSION ${selectedSessionId}\n`;
    output += `Export Time: ${new Date().toISOString()}\n`;
    output += `Category: ${activeTab.toUpperCase()}\n`;
    output += `=================================================================\n\n`;

    filteredLogs.forEach((l) => {
      output += `[${l.timestamp}] [${l.severity.toUpperCase()}] [${l.type}] ${l.message}\n`;
    });

    exportAsFile(output, `AURAVISION_AUDIT_${selectedSessionId}.txt`, 'text/plain');
  };

  const handleDownloadJsonl = () => {
    const jsonl = filteredLogs.map((item) => JSON.stringify(item)).join('\n');
    exportAsFile(jsonl, `AURAVISION_AUDIT_${selectedSessionId}.jsonl`, 'application/x-ndjson');
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
            <ClipboardList size={20} color="var(--cyan)" />
            <h2 style={{ fontSize: '18px', color: '#fff', margin: 0 }}>
              Mission Sessions & Verification Audit
            </h2>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
            Deterministic flight logs, sequence compliance timestamps, and detection histories.
          </p>
        </div>

        {/* Download Buttons */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" onClick={handleDownloadTxt}>
            <Download size={14} />
            <span>Export TXT Log</span>
          </button>
          <button className="btn btn-cyan" onClick={handleDownloadJsonl}>
            <FileText size={14} />
            <span>Export JSONL</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Sessions List on Left, Tabbed Events on Right */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 2.5fr)', gap: 16 }}>
        {/* Sessions Column */}
        <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h3 style={{ fontSize: '14px', color: '#fff', margin: 0 }}>Mission Sessions</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {sessions.map((ses) => {
              const isSelected = ses.id === selectedSessionId;
              return (
                <div
                  key={ses.id}
                  onClick={() => setSelectedSessionId(ses.id)}
                  style={{
                    padding: '12px',
                    borderRadius: 'var(--radius-md)',
                    background: isSelected ? 'rgba(0, 229, 255, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                    border: `1px solid ${isSelected ? 'var(--cyan)' : 'var(--border-subtle)'}`,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong className="font-mono" style={{ fontSize: '13px', color: isSelected ? 'var(--cyan)' : '#fff' }}>
                      {ses.session_code}
                    </strong>
                    <span
                      className={`badge ${
                        ses.status === 'RUNNING'
                          ? 'badge-valid'
                          : ses.status === 'PAUSED'
                          ? 'badge-warning'
                          : 'badge-muted'
                      }`}
                      style={{ fontSize: '9px' }}
                    >
                      {ses.status}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)', marginTop: 6 }}>
                    <span>Step {ses.current_step_number}</span>
                    <span style={{ color: 'var(--valid)' }}>{ses.compliance_rate || 96}% Compliance</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Audit Events Viewer with Filter Tabs */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Tabs */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12, flexWrap: 'wrap', gap: 8 }}>
            <div style={{ display: 'flex', gap: 6 }}>
              {[
                { id: 'all', label: 'All Events' },
                { id: 'sequence', label: 'Sequence Events' },
                { id: 'detections', label: 'Detections' },
                { id: 'alerts', label: 'Alerts' },
                { id: 'system', label: 'System Events' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  className={`btn ${activeTab === tab.id ? 'btn-cyan' : 'btn-ghost'}`}
                  style={{ padding: '6px 12px', fontSize: '12px' }}
                  onClick={() => setActiveTab(tab.id as any)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Search Filter */}
            <div style={{ position: 'relative', width: '220px' }}>
              <Search size={14} style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Filter logs..."
                className="input-field"
                style={{ paddingLeft: '30px', fontSize: '12px' }}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>

          {/* Table / Event Stream */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: '520px', overflowY: 'auto' }}>
            {filteredLogs.length === 0 ? (
              <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
                No audit events recorded under this filter.
              </div>
            ) : (
              filteredLogs.map((item) => {
                const isCrit = item.severity === 'critical';
                const isWarn = item.severity === 'warning';
                const isValid = item.severity === 'valid';

                return (
                  <div
                    key={item.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '10px 14px',
                      background: 'rgba(0, 0, 0, 0.25)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      fontSize: '12px',
                    }}
                  >
                    {/* Timestamp */}
                    <span className="font-mono" style={{ color: 'var(--text-muted)', fontSize: '11px', width: '64px' }}>
                      {item.timestamp}
                    </span>

                    {/* Status Icon */}
                    {isValid ? (
                      <CheckCircle size={15} color="var(--valid)" />
                    ) : isWarn ? (
                      <AlertTriangle size={15} color="var(--warning)" />
                    ) : isCrit ? (
                      <AlertOctagon size={15} color="var(--critical)" />
                    ) : (
                      <Info size={15} color="var(--cyan)" />
                    )}

                    {/* Type Badge */}
                    <span
                      className={`badge ${
                        isValid
                          ? 'badge-valid'
                          : isWarn
                          ? 'badge-warning'
                          : isCrit
                          ? 'badge-critical'
                          : 'badge-cyan'
                      } font-mono`}
                      style={{ fontSize: '10px' }}
                    >
                      {item.type}
                    </span>

                    {/* Message */}
                    <div style={{ flex: 1, color: '#f8fafc' }}>
                      {item.message}
                    </div>

                    {/* Category pill */}
                    <span className="badge badge-muted" style={{ fontSize: '9px' }}>
                      {item.category}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
