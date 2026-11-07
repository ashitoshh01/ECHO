import React from 'react';
import { AlertTriangle, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { getRiskColor } from '../../api';

export function RiskBadge({ score, pct, showLabel = true, size = 'md' }) {
  const percentage = pct ?? (score != null ? Math.round(score * 100) : 0);
  const color = getRiskColor(percentage);

  const sizeClasses = {
    sm: 'text-[11px] px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
    lg: 'text-sm px-3 py-1.5',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${color.badge} ${sizeClasses[size] || sizeClasses.md}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${color.dot}`} />
      <span>{percentage}%</span>
      {showLabel && (
        <span className="text-[10px] opacity-75 font-normal uppercase tracking-wider">
          {percentage >= 50 ? 'High' : percentage >= 30 ? 'Medium' : 'Low'}
        </span>
      )}
    </span>
  );
}

export function BusFactorBadge() {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
      <AlertTriangle className="w-3 h-3 text-rose-500" />
      <span>Bus factor 1</span>
    </span>
  );
}

export function PlantedGapBadge() {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
      <ShieldAlert className="w-3 h-3 text-purple-500" />
      <span>Planted Gap</span>
    </span>
  );
}

