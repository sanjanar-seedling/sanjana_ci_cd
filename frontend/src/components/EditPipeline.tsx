import { useState } from 'react';
import { Save, X, Pencil, Tag, Target } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import { usePipeline } from '../hooks/usePipeline';
import { agentColors } from '../utils/statusColors';
import type { Stage } from '../types/pipeline';

export default function EditPipeline() {
  const { currentPipeline, setPipeline, stopEditing } = usePipelineContext();
  const { loading, error, update, setError } = usePipeline();

  const [name, setName] = useState(currentPipeline?.name ?? '');
  const [goal, setGoal] = useState(currentPipeline?.goal ?? '');
  const [stages, setStages] = useState<Stage[]>(
    currentPipeline?.stages.map((s) => ({ ...s })) ?? [],
  );

  if (!currentPipeline) return null;

  const updateStageCommand = (index: number, command: string) => {
    setStages((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], command };
      return next;
    });
  };

  const updateStageTimeout = (index: number, timeout: number) => {
    setStages((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], timeout_seconds: timeout };
      return next;
    });
  };

  const toggleCritical = (index: number) => {
    setStages((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], critical: !next[index].critical };
      return next;
    });
  };

  const handleSave = async () => {
    setError(null);
    const updated = await update(currentPipeline.pipeline_id, {
      name: name.trim(),
      goal: goal.trim(),
      stages,
    });
    if (updated) {
      setPipeline(updated);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-5 py-3 flex items-center gap-3 flex-shrink-0">
        <Pencil className="w-4 h-4 text-accent" />
        <h2 className="text-sm font-semibold text-gray-800 flex-1">Edit Pipeline</h2>
        <button
          onClick={stopEditing}
          className="p-1.5 hover:bg-gray-100 rounded-md transition-colors"
          title="Cancel editing"
        >
          <X className="w-4 h-4 text-gray-500" />
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {/* Pipeline Name */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
            <Tag className="w-4 h-4 text-gray-400" />
            Pipeline Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Flask CI, Express Deploy"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none"
          />
        </div>

        {/* Pipeline Goal */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
            <Target className="w-4 h-4 text-gray-400" />
            Pipeline Goal
          </label>
          <input
            type="text"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="e.g. Run tests and deploy, Lint and build"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none"
          />
        </div>

        {/* Stage Editors */}
        {stages.map((stage, i) => {
          const agentStyle = agentColors[stage.agent];
          return (
            <div key={stage.id} className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-sm font-semibold text-gray-800">{stage.id}</span>
                <span
                  className="px-2 py-0.5 rounded text-xs font-medium text-white"
                  style={{ backgroundColor: agentStyle.color }}
                >
                  {agentStyle.label}
                </span>
                <button
                  onClick={() => toggleCritical(i)}
                  className={`ml-auto px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                    stage.critical
                      ? 'bg-red-50 text-red-600 hover:bg-red-100'
                      : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
                  }`}
                >
                  {stage.critical ? 'critical' : 'optional'}
                </button>
              </div>

              <label className="block text-xs text-gray-500 mb-1">Command</label>
              <textarea
                value={stage.command}
                onChange={(e) => updateStageCommand(i, e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none resize-none"
              />

              <div className="flex items-center gap-4 mt-2">
                <div className="flex items-center gap-2">
                  <label className="text-xs text-gray-500">Timeout (s)</label>
                  <input
                    type="number"
                    value={stage.timeout_seconds}
                    onChange={(e) => updateStageTimeout(i, parseInt(e.target.value) || 60)}
                    className="w-20 px-2 py-1 border border-gray-300 rounded text-xs text-center focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none"
                  />
                </div>
                {stage.depends_on.length > 0 && (
                  <div className="text-xs text-gray-400">
                    depends on: {stage.depends_on.join(', ')}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="bg-white border-t border-gray-200 px-5 py-3 flex items-center gap-3 flex-shrink-0">
        <button
          onClick={handleSave}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent/90 disabled:bg-gray-300 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Save className="w-4 h-4" />
          {loading ? 'Saving...' : 'Save Changes'}
        </button>
        <button
          onClick={stopEditing}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
