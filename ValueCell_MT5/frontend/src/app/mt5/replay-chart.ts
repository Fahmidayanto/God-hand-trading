import type { IChartApi } from "lightweight-charts";

type ReplayChartApi = Pick<IChartApi, "priceScale" | "timeScale">;

export function followReplayPlayhead(chart: ReplayChartApi): void {
  chart.priceScale("right").applyOptions({ autoScale: true });
  chart.timeScale().applyOptions({
    rightOffset: 18,
    fixLeftEdge: false,
    fixRightEdge: false,
  });
  chart.timeScale().scrollToPosition(0, false);
}
