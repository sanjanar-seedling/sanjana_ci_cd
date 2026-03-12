import { memo, useEffect, useState } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import {
  Hammer,
  FlaskConical,
  Shield,
  Rocket,
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  SkipForward,
} from 'lucide-react';
import type { Stage, StageStatus, AgentType } from '../types/pipeline';
import { statusConfig, agentColors } from '../utils/statusColors';

const agentIcons: Record<AgentType, React.ReactNode> = {
  build: <Hammer className="w-4 h-4" />,
  test: <FlaskConical className="w-4 h-4" />,
  security: <Shield className="w-4 h-4" />,
  deploy: <Rocket className="w-4 h-4" />,
  verify: <Activity className="w-4 h-4" />,
};

const statusIcons: Record<StageStatus, React.ReactNode> = {
  pending: <Clock className="w-3.5 h-3.5" />,
  running: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
  success: <CheckCircle className="w-3.5 h-3.5" />,
  failed: <XCircle className="w-3.5 h-3.5" />,
  skipped: <SkipForward className="w-3.5 h-3.5" />,
};

interface StageNodeData {
  stage: Stage;
  status: StageStatus;
}

function StageNodeComponent({ data }: NodeProps<StageNodeData>) {
  const { stage, status } = data;
  const config = statusConfig[status];
  const agentColor = agentColors[stage.agent];
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (status !== 'running') {
      setElapsed(0);
      return;
    }
    const start = Date.now();
    const timer = setInterval(() => setElapsed((Date.now() - start) / 1000), 100);
    return () => clearInterval(timer);
  }, [status]);

  return (
    <div
      className={`rounded-xl border-2 bg-white shadow-sm transition-all duration-300 w-[200px] ${
        status === 'running' ? 'animate-pulse-border' : ''
      }`}
      style={{ borderColor: config.border, backgroundColor: config.bg }}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-400 !w-2 !h-2 !border-0" />

      <div className="px-3.5 py-3">
        {/* Header row */}
        <div className="flex items-center justify-between mb-1.5">
          <span className="font-semibold text-sm text-gray-800 truncate">{stage.id}</span>
          <span style={{ color: config.text }}>{statusIcons[status]}</span>
        </div>

        {/* Agent badge */}
        <div className="flex items-center gap-1.5">
          <span style={{ color: agentColor.color }}>{agentIcons[stage.agent]}</span>
          <span className="text-xs text-gray-500">{agentColor.label}</span>
          {!stage.critical && (
            <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-400 rounded-full ml-auto">
              optional
            </span>
          )}
        </div>

        {/* Running timer */}
        {status === 'running' && (
          <div className="mt-2 text-[11px] text-accent font-mono">
            {elapsed.toFixed(1)}s
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-gray-400 !w-2 !h-2 !border-0" />
    </div>
  );
}

export default memo(StageNodeComponent);
