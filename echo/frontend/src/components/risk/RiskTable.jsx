import React, { useState, useMemo } from 'react';
import {
  Search,
  Filter,
  ArrowUpDown,
  FileCode,
  GitPullRequest,
  Ticket,
  MessageSquare,
  FileText,
  ChevronRight,
  ExternalLink,
  Info
} from 'lucide-react';
import { RiskBadge, BusFactorBadge, PlantedGapBadge } from '../common/RiskBadge';
import { getRiskColor } from '../../api';

export default function RiskTable({
  artifacts = [],
  plantedGaps = [],
  leaverName = 'Departing Lead',
  repoName = 'core-platform',
  branch = 'main',
  onSelectArtifact,
}) {
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('all'); // 'all' | 'high' | 'bus1' | 'planted' | 'module' | 'pull_request' | 'ticket'
  const [sortKey, setSortKey] = useState('risk_desc'); // 'risk_desc' | 'risk_asc' | 'criticality' | 'recency' | 'title'

  const typeIcons = {
    module: FileCode,
    script: FileCode,
    config: FileCode,
    pull_request: GitPullRequest,
    ticket: Ticket,
    chat_thread: MessageSquare,
    document: FileText,
  };

  const filteredArtifacts = useMemo(() => {
    if (!artifacts) return [];
    return artifacts.filter((a) => {
      // Search filter
      const matchesSearch =
        a.title.toLowerCase().includes(search.toLowerCase()) ||
        a.artifact_id.toLowerCase().includes(search.toLowerCase()) ||
        a.type.toLowerCase().includes(search.toLowerCase());

      if (!matchesSearch) return false;

      // Type / Status filter
      if (filterType === 'high') return a.risk_pct >= 50;
      if (filterType === 'bus1') return a.bus_factor_one;
      if (filterType === 'planted') return plantedGaps.includes(a.artifact_id);
      if (filterType === 'module') return a.type === 'module' || a.type === 'script';
      if (filterType === 'pull_request') return a.type === 'pull_request';
      if (filterType === 'ticket') return a.type === 'ticket';

      return true;
    });
  }, [artifacts, search, filterType, plantedGaps]);

  const sortedArtifacts = useMemo(() => {
    return [...filteredArtifacts].sort((a, b) => {
      if (sortKey === 'risk_desc') return b.risk_score - a.risk_score;
      if (sortKey === 'risk_asc') return a.risk_score - b.risk_score;
      if (sortKey === 'criticality') {
        const critA = a.components?.criticality ?? 0;
        const critB = b.components?.criticality ?? 0;
        return critB - critA;
      }
      if (sortKey === 'recency') {
        const recA = a.components?.recency_weight ?? 0;
        const recB = b.components?.recency_weight ?? 0;
        return recB - recA;
      }
      if (sortKey === 'title') return a.title.localeCompare(b.title);
      return 0;
    });
  }, [filteredArtifacts, sortKey]);

  return (
    <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs overflow-hidden">
      {/* Table Toolbar */}
      <div className="p-4 border-b border-slate-200/80 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white">
        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search artifacts, IDs, or file paths..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 text-xs rounded-lg border border-slate-200 bg-slate-50/50 text-slate-800 placeholder-slate-400 focus:outline-none focus:border-purple-500 focus:bg-white transition"
          />
        </div>

        {/* Filter Pills and Sort */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Quick Filters */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0">
            {[
              { id: 'all', label: 'All' },
              { id: 'high', label: 'High Risk (≥50%)' },
              { id: 'bus1', label: 'Bus Factor 1' },
              { id: 'planted', label: 'Planted Gaps' },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setFilterType(f.id)}
                className={`text-xs px-2.5 py-1 rounded-md font-medium transition shrink-0 ${
                  filterType === f.id
                    ? 'bg-purple-50 text-purple-700 border border-purple-200'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Sort Dropdown */}
          <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200 shrink-0">
            <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value)}
              className="text-xs bg-transparent border-0 text-slate-700 font-medium focus:ring-0 cursor-pointer pr-4 py-1"
            >
              <option value="risk_desc">Risk: Highest First</option>
              <option value="risk_asc">Risk: Lowest First</option>
              <option value="criticality">Criticality</option>
              <option value="recency">Recency</option>
              <option value="title">Alphabetical</option>
            </select>
          </div>
        </div>
      </div>

      {/* Table Element */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-600">
          <thead className="bg-slate-50/80 border-b border-slate-200/80 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
            <tr>
              <th className="py-3 px-4">Artifact &amp; Identifier</th>
              <th className="py-3 px-3">Type</th>
              <th className="py-3 px-3">Ownership ({leaverName})</th>
              <th className="py-3 px-3">Crit / Doc Gap</th>
              <th className="py-3 px-3">Recency</th>
              <th className="py-3 px-4 text-right">Risk Score</th>
              <th className="py-3 px-4 text-center">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sortedArtifacts.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-slate-400">
                  No artifacts match your search and filter criteria.
                </td>
              </tr>
            ) : (
              sortedArtifacts.map((a) => {
                const Icon = typeIcons[a.type] || FileCode;
                const isPlanted = plantedGaps.includes(a.artifact_id);
                const color = getRiskColor(a.risk_pct);

                return (
                  <tr
                    key={a.artifact_id}
                    onClick={() => onSelectArtifact(a)}
                    className="hover:bg-slate-50/80 transition cursor-pointer group"
                  >
                    {/* Artifact Title and ID */}
                    <td className="py-3 px-4 max-w-xs sm:max-w-md">
                      <div className="flex items-start gap-2.5">
                        <div className="p-1.5 rounded-lg bg-slate-100 text-slate-600 group-hover:bg-purple-50 group-hover:text-purple-600 transition mt-0.5 shrink-0">
                          <Icon className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="font-medium text-slate-900 group-hover:text-purple-700 transition">
                            {a.title}
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="font-mono text-[11px] text-slate-400">
                              {a.artifact_id}
                            </span>
                            {a.bus_factor_one && (
                              <span className="text-[10px] font-medium px-1.5 py-0.2 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
                                Bus factor 1
                              </span>
                            )}
                            {isPlanted && (
                              <span className="text-[10px] font-medium px-1.5 py-0.2 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
                                Planted gap
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Type */}
                    <td className="py-3 px-3">
                      <span className="text-[11px] font-medium text-slate-600 px-2 py-0.5 rounded bg-slate-100 capitalize">
                        {a.type}
                      </span>
                    </td>

                    {/* Ownership Concentration */}
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-800">
                          {Math.round((a.components?.ownership_concentration ?? 0) * 100)}%
                        </span>
                        <div className="w-12 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-purple-600 rounded-full"
                            style={{
                              width: `${Math.round((a.components?.ownership_concentration ?? 0) * 100)}%`,
                            }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Criticality & Doc Gap */}
                    <td className="py-3 px-3 font-mono text-[11px] text-slate-500">
                      <div>Crit: {a.components?.criticality != null ? Math.round(a.components.criticality * 5) : '—'}/5</div>
                      <div className="text-slate-400">
                        Doc gap: {Math.round((a.components?.doc_gap ?? 0) * 100)}%
                      </div>
                    </td>

                    {/* Recency */}
                    <td className="py-3 px-3 font-mono text-[11px] text-slate-600">
                      ×{a.components?.recency_weight}
                    </td>

                    {/* Risk Score */}
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <RiskBadge pct={a.risk_pct} size="sm" showLabel={false} />
                      </div>
                      <div className="w-20 ml-auto mt-1.5 h-1 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${color.bar}`}
                          style={{ width: `${Math.min(100, a.risk_pct)}%` }}
                        />
                      </div>
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-4 text-center">
                      <span className="inline-flex items-center gap-1 text-slate-400 group-hover:text-purple-600 text-xs font-medium transition">
                        <span>Details</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Footer Info */}
      <div className="p-3 bg-slate-50/60 border-t border-slate-200/80 flex items-center justify-between text-xs text-slate-500">
        <span>Showing {sortedArtifacts.length} of {artifacts?.length || 0} tracked artifacts</span>
        <span className="font-mono text-[11px]">{repoName} branch @ {branch}</span>
      </div>
    </div>
  );
}
