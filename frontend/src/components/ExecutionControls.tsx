import { useEffect, useState, useCallback } from 'react';
import { Play, Loader2, CheckCircle, XCircle, RefreshCw, Pencil } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import { usePipeline } from '../hooks/usePipeline';
import { useWebSocket } from '../hooks/useWebSocket';
import type { StageUpdate } from '../types/pipeline';

export default function ExecutionControls() {
  const {
    currentPipeline,
    stageStatuses,
    isExecuting,
    startExecution,
    stopExecution,
    updateStageStatus,
    setBulkResults,
    addToHistory,
    setRecoveryPlan,
    startRegenerate,
    startEditing,
  } = usePipelineContext();

  const { loading, error, execute } = usePipeline();
  const [elapsed, setElapsed] = useState(0);
  const [wsActive, setWsActive] = useState(false);
  const [pipelineIdForWs, setPipelineIdForWs] = useState<string | null>(null);

  const onWsUpdate = useCallback((update: StageUpdate) => {
    updateStageStatus(update.stage_id, update.status);
    if (update.recovery_strategy) {
      setRecoveryPlan(update.stage_id, {
        strategy: update.recovery_strategy,
        reason: update.recovery_reason ?? '',
        modified_command: update.modified_command,
      });
    }
  }, [updateStageStatus, setRecoveryPlan]);

  useWebSocket(wsActive ? pipelineIdForWs : null, onWsUpdate);

  // Elapsed timer
  useEffect(() => {
    if (!isExecuting) return;
    const start = Date.now();
    const timer = setInterval(() => setElapsed((Date.now() - start) / 1000), 100);
    return () => clearInterval(timer);
  }, [isExecuting]);

  const handleExecute = async () => {
    if (!currentPipeline) return;

    // Reset all statuses to pending
    for (const stage of currentPipeline.stages) {
      updateStageStatus(stage.id, 'pending');
    }

    startExecution();
    setElapsed(0);
    setPipelineIdForWs(currentPipeline.pipeline_id);
    setWsActive(true);

    const results = await execute(currentPipeline.pipeline_id);

    setWsActive(false);
    stopExecution();

    if (results) {
      setBulkResults(results);
      const hasFailed = Object.values(results).some((r) => r.status === 'failed');
      addToHistory({
        pipeline: currentPipeline,
        results,
        completedAt: new Date().toISOString(),
        overallStatus: hasFailed ? 'failed' : 'success',
      });
    }
  };

  if (!currentPipeline) return null;

  const total = currentPipeline.stages.length;
  const completed = Array.from(stageStatuses.values()).filter(
    (s) => s === 'success' || s === 'skipped',
  ).length;
  const failed = Array.from(stageStatuses.values()).filter((s) => s === 'failed').length;
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  const allDone = !isExecuting && (completed + failed === total) && total > 0 && (completed > 0 || failed > 0);
  const pipelineSuccess = allDone && failed === 0;

  return (
    <div className="bg-white border-b border-gray-200 px-5 py-3 flex items-center gap-3 flex-shrink-0">
      {/* Execute button */}
      <button
        onClick={handleExecute}
        disabled={isExecuting || loading}
        className="flex items-center gap-2 px-5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
      >
        {isExecuting || loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Executing...
          </>
        ) : (
          <>
            <Play className="w-4 h-4" />
            Execute Pipeline
          </>
        )}
      </button>

      {/* Regenerate button */}
      <button
        onClick={startRegenerate}
        disabled={isExecuting || loading}
        className="flex items-center gap-1.5 px-3 py-2 bg-blue-50 hover:bg-blue-100 disabled:bg-gray-100 disabled:text-gray-400 text-blue-700 text-sm font-medium rounded-lg transition-colors"
        title="Re-analyze repo and generate a new pipeline"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        Regenerate
      </button>

      {/* Edit button */}
      <button
        onClick={startEditing}
        disabled={isExecuting || loading}
        className="flex items-center gap-1.5 px-3 py-2 bg-amber-50 hover:bg-amber-100 disabled:bg-gray-100 disabled:text-gray-400 text-amber-700 text-sm font-medium rounded-lg transition-colors"
        title="Edit stage commands and settings"
      >
        <Pencil className="w-3.5 h-3.5" />
        Edit
      </button>

      {/* Progress */}
      <div className="flex-1 flex items-center gap-3">
        <div className="flex-1 max-w-xs">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>{completed}/{total} stages complete</span>
            {isExecuting && <span className="font-mono">{elapsed.toFixed(1)}s</span>}
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Status banner */}
        {allDone && (
          <div
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium ${
              pipelineSuccess
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-red-50 text-red-700'
            }`}
          >
            {pipelineSuccess ? (
              <>
                <CheckCircle className="w-4 h-4" />
                Pipeline Succeeded
              </>
            ) : (
              <>
                <XCircle className="w-4 h-4" />
                Pipeline Failed
              </>
            )}
          </div>
        )}
      </div>

      {error && (
        <span className="text-sm text-red-600">{error}</span>
      )}
    </div>
  );
}
