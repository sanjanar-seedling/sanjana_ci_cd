import React, { createContext, useContext, useState, useCallback } from 'react';
import type { PipelineSpec, StageStatus, StageResult, HistoryEntry } from '../types/pipeline';

interface PipelineState {
  currentPipeline: PipelineSpec | null;
  stageStatuses: Map<string, StageStatus>;
  stageResults: Map<string, StageResult>;
  isExecuting: boolean;
  executionHistory: HistoryEntry[];
  selectedStageId: string | null;
  replannerInfo: { stageId: string; strategy?: string; reason?: string } | null;
}

interface PipelineActions {
  setPipeline: (spec: PipelineSpec) => void;
  clearPipeline: () => void;
  updateStageStatus: (stageId: string, status: StageStatus) => void;
  setStageResult: (stageId: string, result: StageResult) => void;
  setBulkResults: (results: Record<string, StageResult>) => void;
  startExecution: () => void;
  stopExecution: () => void;
  addToHistory: (entry: HistoryEntry) => void;
  selectStage: (stageId: string | null) => void;
  setReplannerInfo: (info: PipelineState['replannerInfo']) => void;
  loadFromHistory: (entry: HistoryEntry) => void;
}

const PipelineContext = createContext<(PipelineState & PipelineActions) | null>(null);

export function PipelineProvider({ children }: { children: React.ReactNode }) {
  const [currentPipeline, setCurrentPipeline] = useState<PipelineSpec | null>(null);
  const [stageStatuses, setStageStatuses] = useState<Map<string, StageStatus>>(new Map());
  const [stageResults, setStageResults] = useState<Map<string, StageResult>>(new Map());
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionHistory, setExecutionHistory] = useState<HistoryEntry[]>([]);
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);
  const [replannerInfo, setReplannerInfo] = useState<PipelineState['replannerInfo']>(null);

  const setPipeline = useCallback((spec: PipelineSpec) => {
    setCurrentPipeline(spec);
    const statuses = new Map<string, StageStatus>();
    for (const stage of spec.stages) {
      statuses.set(stage.id, 'pending');
    }
    setStageStatuses(statuses);
    setStageResults(new Map());
    setSelectedStageId(null);
    setReplannerInfo(null);
  }, []);

  const clearPipeline = useCallback(() => {
    setCurrentPipeline(null);
    setStageStatuses(new Map());
    setStageResults(new Map());
    setIsExecuting(false);
    setSelectedStageId(null);
    setReplannerInfo(null);
  }, []);

  const updateStageStatus = useCallback((stageId: string, status: StageStatus) => {
    setStageStatuses((prev) => {
      const next = new Map(prev);
      next.set(stageId, status);
      return next;
    });
  }, []);

  const setStageResult = useCallback((stageId: string, result: StageResult) => {
    setStageResults((prev) => {
      const next = new Map(prev);
      next.set(stageId, result);
      return next;
    });
    setStageStatuses((prev) => {
      const next = new Map(prev);
      next.set(stageId, result.status);
      return next;
    });
  }, []);

  const setBulkResults = useCallback((results: Record<string, StageResult>) => {
    const newResults = new Map<string, StageResult>();
    const newStatuses = new Map<string, StageStatus>();
    for (const [id, result] of Object.entries(results)) {
      newResults.set(id, result);
      newStatuses.set(id, result.status);
    }
    setStageResults(newResults);
    setStageStatuses((prev) => {
      const merged = new Map(prev);
      for (const [id, status] of newStatuses) {
        merged.set(id, status);
      }
      return merged;
    });
  }, []);

  const startExecution = useCallback(() => setIsExecuting(true), []);
  const stopExecution = useCallback(() => setIsExecuting(false), []);

  const addToHistory = useCallback((entry: HistoryEntry) => {
    setExecutionHistory((prev) => [entry, ...prev]);
  }, []);

  const selectStage = useCallback((stageId: string | null) => {
    setSelectedStageId(stageId);
  }, []);

  const loadFromHistory = useCallback((entry: HistoryEntry) => {
    setCurrentPipeline(entry.pipeline);
    const statuses = new Map<string, StageStatus>();
    const results = new Map<string, StageResult>();
    if (entry.results) {
      for (const [id, result] of Object.entries(entry.results)) {
        statuses.set(id, result.status);
        results.set(id, result);
      }
    } else {
      for (const stage of entry.pipeline.stages) {
        statuses.set(stage.id, 'pending');
      }
    }
    setStageStatuses(statuses);
    setStageResults(results);
    setIsExecuting(false);
    setSelectedStageId(null);
    setReplannerInfo(null);
  }, []);

  const value: PipelineState & PipelineActions = {
    currentPipeline,
    stageStatuses,
    stageResults,
    isExecuting,
    executionHistory,
    selectedStageId,
    replannerInfo,
    setPipeline,
    clearPipeline,
    updateStageStatus,
    setStageResult,
    setBulkResults,
    startExecution,
    stopExecution,
    addToHistory,
    selectStage,
    setReplannerInfo,
    loadFromHistory,
  };

  return (
    <PipelineContext.Provider value={value}>
      {children}
    </PipelineContext.Provider>
  );
}

export function usePipelineContext() {
  const ctx = useContext(PipelineContext);
  if (!ctx) throw new Error('usePipelineContext must be used within PipelineProvider');
  return ctx;
}
