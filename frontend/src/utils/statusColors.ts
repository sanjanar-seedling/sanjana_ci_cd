import type { AgentType, StageStatus } from '../types/pipeline';

export const statusConfig: Record<StageStatus, {
  border: string;
  bg: string;
  text: string;
  label: string;
}> = {
  pending:  { border: '#D5D8DC', bg: '#FFFFFF',  text: '#5D6D7E', label: 'Pending' },
  running:  { border: '#2E75B6', bg: '#EAF2F8',  text: '#2E75B6', label: 'Running' },
  success:  { border: '#27AE60', bg: '#EAFAF1',  text: '#27AE60', label: 'Success' },
  failed:   { border: '#C0392B', bg: '#FDEDEC',  text: '#C0392B', label: 'Failed' },
  skipped:  { border: '#E67E22', bg: '#FEF5E7',  text: '#E67E22', label: 'Skipped' },
};

export const agentColors: Record<AgentType, { color: string; label: string }> = {
  build:    { color: '#27AE60', label: 'Build' },
  test:     { color: '#2E75B6', label: 'Test' },
  security: { color: '#C0392B', label: 'Security' },
  deploy:   { color: '#E67E22', label: 'Deploy' },
  verify:   { color: '#8E44AD', label: 'Verify' },
};
