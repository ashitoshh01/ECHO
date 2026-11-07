import React, { useState, useEffect, useCallback } from 'react';
import AppShell from './components/layout/AppShell';
import RiskMap from './components/risk/RiskMap';
import ExitInterview from './components/interview/ExitInterview';
import Handover from './components/handover/Handover';
import AskEcho from './components/ask/AskEcho';
import { echoApi } from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState('risk');
  const [focusArtifactId, setFocusArtifactId] = useState(null);
  const [handoverKey, setHandoverKey] = useState(0);
  const [resetting, setResetting] = useState(false);
  const [backendStatus, setBackendStatus] = useState('checking'); // 'checking' | 'online' | 'offline'

  // Dynamic Project & Team Member State
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [teamMembers, setTeamMembers] = useState([]);

  // Fetch projects and active project state
  const loadProjectsAndTeam = useCallback(async () => {
    try {
      const healthRes = await echoApi.checkHealth();
      setBackendStatus('online');
      if (healthRes.active_project) {
        setActiveProject(healthRes.active_project);
      }

      const pRes = await echoApi.getProjects();
      if (pRes && pRes.projects) {
        setProjects(pRes.projects);
        const active = pRes.projects.find((p) => p.is_active) || pRes.projects[0];
        if (active) setActiveProject(active);
      }

      const mRes = await echoApi.getTeamMembers();
      if (mRes && mRes.team_members) {
        setTeamMembers(mRes.team_members);
      }
    } catch (e) {
      setBackendStatus('offline');
    }
  }, []);

  useEffect(() => {
    loadProjectsAndTeam();
    const interval = setInterval(loadProjectsAndTeam, 12000);
    return () => clearInterval(interval);
  }, [loadProjectsAndTeam]);

  // Project selection handler
  const handleSelectProject = async (projectId) => {
    try {
      const res = await echoApi.selectProject(projectId);
      if (res.active_project) {
        setActiveProject(res.active_project);
      }
      const mRes = await echoApi.getTeamMembers(projectId);
      if (mRes && mRes.team_members) {
        setTeamMembers(mRes.team_members);
      }
      setHandoverKey((k) => k + 1);
    } catch (e) {
      alert(`Failed to switch project: ${e.message}`);
    }
  };

  const handleScanLiveGit = async () => {
    await loadProjectsAndTeam();
    setHandoverKey((k) => k + 1);
  };

  const handleNavigateToInterview = (artifactId) => {
    setFocusArtifactId(artifactId);
    setActiveTab('interview');
  };

  const handleResetDemo = async () => {
    if (!window.confirm('Reset benchmark demo state? This resets submitted answers and decisions for a clean presentation run.')) {
      return;
    }
    setResetting(true);
    try {
      await echoApi.resetDemoState();
      setHandoverKey((k) => k + 1);
      await loadProjectsAndTeam();
    } catch (e) {
      alert(`Reset failed: ${e.message}`);
    } finally {
      setTimeout(() => setResetting(false), 300);
    }
  };

  // Derive leaver, successor, manager dynamically
  const leaver = teamMembers.find((m) => m.is_leaver) || null;
  const successor = teamMembers.find((m) => m.is_successor) || null;
  const manager = teamMembers.find((m) => m.is_manager) || null;

  return (
    <AppShell
      activeTab={activeTab}
      onSelectTab={(tab) => {
        setActiveTab(tab);
        if (tab !== 'interview') setFocusArtifactId(null);
      }}
      onResetDemo={handleResetDemo}
      resetting={resetting}
      backendStatus={backendStatus}
      onRetryConnection={loadProjectsAndTeam}
      projects={projects}
      activeProject={activeProject}
      onSelectProject={handleSelectProject}
      onScanLiveGit={handleScanLiveGit}
      leaver={leaver}
      successor={successor}
      manager={manager}
    >
      <div style={{ display: activeTab === 'risk' ? 'block' : 'none' }}>
        <RiskMap
          onNavigateToInterview={handleNavigateToInterview}
          activeProject={activeProject}
          refreshKey={handoverKey}
        />
      </div>

      <div style={{ display: activeTab === 'interview' ? 'block' : 'none' }}>
        <ExitInterview
          key={handoverKey}
          focusArtifactId={focusArtifactId}
          onAnswerSubmitted={() => setHandoverKey((k) => k + 1)}
          activeProject={activeProject}
          refreshKey={handoverKey}
        />
      </div>

      <div style={{ display: activeTab === 'handover' ? 'block' : 'none' }}>
        <Handover
          key={handoverKey}
          active={activeTab === 'handover'}
          onNavigateToInterview={handleNavigateToInterview}
          activeProject={activeProject}
          refreshKey={handoverKey}
        />
      </div>

      <div style={{ display: activeTab === 'ask' ? 'block' : 'none' }}>
        <AskEcho
          key={handoverKey}
          activeProject={activeProject}
          successor={successor}
          refreshKey={handoverKey}
        />
      </div>
    </AppShell>
  );
}
