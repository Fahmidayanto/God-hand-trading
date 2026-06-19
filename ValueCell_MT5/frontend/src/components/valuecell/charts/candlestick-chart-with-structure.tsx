/**
 * CandlestickChartWithStructure
 * 
 * Displays candlestick chart with market structure overlay (BoS, CHoCH, HH, LL).
 * 
 * FIX APPLIED: Horizontal lines (BoS, CHoCH, LL, HH) now start from the exact candle
 * where the structure event occurred, rather than from several candles ahead.
 * 
 * The fix uses "closest timestamp matching" instead of exact timestamp matching,
 * which handles cases where CSV timestamps don't exactly match candle timestamps.
 * 
 * Lines are drawn from the structure candle (start point) to the end of chart (end point).
 */

import {
  BarChart,
  CandlestickChart as ECandlestickChart,
  LineChart,
  ScatterChart,
} from "echarts/charts";
import {
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
} from "echarts/components";
import type { ECharts } from "echarts/core";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts/types/dist/shared";
import { useEffect, useMemo, useRef } from "react";
import { useChartResize } from "@/hooks/use-chart-resize";
import { TIME_FORMATS, TimeUtils } from "@/lib/time";
import { cn } from "@/lib/utils";
import { useStockColors } from "@/store/settings-store";
import type { MarketStructureLines } from "@/api/mt5_agents";

// Register ECharts components
echarts.use([
  BarChart,
  ECandlestickChart,
  LineChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  AxisPointerComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkPointComponent,
  CanvasRenderer,
]);

export interface CandlestickData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface CandlestickChartWithStructureProps {
  data: CandlestickData[];
  structureLines?: MarketStructureLines;
  width?: number | string;
  height?: number | string;
  className?: string;
  loading?: boolean;
  showVolume?: boolean;
  showStructure?: boolean;
  dateFormat?: string;
}

