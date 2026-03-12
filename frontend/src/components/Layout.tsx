import React from 'react';
import { GitBranch, Plus, ArrowLeft } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import ExecutionHistory from './ExecutionHistory';

export default function Layout({ children }: { children: React.ReactNode }) {
  const { currentPipeline, clearPipeline } = usePipelineContext();

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-[280px] bg-sidebar flex flex-col flex-shrink-0">
        {/* Logo */}
        <div className="px-5 py-6 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent flex items-center justify-center">
              <GitBranch className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-white font-semibold text-sm leading-tight">CI/CD</h1>
              <p className="text-blue-200/60 text-xs">Orchestrator</p>
            </div>
          </div>
        </div>

        {/* New Pipeline Button */}
        <div className="px-4 py-4">
          <button
            onClick={clearPipeline}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-accent hover:bg-accent/80 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Pipeline
          </button>
        </div>

        {/* History */}
        <div className="flex-1 overflow-y-auto">
          <ExecutionHistory />
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col bg-gray-50 overflow-hidden">
        {/* Header bar */}
        {currentPipeline && (
          <div className="h-12 bg-white border-b border-gray-200 flex items-center px-5 flex-shrink-0">
            <button
              onClick={clearPipeline}
              className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              New Pipeline
            </button>
            <span className="mx-3 text-gray-300">|</span>
            {currentPipeline.name && (
              <>
                <span className="text-sm font-medium text-gray-800 truncate">
                  {currentPipeline.name}
                </span>
                <span className="mx-3 text-gray-300">|</span>
              </>
            )}
            <span className="text-sm text-gray-600 truncate">
              {currentPipeline.repo_url}
            </span>
          </div>
        )}

        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
