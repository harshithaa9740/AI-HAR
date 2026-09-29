import React, { useState, useEffect } from 'react';
import './App.css';
import { Header } from './components/Header';
import { Sidebar, type NavPageId } from './components/Sidebar';
import { ConnectModal } from './components/ConnectModal';
import { LiveMission } from './pages/LiveMission';
import { Overview } from './pages/Overview';
import { Experiments } from './pages/Experiments';
import { SessionsAudit } from './pages/SessionsAudit';
import { AIModels } from './pages/AIModels';
import { DemoMode } from './pages/DemoMode';
import { SystemSettings } from './pages/SystemSettings';
import { BackendConfigManager } from './config/backendConfig';
import { wsService } from './services/websocketService';

export const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<NavPageId>('live-mission');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(() => !BackendConfigManager.getConfig().isConfigured);

  useEffect(() => {
    // Connect WebSocket
    wsService.connect();

    return () => {
      wsService.disconnect();
    };
  }, []);

  return (
    <div className="app-container">
      {/* Top Header */}
      <Header
        onOpenConnectModal={() => setIsConnectModalOpen(true)}
        onNavigateToSettings={() => setCurrentPage('settings')}
      />

      {/* App Body (Sidebar + Content View) */}
      <div className="app-body">
        {/* Navigation Sidebar */}
        <Sidebar
          currentPage={currentPage}
          onSelectPage={(page) => setCurrentPage(page)}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          activeViolationsCount={0}
        />

        {/* Main Scrollable Content Area */}
        <main className="app-content">
          {currentPage === 'live-mission' && <LiveMission />}
          {currentPage === 'overview' && <Overview onNavigate={setCurrentPage} />}
          {currentPage === 'experiments' && <Experiments />}
          {currentPage === 'sessions-audit' && <SessionsAudit />}
          {currentPage === 'ai-models' && <AIModels />}
          {currentPage === 'demo-mode' && <DemoMode />}
          {currentPage === 'settings' && <SystemSettings />}
        </main>
      </div>

      {/* Connect to AURAVISION Backend Modal */}
      <ConnectModal
        isOpen={isConnectModalOpen}
        onClose={() => setIsConnectModalOpen(false)}
        onConnected={() => {
          wsService.reconnect();
        }}
      />
    </div>
  );
};

export default App;
