import type { EChartsCoreOption } from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { Flex, Text } from '@radix-ui/themes';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { fetchVoteBreakdown, type VoteBreakdownResponse, type VotePosition } from '../api/votes';
import type { PartyGroup } from '../api/graph';
import { PARTY_COLORS } from './MemberGraphView';

echarts.use([BarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const POSITIONS: { position: VotePosition; label: string; color: string }[] = [
  { position: 'yea', label: 'Yea', color: '#16a34a' },
  { position: 'nay', label: 'Nay', color: '#dc2626' },
  { position: 'present', label: 'Present', color: '#f59e0b' },
  { position: 'not_voting', label: 'Not voting', color: '#9ca3af' },
];
const PARTY_LABELS: Record<PartyGroup, string> = {
  democratic: 'Democratic',
  republican: 'Republican',
  other: 'Other',
};
const ROW_HEIGHT = 48;

type Selection = { party: PartyGroup; position: VotePosition };

/** Share of yea/nay/present/not-voting per party, with the members behind each segment. */
export function VotePartyChart({ rollcallId }: { rollcallId: string }) {
  const [data, setData] = useState<VoteBreakdownResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [selection, setSelection] = useState<Selection | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setData(null);
    setFailed(false);
    setSelection(null);
    fetchVoteBreakdown(rollcallId).then(setData).catch(() => setFailed(true));
  }, [rollcallId]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !data || data.parties.length === 0) return;
    const chart = echarts.init(el);
    const rows = [...data.parties].reverse();
    const totals = rows.map((row) => row.positions.reduce((sum, item) => sum + item.members.length, 0));
    const option: EChartsCoreOption = {
      grid: { top: 28, right: 12, bottom: 4, left: 8, containLabel: true },
      legend: { top: 0, textStyle: { color: 'var(--gray-11)' } },
      tooltip: {
        trigger: 'item',
        confine: true,
        formatter: (params: { seriesName: string; dataIndex: number; value: number }) => {
          const count = rows[params.dataIndex].positions.find((item) => PARTY_POSITION_LABEL[item.position] === params.seriesName)?.members.length ?? 0;
          return `${PARTY_LABELS[rows[params.dataIndex].party]} · ${params.seriesName}: ${count} (${params.value.toFixed(1)}%)`;
        },
      },
      xAxis: { type: 'value', max: 100, show: false },
      yAxis: {
        type: 'category',
        data: rows.map((row, index) => `${PARTY_LABELS[row.party]} (${totals[index]})`),
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: { color: 'var(--gray-11)' },
      },
      series: POSITIONS.map(({ position, label, color }) => ({
        name: label,
        type: 'bar',
        stack: 'share',
        itemStyle: { color },
        label: {
          show: true,
          color: '#fff',
          formatter: (params: { value: number }) => (params.value >= 6 ? `${Math.round(params.value)}%` : ''),
        },
        data: rows.map((row, index) => {
          const count = row.positions.find((item) => item.position === position)?.members.length ?? 0;
          return totals[index] ? (count / totals[index]) * 100 : 0;
        }),
      })),
    };
    chart.setOption(option);
    chart.on('click', (params) => {
      const row = rows[params.dataIndex];
      const clicked = POSITIONS.find((item) => item.label === params.seriesName);
      if (row && clicked) setSelection({ party: row.party, position: clicked.position });
    });
    const resize = () => chart.resize();
    window.addEventListener('resize', resize);
    return () => {
      window.removeEventListener('resize', resize);
      chart.dispose();
    };
  }, [data]);

  if (failed) return <Text size="1" color="gray">Party breakdown is unavailable for this vote.</Text>;
  if (!data) return <Text size="1" color="gray">Loading party breakdown…</Text>;
  if (data.parties.length === 0) return null;

  const members = selection
    ? data.parties
        .find((row) => row.party === selection.party)
        ?.positions.find((item) => item.position === selection.position)?.members ?? []
    : [];
  const selectedLabel = selection ? POSITIONS.find((item) => item.position === selection.position)?.label : null;

  return (
    <Flex direction="column" gap="2">
      <div ref={containerRef} style={{ width: '100%', height: data.parties.length * ROW_HEIGHT + 40 }} />
      {selection ? (
        <Flex direction="column" gap="1">
          <Text size="2" weight="bold" style={{ color: PARTY_COLORS[selection.party] }}>
            {PARTY_LABELS[selection.party]} · {selectedLabel} ({members.length})
          </Text>
          <Flex wrap="wrap" gap="2">
            {members.map((member) => (
              <Text size="1" key={member.bioguide_id}>
                <Link to={`/members/${encodeURIComponent(member.bioguide_id)}`}>
                  {member.name}{member.state ? ` (${member.state})` : ''}
                </Link>
              </Text>
            ))}
          </Flex>
        </Flex>
      ) : (
        <Text size="1" color="gray">Select a segment to list those members.</Text>
      )}
    </Flex>
  );
}

const PARTY_POSITION_LABEL: Record<VotePosition, string> = Object.fromEntries(
  POSITIONS.map((item) => [item.position, item.label]),
) as Record<VotePosition, string>;
