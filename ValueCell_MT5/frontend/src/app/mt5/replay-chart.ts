import type { IChartApi } from "lightweight-charts";

type ReplayChartApi = Pick<IChartApi, "priceScale" | "timeScale">;

export function followReplayPlayhead(chart: any): void {
  chart.priceScale?.("right")?.applyOptions?.({ autoScale: true });
  const ts = chart.timeScale?.();
  if (ts) {
    ts.applyOptions?.({
      rightOffset: 18,
      fixLeftEdge: false,
      fixRightEdge: false,
    });
    if (typeof ts.scrollToPosition === "function") {
      ts.scrollToPosition(0, false);
    } else if (typeof ts.scrollToRealTime === "function") {
      ts.scrollToRealTime();
    }
  }
}
