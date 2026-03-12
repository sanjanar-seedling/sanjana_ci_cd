import { CheckCircle, XCircle, Clock } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import type { HistoryEntry } from '../types/pipeline';

function extractRepoName(url: string): string {
  try {
    const parts = url.replace(/\.git$/, '').split('/');
    return parts[parts.length - 1] || url;
  } catch {
    return url;
  }
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

export default function ExecutionHistory() {
  const { executionHistory, loadFromHistory } = usePipelineContext();

  return (
    <div className="px-4">
      <h3 className="text-xs font-semibold text-blue-200/50 uppercase tracking-wider px-1 mb-2">
        History
      </h3>

      {executionHistory.length === 0 ? (
        <div className="flex flex-col items-center py-8 text-blue-200/30">
          <Clock className="w-8 h-8 mb-2" />
          <p className="text-xs">No runs yet</p>
        </div>
      ) : (
        <div className="space-y-1">
          {executionHistory.map((entry: HistoryEntry, i: number) => (
            <button
              key={i}
              onClick={() => loadFromHistory(entry)}
              className="w-full text-left px-3 py-2.5 rounded-lg hover:bg-white/10 transition-colors group"
            >
              <div className="flex items-center gap-2">
                {entry.overallStatus === 'success' ? (
                  <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                )}
                <span className="text-sm text-white truncate font-medium">
                  {extractRepoName(entry.pipeline.repo_url)}
                </span>
              </div>
              <div className="ml-6 mt-0.5 flex items-center gap-2">
                <span className="text-xs text-blue-200/50 truncate flex-1">
                  {entry.pipeline.goal}
                </span>
                <span className="text-[10px] text-blue-200/40 flex-shrink-0">
                  {formatTime(entry.completedAt)}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
