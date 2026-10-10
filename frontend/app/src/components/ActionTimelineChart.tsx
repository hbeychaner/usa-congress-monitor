import type { EChartsCoreOption } from 'echarts/core';
import { LineChart, ScatterChart } from 'echarts/charts';
import {
    DataZoomComponent,
    GridComponent,
    LegendComponent,
    TooltipComponent,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { Flex, Text } from '@radix-ui/themes';
import { useEffect, useMemo, useRef, useState } from 'react';

echarts.use([
    LineChart,
    ScatterChart,
    GridComponent,
    TooltipComponent,
    LegendComponent,
    DataZoomComponent,
    CanvasRenderer,
]);

export type TimelineAction = {
    date: string;
    text: string;
    source?: string;
};

type Lane = { name: string; color: string; pattern: RegExp };

// First matching lane wins, so order runs from most to least specific.
const LANES: Lane[] = [
    { name: 'Law', color: '#46a758', pattern: /became (public|private) law|signed by president|presented to president|veto/i },
    { name: 'Floor', color: '#e5484d', pattern: /passed|agreed to|failed|vote|cloture|motion|considered|rule|placed on|calendar|received in the (senate|house)|message on/i },
    { name: 'Committee', color: '#3b82f6', pattern: /committee|subcommittee|referred|hearing|markup|reported|discharge/i },
    { name: 'Introduced', color: '#8e4ec6', pattern: /introduced|sponsor|cosponsor/i },
];
const OTHER_LANE: Lane = { name: 'Other', color: '#8b8d98', pattern: /./ };
const ALL_LANES = [...LANES, OTHER_LANE].reverse();
const SAME_DAY_JITTER = 0.14;
const POINT_SIZE = 13;
const CHART_HEIGHT = 300;
// Canvas cannot resolve CSS variables, so colors are literal.
const AXIS_TEXT = '#8b8d98';
const LANE_TEXT = '#60646c';
const GRID_FAINT = '#eceef0';
const GRID_STRONG = '#cdced6';
const DAY_MS = 86_400_000;
const SINGLE_DAY_PADDING_DAYS = 3;
const RANGE_PADDING = 0.05;
const DAY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})/;
const HTML_ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

