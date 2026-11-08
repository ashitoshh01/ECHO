import React, { useState, useEffect } from 'react';
import {
  X,
  Sliders,
  Shield,
  BookOpen,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Network,
  RefreshCw,
  GitBranch,
  FolderGit2
} from 'lucide-react';
import { echoApi } from '../../api';

export function SettingsModal({ isOpen, onClose, onScanLiveGit }) {
  const [connectors, setConnectors] = useState([]);
  const [loadingConn, setLoadingConn] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setLoadingConn(true);
      echoApi.getConnectors()
        .then((res) => setConnectors(res.connectors || []))
        .catch(() => setConnectors([]))
        .finally(() => setLoadingConn(false));
    }
  }, [isOpen]);

  const handleTriggerScan = async () => {
    setScanning(true);
    setScanMsg(null);
    try {
      const res = await echoApi.scanGitRepository('.');
      setScanMsg(`Successfully scanned ${res.artifacts_count} artifacts from current Git workspace!`);
      if (onScanLiveGit) onScanLiveGit();
    } catch (e) {
      setScanMsg(`Scan failed: ${e.message}`);
    } finally {
      setScanning(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xl w-full max-w-xl overflow-hidden fade-in">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="w-5 h-5 text-purple-600" />
            <h3 className="text-base font-semibold text-slate-900">Engine &amp; Connector Settings</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto text-sm text-slate-600">
          {/* Real Connectors Telemetry */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Network className="w-3.5 h-3.5 text-purple-600" />
                <span>External Activity Connectors (Actual Status)</span>
              </h4>
              {loadingConn && <span className="text-[11px] text-slate-400">Inspecting...</span>}
            </div>

            <div className="space-y-2">
              {connectors.map((c) => {
                const isConn = c.status === 'connected';
                return (
                  <div
                    key={c.id}
                    className="p-3 rounded-xl border border-slate-200 bg-white flex items-start justify-between gap-3 text-xs"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">{c.name}</span>
                        <span
                          className={`text-[10px] font-medium px-2 py-0.2 rounded-full border ${
                            isConn
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : 'bg-slate-100 text-slate-500 border-slate-200'
                          }`}
                        >
                          {isConn ? 'Connected' : 'Not Configured'}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-1">{c.details}</p>
                    </div>

                    {c.type === 'git' && (
                      <button
                        onClick={handleTriggerScan}
                        disabled={scanning}
                        className="px-2.5 py-1 rounded-lg bg-purple-50 text-purple-700 border border-purple-200 text-[11px] font-medium hover:bg-purple-100 transition shrink-0"
                      >
                        {scanning ? 'Scanning...' : 'Scan Now'}
                      </button>
                    )}

                    {c.type === 'github' && isConn && (
                      <button
                        onClick={async () => {
                          try {
                            await echoApi.disconnectGitHub();
                            const res = await echoApi.getConnectors();
                            setConnectors(res.connectors || []);
                          } catch (e) {
                            setScanMsg(`Disconnect failed: ${e.message}`);
                          }
                        }}
                        className="px-2.5 py-1 rounded-lg bg-rose-50 text-rose-700 border border-rose-200 text-[11px] font-medium hover:bg-rose-100 transition shrink-0"
                      >
                        Disconnect
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            {scanMsg && (
              <p className="text-xs mt-2 text-purple-700 bg-purple-50 p-2 rounded-lg border border-purple-200">
                {scanMsg}
              </p>
            )}
          </div>

          {/* Formula */}
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Deterministic Risk Formula
            </h4>
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl font-mono text-xs text-slate-800 leading-relaxed">
              Risk = OwnershipConcentration × Criticality × (1 − DocCoverage) × RecencyWeight
            </div>
          </div>

          {/* Recency Weights */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Recency Decay Weights
            </h4>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2.5 rounded-lg border border-slate-200 bg-white">
                <span className="font-semibold text-slate-900">≤ 7 days</span>
                <span className="text-slate-500 block">Weight: 1.0 (Critical)</span>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-200 bg-white">
                <span className="font-semibold text-slate-900">≤ 30 days</span>
                <span className="text-slate-500 block">Weight: 0.7 (Active)</span>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-200 bg-white">
                <span className="font-semibold text-slate-900">≤ 90 days</span>
                <span className="text-slate-500 block">Weight: 0.4 (Moderate)</span>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-200 bg-white">
                <span className="font-semibold text-slate-900">&gt; 90 days</span>
                <span className="text-slate-500 block">Weight: 0.15 (Archival)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export function HelpModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xl w-full max-w-lg overflow-hidden fade-in">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-purple-600" />
            <h3 className="text-base font-semibold text-slate-900">Echo Demo &amp; Pitch Guide</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4 max-h-[75vh] overflow-y-auto text-sm text-slate-600">
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
            <div className="font-semibold text-slate-900 text-xs uppercase tracking-wide">
              The 2-Minute Rubric Flow
            </div>
            <p className="text-xs text-slate-500">
              Follow this exact workflow for an unbeatable presentation:
            </p>
          </div>

          <div className="space-y-3">
            <div className="p-3 rounded-lg border border-slate-200 bg-white">
              <span className="text-xs font-semibold text-purple-600">Step 1 (0:00 - 0:50): Risk Map</span>
              <p className="text-xs text-slate-600 mt-1">
                Show <code className="text-slate-800 font-mono">nightly_sync.py</code>: single ownership, 0% doc coverage, touched 3 days ago. Detected 4/4 planted gaps.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 bg-white">
              <span className="text-xs font-semibold text-purple-600">Step 2 (0:50 - 1:20): Exit Interview</span>
              <p className="text-xs text-slate-600 mt-1">
                Type answer: <em className="text-slate-800">"we chose 7 because the vendor API rate-limited us"</em>. Notice the real-time decision signal!
              </p>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 bg-white">
              <span className="text-xs font-semibold text-purple-600">Step 3 (1:20 - 1:40): Handover Package</span>
              <p className="text-xs text-slate-600 mt-1">
                Show dynamic 2-week plan with interactive checkmarks, defused landmines, and manager approval sign-off.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 bg-white">
              <span className="text-xs font-semibold text-purple-600">Step 4 (1:40 - 2:00): Ask Echo Trust Layer</span>
              <p className="text-xs text-slate-600 mt-1">
                Ask: <strong className="text-slate-800">"Why is the retry limit 7?"</strong> → Cited answer from interview.<br />
                Ask: <strong className="text-slate-800">"What is the wifi password?"</strong> → <em>Honesty fallback with suggested contact: Priya</em>.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 transition"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
