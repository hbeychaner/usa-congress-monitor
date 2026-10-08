import type { EChartsCoreOption } from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

export type BarDatum = { label: string; value: number };

type Props = {
  data: BarDatum[];
  /** Formats the value in labels and tooltips. */
  formatValue?: (value: number) => string;
  onBarClick?: (label: string) => void;
  rowHeight?: number;
};

/** Horizontal bar chart, largest value on top. */
export function HorizontalBarChart({
  data,
  formatValue = (value) => String(value),
  onBarClick,
  rowHeight = 26,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const clickRef = useRef(onBarClick);
  clickRef.current = onBarClick;
  const dataKey = JSON.stringify(data);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || data.length === 0) return;
    const chart = echarts.init(el);
    // Category axes draw bottom-up, so reverse to put the largest on top.
    const sorted = [...data].sort((a, b) => a.value - b.value);
    const option: EChartsCoreOption = {
      grid: { top: 4, right: 56, bottom: 4, left: 8, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        confine: true,
        valueFormatter: (value: number) => formatValue(value),
      },
      xAxis: { type: 'value', show: false },
      yAxis: {
        type: 'category',
        data: sorted.map((item) => item.label),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: 'var(--gray-6)' } },
        axisLabel: { color: 'var(--gray-11)', width: 200, overflow: 'truncate' },
      },
      series: [
        {
          type: 'bar',
          data: sorted.map((item) => item.value),
          itemStyle: { color: '#3b82f6', borderRadius: [0, 3, 3, 0] },
          label: {
            show: true,
            position: 'right',
            color: 'var(--gray-11)',
            formatter: (params: { value: number }) => formatValue(params.value),
          },
        },
      ],
    };
    chart.setOption(option);
    chart.on('click', (params) => clickRef.current?.(String(params.name)));
    const resize = () => chart.resize();
    window.addEventListener('resize', resize);
    return () => {
      window.removeEventListener('resize', resize);
      chart.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataKey]);

  return <div ref={containerRef} style={{ width: '100%', height: data.length * rowHeight + 8 }} />;
}
