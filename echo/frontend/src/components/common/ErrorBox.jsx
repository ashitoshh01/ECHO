import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default function ErrorBox({ msg, hint, onRetry }) {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50/70 p-5 text-rose-900 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="p-1 rounded-lg bg-rose-100 text-rose-600 shrink-0 mt-0.5">
          <AlertCircle className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-rose-950">Backend Connection Error</h4>
          <p className="text-sm text-rose-800 mt-1">{msg || 'Unable to reach backend service.'}</p>
          {hint && (
            <p className="text-xs text-rose-700/80 mt-2 font-mono bg-rose-100/60 p-2 rounded-lg border border-rose-200/60">
              {hint}
            </p>
          )}
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-rose-800 bg-white border border-rose-200 rounded-lg hover:bg-rose-50 transition shadow-xs"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Retry Connection
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

