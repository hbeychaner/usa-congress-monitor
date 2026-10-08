import forceAtlas2 from 'graphology-layout-forceatlas2';
import Graph from 'graphology';
import Sigma from 'sigma';
import { useEffect, useRef } from 'react';

import type { Neighborhood, PartyGroup } from '../api/graph';

export const PARTY_COLORS: Record<PartyGroup, string> = {
  democratic: '#2563eb',
  republican: '#dc2626',
  other: '#6b7280',
};

const SEED_SIZE = 12;
const NODE_SIZE = 6;

type Props = {
  data: Neighborhood;
  selectedId: string | null;
  onSelect: (bioguideId: string | null) => void;
};

function buildGraph(data: Neighborhood): Graph {
  const graph = new Graph({ type: 'undirected' });
  const nodes = data.nodes ?? [];
  nodes.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(nodes.length, 1);
    graph.addNode(node.member.bioguide_id, {
      label: node.member.display_name,
      size: node.is_seed ? SEED_SIZE : NODE_SIZE,
      color: PARTY_COLORS[node.party_group],
      x: Math.cos(angle) * 10,
      y: Math.sin(angle) * 10,
    });
  });
  (data.links ?? []).forEach((link) => {
    if (link.source === link.target || graph.hasEdge(link.source, link.target)) return;
    graph.addEdge(link.source, link.target, {
      weight: link.score,
      size: 0.3 + 2 * link.score,
      color: `rgba(90, 90, 100, ${0.05 + 0.3 * link.score ** 2})`,
    });
  });
  if (graph.order > 1) {
    forceAtlas2.assign(graph, {
      iterations: 300,
      settings: {
        ...forceAtlas2.inferSettings(graph),
        edgeWeightInfluence: 1,
        gravity: 0.5,
        scalingRatio: 20,
        barnesHutOptimize: false,
      },
    });
  }
  return graph;
}

export function MemberGraphView({ data, selectedId, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!container.current) return;
    const sigma = new Sigma(buildGraph(data), container.current, {
      labelRenderedSizeThreshold: 0,
      labelDensity: 1,
      defaultEdgeType: 'line',
    });
    sigma.on('clickNode', ({ node }) => onSelectRef.current(node));
    sigma.on('clickStage', () => onSelectRef.current(null));
    sigmaRef.current = sigma;
    return () => {
      sigma.kill();
      sigmaRef.current = null;
    };
  }, [data]);

  useEffect(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    sigma.setSetting('nodeReducer', (node, attributes) =>
      node === selectedId ? { ...attributes, highlighted: true, zIndex: 1 } : attributes,
    );
  }, [selectedId, data]);

  return <div ref={container} style={{ width: '100%', height: 640 }} />;
}
