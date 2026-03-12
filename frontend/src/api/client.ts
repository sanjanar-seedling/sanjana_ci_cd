import type { PipelineSpec, StageResult } from '../types/pipeline';

const API_BASE = '';

export async function createPipeline(repoUrl: string, goal: string): Promise<PipelineSpec> {
  const params = new URLSearchParams({ repo_url: repoUrl, goal });
  const res = await fetch(`${API_BASE}/pipelines?${params}`, { method: 'POST' });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to create pipeline: ${res.statusText}`);
  }
  return res.json();
}

export async function executePipeline(pipelineId: string): Promise<Record<string, StageResult>> {
  const res = await fetch(`${API_BASE}/pipelines/${pipelineId}/execute`, { method: 'POST' });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to execute pipeline: ${res.statusText}`);
  }
  return res.json();
}

export async function getPipeline(pipelineId: string): Promise<PipelineSpec> {
  const res = await fetch(`${API_BASE}/pipelines/${pipelineId}`);
  if (!res.ok) throw new Error('Pipeline not found');
  return res.json();
}

export async function getResults(pipelineId: string): Promise<Record<string, StageResult>> {
  const res = await fetch(`${API_BASE}/pipelines/${pipelineId}/results`);
  if (!res.ok) throw new Error('Results not found');
  return res.json();
}

export function createWebSocketUrl(pipelineId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/ws/${pipelineId}`;
}
