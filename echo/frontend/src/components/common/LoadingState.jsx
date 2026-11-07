import React from 'react';
import { Loader2 } from 'lucide-react';

export default function LoadingState({ label = 'Loading data...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-10 h-10 rounded-full bg-purple-50 border border-purple-100 flex items-center justify-center mb-3">
        <Loader2 className="w-5 h-5 text-purple-600 animate-spin" />
      </div>
      <p className="text-sm font-medium text-slate-700">{label}</p>
      <p className="text-xs text-slate-400 mt-1">Connecting to knowledge graph engine</p>
    </div>
  );
}

