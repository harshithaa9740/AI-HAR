import React, { useState, useEffect } from 'react';
import {
  FlaskConical,
  Plus,
  Trash2,
  Edit2,
  Check,
  X,
  AlertCircle,
  FileCheck,
  ArrowDown,
  Layers,
  Save,
  RotateCcw
} from 'lucide-react';
import { apiService } from '../services/api';
import type { ExperimentProtocol, ProtocolStep } from '../types';
import { MOCK_PROTOCOL } from '../services/mockData';

export const Experiments: React.FC = () => {
  const [protocols, setProtocols] = useState<ExperimentProtocol[]>([MOCK_PROTOCOL]);
  const [selectedProtocol, setSelectedProtocol] = useState<ExperimentProtocol>(MOCK_PROTOCOL);
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<ExperimentProtocol>(MOCK_PROTOCOL);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    const loadProtocols = async () => {
      try {
        const list = await apiService.getExperiments();
        if (list.length > 0) {
          setProtocols(list);
          setSelectedProtocol(list[0]);
          setEditForm(list[0]);
        }
      } catch {
        // Use default
      }
    };
    loadProtocols();
  }, []);

  const handleSelectProtocol = (p: ExperimentProtocol) => {
    setSelectedProtocol(p);
    setEditForm(p);
    setIsEditing(false);
    setValidationError(null);
  };

  const handleAddNewStep = () => {
    const nextStepNum = editForm.steps.length + 1;
    const newStep: ProtocolStep = {
      step_number: nextStepNum,
      action_code: 'NEW_ACTION',
      display_name: `Step ${nextStepNum}: Inspect Workspace`,
      description: 'Perform visual inspection of sterile workbench',
      expected_objects: ['workspace'],
      required: true,
    };

    setEditForm({
      ...editForm,
      steps_count: nextStepNum,
      steps: [...editForm.steps, newStep],
    });
  };

  const handleRemoveStep = (indexToRemove: number) => {
    const updatedSteps = editForm.steps
      .filter((_, idx) => idx !== indexToRemove)
      .map((st, idx) => ({ ...st, step_number: idx + 1 }));

    setEditForm({
      ...editForm,
      steps_count: updatedSteps.length,
      steps: updatedSteps,
    });
  };

  const handleUpdateStep = (index: number, field: keyof ProtocolStep, value: any) => {
    const updatedSteps = [...editForm.steps];
    updatedSteps[index] = { ...updatedSteps[index], [field]: value };
    setEditForm({ ...editForm, steps: updatedSteps });
  };

  const handleSaveProtocol = async () => {
    // Protocol validation
    if (!editForm.name.trim()) {
      setValidationError('Protocol name cannot be empty');
      return;
    }
    if (editForm.steps.length === 0) {
      setValidationError('Protocol must have at least one step');
      return;
    }

    try {
      const saved = await apiService.createExperiment(editForm);
      setProtocols((prev) => {
        const existingIdx = prev.findIndex((p) => p.id === saved.id);
        if (existingIdx >= 0) {
          const copy = [...prev];
          copy[existingIdx] = saved;
          return copy;
        }
        return [...prev, saved];
      });
      setSelectedProtocol(saved);
      setIsEditing(false);
      setValidationError(null);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch {
      // Local state fallback
      setSelectedProtocol(editForm);
      setIsEditing(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    }
  };

  const handleCreateNewProtocol = () => {
    const newProto: ExperimentProtocol = {
      id: `BAS-PROTO-${Date.now().toString().slice(-4)}`,
      name: 'New Spaceflight Procedure',
      description: 'Standard operational protocol for microgravity validation',
      version: '1.0.0',
      steps_count: 2,
      steps: [
        {
          step_number: 1,
          action_code: 'PICK_TOOL',
          display_name: 'Pick instrument',
          description: 'Grasp calibrated instrument',
          expected_objects: ['tool'],
          required: true,
        },
        {
          step_number: 2,
          action_code: 'RETURN_TOOL',
          display_name: 'Return instrument',
          description: 'Return instrument to magnetic rack',
          expected_objects: ['tool', 'rack'],
          required: true,
        },
      ],
    };
    setEditForm(newProto);
    setSelectedProtocol(newProto);
    setIsEditing(true);
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
            <FlaskConical size={20} color="var(--cyan)" />
            <h2 style={{ fontSize: '18px', color: '#fff', margin: 0 }}>
              Experiment Protocols & Sequence Builder
            </h2>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
            Define deterministic, verified step sequences for automated AI Human Activity Recognition.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          {!isEditing ? (
            <>
              <button className="btn btn-secondary" onClick={handleCreateNewProtocol}>
                <Plus size={14} />
                <span>New Protocol</span>
              </button>
              <button className="btn btn-cyan" onClick={() => setIsEditing(true)}>
                <Edit2 size={14} />
                <span>Edit Current Protocol</span>
              </button>
            </>
          ) : (
            <>
              <button
                className="btn btn-ghost"
                onClick={() => {
                  setEditForm(selectedProtocol);
                  setIsEditing(false);
                }}
              >
                <RotateCcw size={14} />
                <span>Cancel</span>
              </button>
              <button className="btn btn-primary" onClick={handleSaveProtocol}>
                <Save size={14} />
                <span>Save Protocol Changes</span>
              </button>
            </>
          )}
        </div>
      </div>

      {saveSuccess && (
        <div
          style={{
            padding: '10px 14px',
            background: 'var(--valid-bg)',
            border: '1px solid var(--valid)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--valid)',
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <FileCheck size={16} />
          <span>Protocol successfully saved and synchronized locally!</span>
        </div>
      )}

      {validationError && (
        <div
          style={{
            padding: '10px 14px',
            background: 'var(--critical-bg)',
            border: '1px solid var(--critical)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--critical)',
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <AlertCircle size={16} />
          <span>{validationError}</span>
        </div>
      )}

      {/* Main Content Layout: Sidebar of Protocols + Step Sequence Builder */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 2.5fr)', gap: 16 }}>
        {/* Left: Protocol Library */}
        <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h3 style={{ fontSize: '14px', color: '#fff', margin: 0 }}>Available Protocols</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {protocols.map((p) => {
              const isSelected = p.id === selectedProtocol.id;
              return (
                <div
                  key={p.id}
                  onClick={() => handleSelectProtocol(p)}
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
                    <strong style={{ fontSize: '13px', color: isSelected ? 'var(--cyan)' : '#fff' }}>
                      {p.name}
                    </strong>
                    <span className="badge badge-muted" style={{ fontSize: '9px' }}>
                      v{p.version}
                    </span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: 4 }}>
                    {p.steps_count} Sequential Steps
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Step Sequence Editor */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Protocol Info Header */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                PROTOCOL TITLE
              </label>
              {isEditing ? (
                <input
                  type="text"
                  className="input-field"
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                />
              ) : (
                <div style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>{selectedProtocol.name}</div>
              )}
            </div>

            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                PROTOCOL CODE / ID
              </label>
              <div className="font-mono" style={{ fontSize: '14px', color: 'var(--cyan)', paddingTop: 4 }}>
                {selectedProtocol.id}
              </div>
            </div>
          </div>

          <div>
            <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
              DESCRIPTION
            </label>
            {isEditing ? (
              <textarea
                className="input-field"
                rows={2}
                value={editForm.description}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
              />
            ) : (
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>
                {selectedProtocol.description}
              </p>
            )}
          </div>

          <hr style={{ borderColor: 'var(--border-subtle)', margin: '4px 0' }} />

          {/* Sequential Steps List */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '14px', color: '#fff', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Layers size={16} color="var(--cyan)" />
              <span>Step-by-Step Action Sequence ({editForm.steps.length} Steps)</span>
            </h3>

            {isEditing && (
              <button className="btn btn-secondary btn-icon" onClick={handleAddNewStep} title="Add New Step">
                <Plus size={16} />
              </button>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {(isEditing ? editForm.steps : selectedProtocol.steps).map((step, idx) => (
              <div
                key={step.step_number || idx}
                style={{
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '14px',
                  display: 'flex',
                  gap: 14,
                  alignItems: 'flex-start',
                }}
              >
                {/* Step Number Circle */}
                <div
                  className="step-node"
                  style={{
                    width: 32,
                    height: 32,
                    background: 'rgba(0, 229, 255, 0.1)',
                    border: '1px solid var(--cyan)',
                    color: 'var(--cyan)',
                    fontSize: '12px',
                  }}
                >
                  {step.step_number}
                </div>

                {/* Step Form / Display */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    {isEditing ? (
                      <>
                        <input
                          type="text"
                          className="input-field"
                          style={{ flex: 2 }}
                          placeholder="Display Name (e.g. Open Container)"
                          value={step.display_name}
                          onChange={(e) => handleUpdateStep(idx, 'display_name', e.target.value)}
                        />
                        <input
                          type="text"
                          className="input-field font-mono"
                          style={{ flex: 1 }}
                          placeholder="ACTION_CODE"
                          value={step.action_code}
                          onChange={(e) => handleUpdateStep(idx, 'action_code', e.target.value)}
                        />
                      </>
                    ) : (
                      <>
                        <strong style={{ fontSize: '13px', color: '#fff' }}>{step.display_name}</strong>
                        <span className="badge badge-cyan font-mono">{step.action_code}</span>
                      </>
                    )}

                    {isEditing && (
                      <button
                        className="btn btn-ghost btn-icon"
                        style={{ color: 'var(--critical)' }}
                        onClick={() => handleRemoveStep(idx)}
                        title="Delete Step"
                      >
                        <Trash2 size={15} />
                      </button>
                    )}
                  </div>

                  {isEditing ? (
                    <input
                      type="text"
                      className="input-field"
                      placeholder="Detailed instructions for the astronaut..."
                      value={step.description}
                      onChange={(e) => handleUpdateStep(idx, 'description', e.target.value)}
                    />
                  ) : (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{step.description}</div>
                  )}

                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '11px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Expected Objects:</span>
                    {isEditing ? (
                      <input
                        type="text"
                        className="input-field font-mono"
                        style={{ width: '240px', padding: '4px 8px', fontSize: '11px' }}
                        value={step.expected_objects.join(', ')}
                        onChange={(e) =>
                          handleUpdateStep(
                            idx,
                            'expected_objects',
                            e.target.value.split(',').map((s) => s.trim())
                          )
                        }
                      />
                    ) : (
                      <div style={{ display: 'flex', gap: 4 }}>
                        {step.expected_objects.map((obj) => (
                          <span key={obj} className="badge badge-muted font-mono" style={{ fontSize: '9px' }}>
                            {obj}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
