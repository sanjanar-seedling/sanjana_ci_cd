import { usePipelineContext } from './context/PipelineContext';
import Layout from './components/Layout';
import CreatePipeline from './components/CreatePipeline';
import EditPipeline from './components/EditPipeline';
import PipelineDAG from './components/PipelineDAG';
import ExecutionControls from './components/ExecutionControls';
import StageDetailPanel from './components/StageDetailPanel';
import StatusBanner from './components/StatusBanner';
import { agentColors } from './utils/statusColors';

function PipelineInfo() {
  const { currentPipeline } = usePipelineContext();
  if (!currentPipeline) return null;

  const { analysis } = currentPipeline;

  return (
    <div className="bg-white border-b border-gray-200 px-5 py-3 flex items-center gap-6 flex-shrink-0">
      <div className="flex items-center gap-4 flex-1 min-w-0">
        {currentPipeline.name && (
          <>
            <div className="min-w-0">
              <div className="text-xs text-gray-400 mb-0.5">Name</div>
              <div className="text-sm font-semibold text-gray-900 truncate">{currentPipeline.name}</div>
            </div>
            <div className="h-8 w-px bg-gray-200" />
          </>
        )}
        <div className="min-w-0">
          <div className="text-xs text-gray-400 mb-0.5">Goal</div>
          <div className="text-sm font-medium text-gray-800 truncate">{currentPipeline.goal}</div>
        </div>
        <div className="h-8 w-px bg-gray-200" />
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center px-2 py-1 rounded-md bg-gray-100 text-xs font-medium text-gray-700">
            {analysis.language}
          </span>
          {analysis.framework && (
            <span className="inline-flex items-center px-2 py-1 rounded-md bg-blue-50 text-xs font-medium text-blue-700">
              {analysis.framework}
            </span>
          )}
          <span className="inline-flex items-center px-2 py-1 rounded-md bg-gray-50 text-xs text-gray-500">
            {analysis.package_manager}
          </span>
          {analysis.has_dockerfile && (
            <span className="inline-flex items-center px-2 py-1 rounded-md bg-cyan-50 text-xs text-cyan-700">
              Docker
            </span>
          )}
        </div>
        <div className="h-8 w-px bg-gray-200" />
        <div className="flex items-center gap-1.5">
          {currentPipeline.stages.map((s) => (
            <div
              key={s.id}
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: agentColors[s.agent].color }}
              title={`${s.id} (${s.agent})`}
            />
          ))}
          <span className="text-xs text-gray-400 ml-1">{currentPipeline.stages.length} stages</span>
        </div>
      </div>
    </div>
  );
}

function AppContent() {
  const { currentPipeline, isRegenerating, isEditing } = usePipelineContext();

  // Show regenerate form (pre-filled with current pipeline's repo/goal/name)
  if (isRegenerating && currentPipeline) {
    return (
      <Layout>
        <CreatePipeline
          prefill={{
            repoUrl: currentPipeline.repo_url,
            goal: currentPipeline.goal,
            name: currentPipeline.name,
            useDocker: false,
          }}
        />
      </Layout>
    );
  }

  // Show edit mode
  if (isEditing && currentPipeline) {
    return (
      <Layout>
        <EditPipeline />
      </Layout>
    );
  }

  return (
    <Layout>
      {!currentPipeline ? (
        <CreatePipeline />
      ) : (
        <div className="flex flex-col h-full">
          <PipelineInfo />
          <ExecutionControls />
          <StatusBanner />
          <PipelineDAG />
          <StageDetailPanel />
        </div>
      )}
    </Layout>
  );
}

export default function App() {
  return <AppContent />;
}
