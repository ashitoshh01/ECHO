import React from 'react';

export default function MetricCard({
  label,
  value,
  subtext,
  icon: Icon,
  accent = 'purple', // 'purple' | 'rose' | 'amber' | 'emerald' | 'blue'
  badge,
}) {
  const accentStyles = {
    purple: {
      iconBg: 'bg-purple-50 text-purple-600 border-purple-100',
      valueColor: 'text-slate-900',
    },
    rose: {
      iconBg: 'bg-rose-50 text-rose-600 border-rose-100',
      valueColor: 'text-rose-600',
    },
    amber: {
      iconBg: 'bg-amber-50 text-amber-600 border-amber-100',
      valueColor: 'text-amber-600',
    },
    emerald: {
      iconBg: 'bg-emerald-50 text-emerald-600 border-emerald-100',
      valueColor: 'text-emerald-600',
    },
    blue: {
      iconBg: 'bg-sky-50 text-sky-600 border-sky-100',
      valueColor: 'text-sky-600',
    },
  };

  const style = accentStyles[accent] || accentStyles.purple;

  return (
    <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-xs transition hover:shadow-sm hover:border-slate-300/80">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</span>
        {Icon && (
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center border ${style.iconBg}`}>
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className={`text-2xl font-bold tracking-tight ${style.valueColor}`}>{value}</span>
        {badge && (
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
            {badge}
          </span>
        )}
      </div>
      {subtext && <p className="text-xs text-slate-400 mt-1">{subtext}</p>}
    </div>
  );
}

