import dagre from 'dagre';
import { type Node, type Edge, MarkerType } from 'reactflow';
import type { Stage, StageStatus } from '../types/pipeline';

const NODE_WIDTH = 200;
const NODE_HEIGHT = 80;

export function createNodesAndEdges(
  stages: Stage[],
  statuses: Map<string, StageStatus>,
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', ranksep: 80, nodesep: 60 });

  for (const stage of stages) {
    g.setNode(stage.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  for (const stage of stages) {
    for (const dep of stage.depends_on) {
      g.setEdge(dep, stage.id);
    }
  }

  dagre.layout(g);

  const nodes: Node[] = stages.map((stage) => {
    const pos = g.node(stage.id);
    return {
      id: stage.id,
      type: 'stageNode',
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: {
        stage,
        status: statuses.get(stage.id) ?? 'pending',
      },
    };
  });

  const isExecuting = Array.from(statuses.values()).some((s) => s === 'running');

  const edges: Edge[] = [];
  for (const stage of stages) {
    for (const dep of stage.depends_on) {
      edges.push({
        id: `${dep}->${stage.id}`,
        source: dep,
        target: stage.id,
        animated: isExecuting,
        style: { stroke: '#94A3B8', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#94A3B8' },
      });
    }
  }

  return { nodes, edges };
}