function CandlestickChartWithStructure({
  data,
  structureLines,
  width = "100%",
  height = 500,
  className,
  loading,
  showVolume = true,
  showStructure = true,
  dateFormat = TIME_FORMATS.DATETIME_SHORT,
}: CandlestickChartWithStructureProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ECharts | null>(null);
  const stockColors = useStockColors();

  const option: EChartsOption = useMemo(() => {
    if (!data || data.length === 0) return {};

    const dates = data.map((item) =>
      TimeUtils.formatUTC(item.time, dateFormat),
    );
    const ohlcData = data.map((item) => [
      item.open,
      item.close,
      item.low,
      item.high,
    ]);
    const volumes = data.map((item, index) => [
      index,
      item.volume,
      item.close >= item.open ? 1 : -1,
    ]);

    const mainGridHeight = showVolume ? "50%" : "75%";
    const volumeGridTop = showVolume ? "63%" : undefined;

    // Main candlestick series
    const series: EChartsOption["series"] = [
      {
        name: "K-Line",
        type: "candlestick",
        data: ohlcData,
        clip: true,
        itemStyle: {
          color: stockColors.positive,
          color0: stockColors.negative,
          borderColor: stockColors.positive,
          borderColor0: stockColors.negative,
        },
      },
    ];

    // Volume series
    if (showVolume) {
      series.push({
        name: "Volume",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: (params) => {
            const value = params.value as [number, number, number];
            return value[2] === 1 ? stockColors.positive : stockColors.negative;
          },
        },
      });
    }

    // Add market structure overlay
    if (showStructure && structureLines) {
      // Helper function to find closest candle index by timestamp
      // This fixes the issue where LL/HH lines don't start from the exact candle
      const findClosestCandleIndex = (targetTimestamp: number): number | undefined => {
        if (data.length === 0) return undefined;
        
        let closestIndex = 0;
        let minDiff = Math.abs(new Date(data[0].time).getTime() - targetTimestamp);
        
        for (let i = 1; i < data.length; i++) {
          const candleTimestamp = new Date(data[i].time).getTime();
          const diff = Math.abs(candleTimestamp - targetTimestamp);
          
          // If we find exact match or within 1 minute (60000ms), use it
          if (diff === 0 || diff < 60000) {
            return i;
          }
          
          // If this candle is closer than previous best, update
          if (diff < minDiff) {
            minDiff = diff;
            closestIndex = i;
          }
          
          // If we've passed the target time, return the closest so far
          if (candleTimestamp > targetTimestamp && i > 0) {
            // Check if previous candle was closer
            const prevDiff = Math.abs(new Date(data[i-1].time).getTime() - targetTimestamp);
            return prevDiff < diff ? i - 1 : i;
          }
        }
        
        // Return closest index found (within reasonable range - 1 hour)
        return minDiff < 3600000 ? closestIndex : undefined;
      };

      const markLineData: any[] = [];
      const markPointData: any[] = [];

      // BoS horizontal lines (red/green solid lines)
      // Draw line from the BoS candle to the end of visible chart
      structureLines.bos_lines?.forEach((bos) => {
        const index = findClosestCandleIndex(bos.timestamp);
        if (index !== undefined) {
          markLineData.push([
            {
              // Start point: BoS candle
              coord: [index, bos.price],
              name: `BoS ${bos.price.toFixed(2)}`,
              lineStyle: {
                color: bos.direction === 'BULLISH' ? '#10b981' : '#ef4444',
                width: 2,
                type: 'solid',
              },
            },
            {
              // End point: last candle in data
              coord: [data.length - 1, bos.price],
              label: {
                show: true,
                position: 'end',
                formatter: `BoS {b|${bos.price.toFixed(2)}}`,
                rich: {
                  b: {
                    fontWeight: 'bold',
                    fontSize: 11,
                    padding: [2, 4],
                    backgroundColor: bos.direction === 'BULLISH' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                  },
                },
              },
            },
          ]);
        }
      });

      // CHoCH horizontal lines (purple dashed lines)
      // Draw line from the CHoCH candle to the end of visible chart
      structureLines.choch_lines?.forEach((choch) => {
        const index = findClosestCandleIndex(choch.timestamp);
        if (index !== undefined) {
          markLineData.push([
            {
              // Start point: CHoCH candle
              coord: [index, choch.price],
              name: `CHoCH ${choch.price.toFixed(2)}`,
              lineStyle: {
                color: '#a855f7',
                width: 2,
                type: 'dashed',
              },
            },
            {
              // End point: last candle in data
              coord: [data.length - 1, choch.price],
              label: {
                show: true,
                position: 'end',
                formatter: `CHoCH {b|${choch.price.toFixed(2)}}`,
                rich: {
                  b: {
                    fontWeight: 'bold',
                    fontSize: 11,
                    padding: [2, 4],
                    backgroundColor: 'rgba(168, 85, 247, 0.2)',
                  },
                },
              },
            },
          ]);
        }
      });

      // HH markers (green triangle up)
      structureLines.hh_points?.forEach((hh) => {
        const index = findClosestCandleIndex(hh.timestamp);
        if (index !== undefined) {
          markPointData.push({
            name: 'HH',
            coord: [index, hh.price],
            value: 'HH',
            symbol: 'triangle',
            symbolSize: 12,
            itemStyle: {
              color: '#10b981',
            },
            label: {
              show: true,
              position: 'top',
              formatter: 'HH',
              fontSize: 10,
              fontWeight: 'bold',
              color: '#10b981',
            },
          });
        }
      });

      // LL markers (red triangle down)
      structureLines.ll_points?.forEach((ll) => {
        const index = findClosestCandleIndex(ll.timestamp);
        if (index !== undefined) {
          markPointData.push({
            name: 'LL',
            coord: [index, ll.price],
            value: 'LL',
            symbol: 'triangle',
            symbolRotate: 180,
            symbolSize: 12,
            itemStyle: {
              color: '#ef4444',
            },
            label: {
              show: true,
              position: 'bottom',
              formatter: 'LL',
              fontSize: 10,
              fontWeight: 'bold',
              color: '#ef4444',
            },
          });
        }
      });

      // Add markLine and markPoint to candlestick series
      if (series[0] && series[0].type === 'candlestick') {
        (series[0] as any).markLine = {
          silent: false,
          symbol: 'none',
          data: markLineData,
          animation: false,
        };
        (series[0] as any).markPoint = {
          silent: false,
          data: markPointData,
          animation: false,
        };
      }
    }

    const grids: EChartsOption["grid"] = [
      {
        left: "4%",
        right: "4%",
        top: "3%",
        height: mainGridHeight,
        containLabel: true,
      },
    ];

    const xAxes: EChartsOption["xAxis"] = [
      {
        type: "category" as const,
        data: dates,
        boundaryGap: true,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: "dataMin",
        max: "dataMax",
        axisPointer: { z: 100 },
      },
    ];

    const yAxes: EChartsOption["yAxis"] = [
      {
        scale: true,
        splitArea: { show: true },
      },
    ];

    if (showVolume) {
      grids.push({
        left: "8%",
        right: "6%",
        top: volumeGridTop,
        height: "16%",
        containLabel: true,
      });

      xAxes.push({
        type: "category" as const,
        gridIndex: 1,
        data: dates,
        boundaryGap: true,
        axisLine: { onZero: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        min: "dataMin",
        max: "dataMax",
      });

      yAxes.push({
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
      });
    }

    return {
      animation: false,
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
        borderWidth: 1,
        borderColor: "#ccc",
        padding: 10,
        textStyle: { color: "#000" },
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return '';
          
          const dataIndex = params[0].dataIndex;
          const item = data[dataIndex];
          if (!item) return '';

          let html = `<div style="font-weight: 600; margin-bottom: 8px;">${TimeUtils.formatUTC(item.time, dateFormat)}</div>`;
          html += `<div>Open: <span style="float: right; margin-left: 20px; font-weight: 600;">${item.open.toFixed(2)}</span></div>`;
          html += `<div>High: <span style="float: right; margin-left: 20px; font-weight: 600;">${item.high.toFixed(2)}</span></div>`;
          html += `<div>Low: <span style="float: right; margin-left: 20px; font-weight: 600;">${item.low.toFixed(2)}</span></div>`;
          html += `<div>Close: <span style="float: right; margin-left: 20px; font-weight: 600;">${item.close.toFixed(2)}</span></div>`;
          if (showVolume) {
            html += `<div>Volume: <span style="float: right; margin-left: 20px; font-weight: 600;">${item.volume.toLocaleString()}</span></div>`;
          }
          
          return html;
        },
      },
      axisPointer: {
        link: [{ xAxisIndex: "all" }],
        label: { backgroundColor: "#777" },
      },
      grid: grids,
      xAxis: xAxes,
      yAxis: yAxes,
      dataZoom: [
        {
          type: "inside",
          xAxisIndex: showVolume ? [0, 1] : [0],
        },
        {
          show: true,
          xAxisIndex: showVolume ? [0, 1] : [0],
          type: "slider",
          top: "85%",
        },
      ],
      series,
    };
  }, [data, structureLines, stockColors, showVolume, showStructure, dateFormat]);

  useChartResize(chartInstance);

  useEffect(() => {
    if (!chartRef.current) return;

    chartInstance.current = echarts.init(chartRef.current);
    chartInstance.current.setOption(option);

    return () => {
      chartInstance.current?.dispose();
    };
  }, [option]);

  useEffect(() => {
    if (chartInstance.current) {
      chartInstance.current.setOption(option);
    }
  }, [option]);

  useEffect(() => {
    if (chartInstance.current) {
      if (loading) {
        chartInstance.current.showLoading();
      } else {
        chartInstance.current.hideLoading();
      }
    }
  }, [loading]);

  return (
    <div
      ref={chartRef}
      className={cn("w-fit", className)}
      style={{ width, height }}
    />
  );
}

export default CandlestickChartWithStructure;
