import louvain from 'graphology-communities-louvain';
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

const COMMUNITY_COLORS = ['#0ea5e9', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#84cc16', '#6366f1', '#ef4444'];
const MIN_EXTENT = 20;
const TOPIC_COLOR = '#a855f7';
export const TOPIC_PREFIX = 'topic:';

export type ColorMode = 'party' | 'community';

// Shrink nodes as the neighborhood grows so large graphs stay legible.
function nodeSize(order: number, isSeed: boolean): number {
  const base = Math.max(3, 8 - order / 25);
  return isSeed ? base * 1.6 : base;
}

type Props = {
  data: Neighborhood;
  selectedId: string | null;
  colorMode: ColorMode;
  onSelect: (bioguideId: string | null) => void;
};

function buildGraph(data: Neighborhood, colorMode: ColorMode): Graph {
  const graph = new Graph({ type: 'undirected' });
  const nodes = data.nodes ?? [];
  nodes.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(nodes.length, 1);
    graph.addNode(node.member.bioguide_id, {
      label: node.member.display_name,
      size: nodeSize(nodes.length, node.is_seed),
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
      color: `rgba(90, 90, 100, ${0.2 + 0.5 * link.score})`,
    });
  });
  (data.topic_nodes ?? []).forEach((topic) => {
    graph.addNode(`${TOPIC_PREFIX}${topic.topic_id}`, {
      label: topic.label,
      size: nodeSize(nodes.length, false) * 0.8,
      color: TOPIC_COLOR,
      x: Math.random() * 10 - 5,
      y: Math.random() * 10 - 5,
    });
  });
  (data.topic_links ?? []).forEach((link) => {
    const topicId = `${TOPIC_PREFIX}${link.topic_id}`;
    if (!graph.hasNode(link.member) || !graph.hasNode(topicId) || graph.hasEdge(link.member, topicId)) return;
    graph.addEdge(link.member, topicId, {
      weight: 1,
      size: 0.5 + 3 * link.share,
      color: 'rgba(168, 85, 247, 0.5)',
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
  if (colorMode === 'community' && graph.size > 0) {
    const communities = louvain(graph, { getEdgeWeight: 'weight' });
    graph.forEachNode((id) => {
      if (id.startsWith(TOPIC_PREFIX)) return;
      graph.setNodeAttribute(id, 'color', COMMUNITY_COLORS[communities[id] % COMMUNITY_COLORS.length]);
    });
  }
  return graph;
}

// A fixed minimum extent keeps sizes sane when only a few nodes are shown.
function paddedBBox(graph: Graph): { x: [number, number]; y: [number, number] } {
  const xs: number[] = [];
  const ys: number[] = [];
  graph.forEachNode((_, attrs) => {
    xs.push(attrs.x);
    ys.push(attrs.y);
  });
  const axis = (values: number[]): [number, number] => {
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const half = Math.max((hi - lo) / 2, MIN_EXTENT / 2);
    const mid = (lo + hi) / 2;
    return [mid - half, mid + half];
  };
  return { x: axis(xs), y: axis(ys) };
}

export function MemberGraphView({ data, selectedId, colorMode, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!container.current) return;
    const graph = buildGraph(data, colorMode);
    const sigma = new Sigma(graph, container.current, {
      labelRenderedSizeThreshold: 0,
      labelDensity: 1,
      defaultEdgeType: 'line',
    });
    sigma.setCustomBBox(paddedBBox(graph));
    sigma.on('clickNode', ({ node }) => onSelectRef.current(node));
    sigma.on('clickStage', () => onSelectRef.current(null));
    sigmaRef.current = sigma;
    return () => {
      sigma.kill();
      sigmaRef.current = null;
    };
  }, [data, colorMode]);

  useEffect(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    sigma.setSetting('nodeReducer', (node, attributes) =>
      node === selectedId ? { ...attributes, highlighted: true, zIndex: 1 } : attributes,
    );
  }, [selectedId, data]);

  return <div ref={container} style={{ width: '100%', height: 640 }} />;
}
