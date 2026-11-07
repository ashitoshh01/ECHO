/**
 * Echo Centralized API Client & Service Layer
 * Fully dynamic: connects to FastAPI backend on port 8000 (direct or via Vite proxy)
 */

const API_BASE = (typeof window !== 'undefined' && window.location.port === '8000')
  ? ''
  : (typeof window !== 'undefined' && (window.location.port === '3000' || window.location.port === '5173'))
    ? '' // Vite proxy forwards /api to http://127.0.0.1:8000
    : `http://${(typeof window !== 'undefined' && window.location.hostname) || 'localhost'}:8000`;

export async function api(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      // fallback to statusText
    }
    throw new Error(errorDetail || `Request failed with status ${response.status}`);
  }

  return response.json();
}

// Service Methods
export const echoApi = {
  // Health & Connectors
  checkHealth: () => api('/api/health'),
  getConnectors: () => api('/api/connectors'),

  // Projects
  getProjects: () => api('/api/projects'),
  selectProject: (projectId) => api('/api/projects/select', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId }),
  }),
  scanGitRepository: (repoPath = null, leaverName = null) => api('/api/projects/scan-git', {
    method: 'POST',
    body: JSON.stringify({ repo_path: repoPath, leaver_name: leaverName }),
  }),
  getRepositories: (projectId) => api(`/api/projects/${projectId}/repositories`),
  getTeamMembers: (projectId = null) => api(`/api/team-members${projectId ? `?project_id=${projectId}` : ''}`),

  // Risk Map & Artifacts
  getRiskMap: (projectId = null) => api(`/api/risk-map${projectId ? `?project_id=${projectId}` : ''}`),
  getArtifacts: (projectId = null) => api(`/api/artifacts${projectId ? `?project_id=${projectId}` : ''}`),
  getArtifactDetails: (artifactId, projectId = null) => api(`/api/artifacts/${artifactId}${projectId ? `?project_id=${projectId}` : ''}`),

  // Interview
  getInterviewQuestions: (limit = 6, projectId = null) =>
    api(`/api/interview/questions?limit=${limit}${projectId ? `&project_id=${projectId}` : ''}`),
  regenerateQuestions: (limit = 6, projectId = null) =>
    api(`/api/interview/questions/generate?limit=${limit}${projectId ? `&project_id=${projectId}` : ''}`, { method: 'POST' }),
  submitInterviewAnswer: (payload) => api('/api/interview/answers', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  getInterviewAnswers: (projectId = null) => api(`/api/interview/answers${projectId ? `?project_id=${projectId}` : ''}`),

  // Handover
  getHandoverPackage: (projectId = null) => api(`/api/handover${projectId ? `?project_id=${projectId}` : ''}`),
  approveHandover: (approvedBy = null, projectId = null) => api('/api/handover/approve', {
    method: 'POST',
    body: JSON.stringify({ approved_by: approvedBy, project_id: projectId }),
  }),
  toggleOnboardingTask: (taskId) => api(`/api/handover/task/${taskId}/toggle`, {
    method: 'POST',
  }),

  // Ask Echo
  getConversations: (projectId = null) => api(`/api/conversations${projectId ? `?project_id=${projectId}` : ''}`),
  askEcho: (question, asker = null, projectId = null) => api('/api/ask', {
    method: 'POST',
    body: JSON.stringify({ question, asker, project_id: projectId }),
  }),

  // Reset Demo
  resetDemoState: () => api('/api/reset', { method: 'POST' }),
};

export function getRiskColor(pct) {
  if (pct >= 50) {
    return {
      bar: 'bg-rose-500',
      text: 'text-rose-600',
      bg: 'bg-rose-50',
      border: 'border-rose-200',
      badge: 'bg-rose-50 text-rose-700 border-rose-200 ring-rose-500/10',
      dot: 'bg-rose-500',
    };
  }
  if (pct >= 30) {
    return {
      bar: 'bg-amber-500',
      text: 'text-amber-600',
      bg: 'bg-amber-50',
      border: 'border-amber-200',
      badge: 'bg-amber-50 text-amber-700 border-amber-200 ring-amber-500/10',
      dot: 'bg-amber-500',
    };
  }
  return {
    bar: 'bg-emerald-500',
    text: 'text-emerald-600',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-200 ring-emerald-500/10',
    dot: 'bg-emerald-500',
  };
}