function escapeHtml(value: string): string {
    return value.replace(/[&<>"']/g, (char) => HTML_ESCAPES[char]);
}

// Calendar day as UTC midnight, so the same date from different sources lands on one x value.
function dayOf(date: string): number {
    const match = DAY_PATTERN.exec(date);
    return match ? Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : Number.NaN;
}

function formatDay(time: number): string {
    return new Date(time).toLocaleDateString(undefined, { timeZone: 'UTC' });
}

// Same day and text from several sources collapse into one action listing every source.
function mergeDuplicates(actions: TimelineAction[]): TimelineAction[] {
    const merged = new Map<string, TimelineAction>();
    for (const action of actions) {
        const key = `${dayOf(action.date)}|${action.text.trim().toLowerCase()}`;
        const existing = merged.get(key);
        if (!existing) {
            merged.set(key, { ...action });
        } else if (action.source && !existing.source?.split(', ').includes(action.source)) {
            existing.source = existing.source ? `${existing.source}, ${action.source}` : action.source;
        }
    }
    return [...merged.values()];
}

function laneFor(text: string): Lane {
    return LANES.find((lane) => lane.pattern.test(text)) ?? OTHER_LANE;
}

type Point = { value: [number, number]; action: TimelineAction };

function buildPoints(actions: TimelineAction[]): Map<string, Point[]> {
    const byLane = new Map<string, Point[]>(ALL_LANES.map((lane) => [lane.name, []]));
    const seenPerSlot = new Map<string, number>();
    const dated = mergeDuplicates(actions)
        .map((action) => ({ action, time: dayOf(action.date) }))
        .filter((entry) => !Number.isNaN(entry.time))
        .sort((a, b) => a.time - b.time);
    for (const { action, time } of dated) {
        const lane = laneFor(action.text);
        const row = ALL_LANES.findIndex((candidate) => candidate.name === lane.name);
        const slot = `${lane.name}:${time}`;
        const seen = seenPerSlot.get(slot) ?? 0;
        seenPerSlot.set(slot, seen + 1);
        byLane.get(lane.name)?.push({ value: [time, row + seen * SAME_DAY_JITTER], action });
    }
    return byLane;
}

type Props = { actions: TimelineAction[] };

/** Horizontal legislative timeline: one lane per stage, zoomable, click to read an action. */
export function ActionTimelineChart({ actions }: Props) {
    const containerRef = useRef<HTMLDivElement>(null);
    const points = useMemo(() => buildPoints(actions), [actions]);
    const [selected, setSelected] = useState<TimelineAction | null>(null);

    useEffect(() => {
        setSelected(null);
        const el = containerRef.current;
        if (!el) return;
        const chart = echarts.init(el);
        const chronological = ALL_LANES.flatMap((lane) => points.get(lane.name) ?? []).sort((a, b) => a.value[0] - b.value[0]);
        const times = chronological.map((point) => point.value[0]);
        const first = Math.min(...times);
        const last = Math.max(...times);
        const pad = last === first ? SINGLE_DAY_PADDING_DAYS * DAY_MS : (last - first) * RANGE_PADDING;
        const option: EChartsCoreOption = {
            useUTC: true,
            grid: { top: 16, right: 24, bottom: 76, left: 84 },
            tooltip: {
                trigger: 'item',
                confine: true,
                extraCssText: 'max-width: 360px; white-space: normal;',
                formatter: (params: { data?: Point }) => {
                    const action = params.data?.action;
                    if (!action) return '';
                    const source = action.source ? ` · ${escapeHtml(action.source)}` : '';
                    return `<b>${escapeHtml(formatDay(dayOf(action.date)))}</b>${source}<br/>${escapeHtml(action.text)}`;
                },
            },
            legend: {
                bottom: 0,
                data: [...ALL_LANES].reverse().map((lane) => lane.name),
                textStyle: { color: LANE_TEXT },
            },
            xAxis: {
                type: 'time',
                min: first - pad,
                max: last + pad,
                minInterval: DAY_MS,
                axisLabel: { color: AXIS_TEXT },
                axisLine: { lineStyle: { color: GRID_STRONG } },
                splitLine: { show: true, lineStyle: { color: GRID_FAINT } },
            },
            yAxis: {
                type: 'value',
                min: -0.5,
                max: ALL_LANES.length - 0.5,
                interval: 1,
                axisLine: { show: false },
                axisTick: { show: false },
                splitLine: { lineStyle: { color: GRID_FAINT } },
                axisLabel: {
                    color: LANE_TEXT,
                    formatter: (value: number) => ALL_LANES[value]?.name ?? '',
                },
            },
            dataZoom: [
                { type: 'inside', filterMode: 'none' },
                { type: 'slider', height: 18, bottom: 28, filterMode: 'none' },
            ],
            series: [
                {
                    type: 'line',
                    silent: true,
                    symbol: 'none',
                    z: 1,
                    lineStyle: { color: GRID_STRONG, width: 1, type: 'dashed' },
                    data: chronological.map((point) => [point.value[0], Math.round(point.value[1])]),
                    tooltip: { show: false },
                },
                ...ALL_LANES.map((lane) => ({
                    name: lane.name,
                    type: 'scatter',
                    z: 2,
                    symbolSize: POINT_SIZE,
                    itemStyle: { color: lane.color, borderColor: '#fff', borderWidth: 1.5 },
                    emphasis: { scale: 1.5 },
                    data: points.get(lane.name) ?? [],
                })),
            ],
        };
        chart.setOption(option);
        chart.on('click', (params) => {
            const action = (params.data as Point | undefined)?.action;
            if (action) setSelected(action);
        });
        const observer = new ResizeObserver(() => chart.resize());
        observer.observe(el);
        return () => {
            observer.disconnect();
            chart.dispose();
        };
    }, [points]);

    if (actions.length === 0) return null;
    return (
        <Flex direction="column" gap="2">
            <div ref={containerRef} style={{ width: '100%', height: CHART_HEIGHT }} />
            <Text size="2" color="gray">
                {selected
                    ? `${formatDay(dayOf(selected.date))}${selected.source ? ` · ${selected.source}` : ''} — ${selected.text}`
                    : 'Click a point to read the action; scroll or drag the slider to zoom.'}
            </Text>
        </Flex>
    );
}
