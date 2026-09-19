import type { EChartsCoreOption } from 'echarts/core';
import { LineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

const PALETTE = [
  '#3b82f6', '#e5484d', '#46a758', '#f76b15', '#8e4ec6',
  '#05a2c2', '#d6409f', '#ffb224', '#12a594', '#ad7f58',
];

export type TrendSeries = {
  name: string;
  /** [year, value] pairs on a uniform year grid. */
  points: [number, number][];
};

type Props = {
  series: TrendSeries[];
  height?: number;
  onSeriesClick?: (name: string) => void;
};

/** EMM-style interactive multi-line trend chart (ECharts canvas). */
export function TrendLineChart({ series, height = 320, onSeriesClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const clickRef = useRef(onSeriesClick);
  clickRef.current = onSeriesClick;

  useEffect(() => {
    const el = containerRef.current;
    if (!el || series.length === 0) return;
    const chart = echarts.init(el);
    const option: EChartsCoreOption = {
      color: PALETTE,
      grid: { top: 12, right: 16, bottom: 64, left: 48 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', label: { backgroundColor: 'var(--gray-9)' } },
        order: 'valueDesc',
        confine: true,
      },
      legend: {
        type: 'scroll',
        bottom: 0,
        icon: 'roundRect',
        itemWidth: 14,
        itemHeight: 4,
        textStyle: { color: 'var(--gray-11)' },
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        axisLabel: { color: 'var(--gray-10)' },
        axisLine: { lineStyle: { color: 'var(--gray-6)' } },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: 'var(--gray-10)' },
        splitLine: { lineStyle: { color: 'var(--gray-4)' } },
      },
      dataZoom: [{ type: 'inside' }],
      series: series.map((s) => ({
        name: s.name,
        type: 'line',
        smooth: 0.25,
        showSymbol: false,
        emphasis: { focus: 'series' },
        data: s.points.map(([year, value]) => [String(year), value]),
      })),
    };
    chart.setOption(option);
    chart.on('click', (params) => {
      if (params.seriesName) clickRef.current?.(params.seriesName);
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(el);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [series]);

  if (series.length === 0) return null;
  return <div ref={containerRef} style={{ width: '100%', height }} />;
}
