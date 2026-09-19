import { Box, Flex, Text } from '@radix-ui/themes';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { TopicTrendSeries } from '../api/topics';

const COLORS = [
  'var(--blue-9)',
  'var(--red-9)',
  'var(--grass-9)',
  'var(--orange-9)',
  'var(--violet-9)',
  'var(--cyan-9)',
  'var(--pink-9)',
  'var(--amber-9)',
  'var(--teal-9)',
  'var(--brown-9)',
];

const WIDTH = 900;
const HEIGHT = 280;
const MARGIN = { top: 10, right: 16, bottom: 24, left: 40 };

type YearSeries = {
  topic_id: number;
  label: string;
  color: string;
  byYear: Map<number, number>;
};

function binByYear(series: TopicTrendSeries[]): { years: number[]; lines: YearSeries[] } {
  const allYears = new Set<number>();
  const lines = series.map((s, index) => {
    const byYear = new Map<number, number>();
    for (const point of s.points) {
      const year = new Date(point.timestamp).getFullYear();
      if (Number.isNaN(year)) continue;
      byYear.set(year, (byYear.get(year) ?? 0) + point.frequency);
      allYears.add(year);
    }
    return { topic_id: s.topic_id, label: s.label, color: COLORS[index % COLORS.length], byYear };
  });
  return { years: [...allYears].sort((a, b) => a - b), lines };
}

export function TopicTrendsChart({ series }: { series: TopicTrendSeries[] }) {
  const [hidden, setHidden] = useState<Set<number>>(new Set());
  const { years, lines } = useMemo(() => binByYear(series), [series]);

  if (years.length < 2) return null;

  const visible = lines.filter((line) => !hidden.has(line.topic_id));
  const minYear = years[0];
  const maxYear = years[years.length - 1];
  const maxValue = Math.max(
    1,
    ...visible.flatMap((line) => [...line.byYear.values()]),
  );

  const x = (year: number) =>
    MARGIN.left + ((year - minYear) / (maxYear - minYear)) * (WIDTH - MARGIN.left - MARGIN.right);
  const y = (value: number) =>
    MARGIN.top + (1 - value / maxValue) * (HEIGHT - MARGIN.top - MARGIN.bottom);

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * maxValue));
  const xTickCount = Math.min(8, maxYear - minYear);
  const xTicks = Array.from({ length: xTickCount + 1 }, (_, i) =>
    Math.round(minYear + ((maxYear - minYear) * i) / xTickCount),
  );

  const toggle = (topicId: number) =>
    setHidden((current) => {
      const next = new Set(current);
      if (next.has(topicId)) next.delete(topicId);
      else next.add(topicId);
      return next;
    });

  return (
    <Flex direction="column" gap="3">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: '100%', height: 'auto' }}
        role="img"
        aria-label="Topic activity over time"
      >
        {yTicks.map((tick) => (
          <g key={tick}>
            <line
              x1={MARGIN.left}
              x2={WIDTH - MARGIN.right}
              y1={y(tick)}
              y2={y(tick)}
              stroke="var(--gray-4)"
              strokeWidth={1}
            />
            <text
              x={MARGIN.left - 6}
              y={y(tick) + 3}
              textAnchor="end"
              fontSize={10}
              fill="var(--gray-9)"
            >
              {tick}
            </text>
          </g>
        ))}
        {xTicks.map((year) => (
          <text
            key={year}
            x={x(year)}
            y={HEIGHT - 6}
            textAnchor="middle"
            fontSize={10}
            fill="var(--gray-9)"
          >
            {year}
          </text>
        ))}
        {visible.map((line) => {
          const path = years
            .map((year, index) => {
              const value = line.byYear.get(year) ?? 0;
              return `${index === 0 ? 'M' : 'L'}${x(year).toFixed(1)},${y(value).toFixed(1)}`;
            })
            .join(' ');
          return (
            <g key={line.topic_id}>
              <path d={path} fill="none" stroke={line.color} strokeWidth={2} strokeLinejoin="round">
                <title>{line.label}</title>
              </path>
              {years.map((year) => {
                const value = line.byYear.get(year) ?? 0;
                if (!value) return null;
                return (
                  <circle key={year} cx={x(year)} cy={y(value)} r={2.5} fill={line.color}>
                    <title>{`${line.label} — ${year}: ${value} bills`}</title>
                  </circle>
                );
              })}
            </g>
          );
        })}
      </svg>
      <Flex gap="3" wrap="wrap">
        {lines.map((line) => {
          const isHidden = hidden.has(line.topic_id);
          return (
            <Flex
              key={line.topic_id}
              align="center"
              gap="1"
              onClick={() => toggle(line.topic_id)}
              style={{ cursor: 'pointer', opacity: isHidden ? 0.35 : 1 }}
            >
              <Box
                style={{
                  width: 12,
                  height: 3,
                  borderRadius: 2,
                  background: line.color,
                  flexShrink: 0,
                }}
              />
              <Text size="1" style={{ textTransform: 'capitalize' }}>
                <Link to={`/topics/${line.topic_id}`} onClick={(event) => event.stopPropagation()}>
                  {line.label}
                </Link>
              </Text>
            </Flex>
          );
        })}
      </Flex>
      <Text size="1" color="gray">
        Bills per year for the largest topics. Click a legend entry to toggle its line.
      </Text>
    </Flex>
  );
}
