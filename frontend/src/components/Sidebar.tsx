import React from 'react';
import {
  LayoutDashboard,
  Radio,
  FlaskConical,
  ClipboardList,
  Cpu,
  PlaySquare,
  Settings2,
  ChevronLeft,
  ChevronRight,
  ShieldAlert
} from 'lucide-react';

export type NavPageId = 
  | 'overview' 
  | 'live-mission' 
  | 'experiments' 
  | 'sessions-audit' 
  | 'ai-models' 
  | 'demo-mode' 
  | 'settings';

interface SidebarProps {
  currentPage: NavPageId;
  onSelectPage: (page: NavPageId) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  activeViolationsCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPage,
  onSelectPage,
  collapsed,
  onToggleCollapse,
  activeViolationsCount = 0
}) => {
  const navItems = [
    { id: 'overview' as NavPageId, label: 'Overview', icon: LayoutDashboard },
    { id: 'live-mission' as NavPageId, label: 'Live Mission', icon: Radio, primary: true },
    { id: 'experiments' as NavPageId, label: 'Experiments', icon: FlaskConical },
    { id: 'sessions-audit' as NavPageId, label: 'Sessions & Audit', icon: ClipboardList },
    { id: 'ai-models' as NavPageId, label: 'AI Models', icon: Cpu },
    { id: 'demo-mode' as NavPageId, label: 'Demo Mode', icon: PlaySquare },
    { id: 'settings' as NavPageId, label: 'System Settings', icon: Settings2 },
  ];

  return (
    <aside className={`app-sidebar ${collapsed ? 'collapsed' : ''}`}>
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentPage === item.id;
          return (
            <div
              key={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectPage(item.id)}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="nav-icon" />
              {!collapsed && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                  <span className="nav-label">{item.label}</span>
                  {item.id === 'live-mission' && activeViolationsCount > 0 && (
                    <span
                      className="badge badge-critical"
                      style={{ padding: '1px 5px', fontSize: '10px' }}
                      title={`${activeViolationsCount} active protocol deviations`}
                    >
                      {activeViolationsCount}
                    </span>
                  )}
                  {item.id === 'live-mission' && activeViolationsCount === 0 && (
                    <span
                      className="badge badge-cyan"
                      style={{ padding: '1px 5px', fontSize: '9px' }}
                    >
                      LIVE
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        {!collapsed && (
          <div
            style={{
              padding: '8px 10px',
              background: 'rgba(0, 229, 255, 0.05)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid rgba(0, 229, 255, 0.15)',
              marginBottom: 4,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--cyan)', fontSize: 11, fontWeight: 600 }}>
              <ShieldAlert size={12} />
              <span>ISRO BAS PROTOCOL</span>
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>
              AURA-VALIDATOR v2.4.0
            </div>
          </div>
        )}

        <button
          className="sidebar-collapse-btn"
          onClick={onToggleCollapse}
          title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          {!collapsed && <span>Collapse Sidebar</span>}
        </button>
      </div>
    </aside>
  );
};
