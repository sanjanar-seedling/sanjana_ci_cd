import { useMemo, useCallback } from 'react';
import ReactFlow, {
  Background,
  MiniMap,
  Controls,
  type NodeTypes,
  BackgroundVariant,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { usePipelineContext } from '../context/PipelineContext';
import { createNodesAndEdges } from '../utils/dagLayout';
import StageNode from './StageNode';

const nodeTypes: NodeTypes = {
  stageNode: StageNode,
};

export default function PipelineDAG() {
  const { currentPipeline, stageStatuses, selectStage } = usePipelineContext();

  const { nodes, edges } = useMemo(() => {
    if (!currentPipeline) return { nodes: [], edges: [] };
    return createNodesAndEdges(currentPipeline.stages, stageStatuses);
  }, [currentPipeline, stageStatuses]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: { id: string }) => {
      selectStage(node.id);
    },
    [selectStage],
  );

  if (!currentPipeline) return null;

  return (
    <div className="flex-1 min-h-0">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        zoomOnScroll
        panOnScroll
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#E2E8F0" />
        <MiniMap
          nodeColor="#CBD5E1"
          maskColor="rgba(255,255,255,0.8)"
          className="!bg-white !border !border-gray-200 !rounded-lg !shadow-sm"
        />
        <Controls className="!bg-white !border !border-gray-200 !rounded-lg !shadow-sm" />
      </ReactFlow>
    </div>
  );
}
