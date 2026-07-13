import type { IChartApi } from "lightweight-charts";

type ReplayChartApi = Pick<IChartApi, "priceScale" | "timeScale">;

export function followReplayPlayhead(chart: ReplayChartApi): void {
  chart.priceScale("right").applyOptions({ autoScale: true });
  chart.timeScale().scrollToRealTime();
}
