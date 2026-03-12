import { useState, useCallback } from 'react';
import { createPipeline, executePipeline, updatePipeline } from '../api/client';
import type { PipelineSpec, Stage, StageResult } from '../types/pipeline';

export function usePipeline() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = useCallback(async (
    repoUrl: string,
    goal: string,
    useDocker: boolean = false,
    name: string = '',
  ): Promise<PipelineSpec | null> => {
    setLoading(true);
    setError(null);
    try {
      const spec = await createPipeline(repoUrl, goal, useDocker, name);
      return spec;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create pipeline');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const execute = useCallback(async (pipelineId: string): Promise<Record<string, StageResult> | null> => {
    setLoading(true);
    setError(null);
    try {
      const results = await executePipeline(pipelineId);
      return results;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute pipeline');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const update = useCallback(async (
    pipelineId: string,
    changes: { name?: string; goal?: string; stages?: Stage[] },
  ): Promise<PipelineSpec | null> => {
    setLoading(true);
    setError(null);
    try {
      const spec = await updatePipeline(pipelineId, changes);
      return spec;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update pipeline');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, generate, execute, update, setError };
}
