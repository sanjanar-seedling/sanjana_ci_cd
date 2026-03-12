import { CheckCircle, XCircle, Clock, Trash2 } from 'lucide-react';
import { deletePipeline } from '../api/client';
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
  const { executionHistory, loadFromHistory, removeFromHistory } = usePipelineContext();

  const handleDelete = async (e: React.MouseEvent, entry: HistoryEntry) => {
    e.stopPropagation();
    try {
      await deletePipeline(entry.pipeline.pipeline_id);
      removeFromHistory(entry.pipeline.pipeline_id);
    } catch {
      // silently ignore
    }
  };

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
            <div
              key={i}
              className="flex items-center rounded-lg hover:bg-white/10 transition-colors group"
            >
              <button
                onClick={() => loadFromHistory(entry)}
                className="flex-1 text-left px-3 py-2.5 min-w-0"
              >
                <div className="flex items-center gap-2">
                  {entry.overallStatus === 'success' ? (
                    <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  )}
                  <span className="text-sm text-white truncate font-medium">
                    {entry.pipeline.name || extractRepoName(entry.pipeline.repo_url)}
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
              <button
                onClick={(e) => handleDelete(e, entry)}
                className="p-2 mr-1 opacity-0 group-hover:opacity-100 hover:bg-red-500/20 rounded-md transition-all"
                title="Delete pipeline"
              >
                <Trash2 className="w-3.5 h-3.5 text-red-400" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
