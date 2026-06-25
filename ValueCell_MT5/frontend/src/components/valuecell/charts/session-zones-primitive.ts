import type {
  IChartApi,
  ISeriesApi,
  ISeriesPrimitive,
  ISeriesPrimitivePaneView,
  ISeriesPrimitivePaneRenderer,
  SeriesType,
  Time,
  UTCTimestamp,
} from "lightweight-charts";

export interface SessionZoneBox {
  /** unix seconds */
  start: number;
  /** unix seconds */
  end: number;
  /** session name, used to pick a color */
  session: string;
  /** whether the session is still running */
  open: boolean;
}

/**
 * Semi-transparent fill color per trading session.
 * Mirrors the session names exported by the MT5 EA (Dev_Bot_v11.cs).
 */
export function sessionColor(session: string): string {
  switch (session) {
    case "Sydney":
      return "rgba(99, 102, 241, 0.10)"; // indigo
    case "Sydney_Tokyo_Overlap":
      return "rgba(168, 85, 247, 0.10)"; // purple
    case "Asia":
      return "rgba(239, 68, 68, 0.10)"; // red
    case "Tokyo_London_Overlap":
      return "rgba(245, 158, 11, 0.10)"; // amber
    case "London":
      return "rgba(234, 179, 8, 0.12)"; // yellow
    case "London_NewYork_Overlap":
      return "rgba(16, 185, 129, 0.14)"; // emerald (key session)
    case "NewYork":
      return "rgba(59, 130, 246, 0.10)"; // blue
    default:
      return "rgba(148, 163, 184, 0.08)"; // slate / unknown
  }
}

/**
 * Short, readable label per session for on-chart annotation.
 */
export function sessionLabel(session: string): string {
  switch (session) {
    case "Sydney":
      return "Sydney";
    case "Sydney_Tokyo_Overlap":
      return "Sydney / Tokyo";
    case "Asia":
      return "Asia (Tokyo)";
    case "Tokyo_London_Overlap":
      return "Tokyo / London";
    case "London":
      return "London";
    case "London_NewYork_Overlap":
      return "London / NY";
    case "NewYork":
      return "New York";
    default:
      return session;
  }
}

/** Solid (label) color matching each session's band tint. */
export function sessionLabelColor(session: string): string {
  switch (session) {
    case "Sydney":
      return "rgba(129, 140, 248, 0.95)"; // indigo
    case "Sydney_Tokyo_Overlap":
      return "rgba(192, 132, 252, 0.95)"; // purple
    case "Asia":
      return "rgba(248, 113, 113, 0.95)"; // red
    case "Tokyo_London_Overlap":
      return "rgba(251, 191, 36, 0.95)"; // amber
    case "London":
      return "rgba(250, 204, 21, 0.95)"; // yellow
    case "London_NewYork_Overlap":
      return "rgba(52, 211, 153, 0.95)"; // emerald
    case "NewYork":
      return "rgba(96, 165, 250, 0.95)"; // blue
    default:
      return "rgba(203, 213, 225, 0.9)"; // slate
  }
}

class SessionZonesPaneRenderer implements ISeriesPrimitivePaneRenderer {
  constructor(
    private readonly source: SessionZonesPrimitive,
  ) {}

  draw(target: {
    useBitmapCoordinateSpace: (
      cb: (scope: {
        context: CanvasRenderingContext2D;
        bitmapSize: { width: number; height: number };
        horizontalPixelRatio: number;
        verticalPixelRatio: number;
      }) => void,
    ) => void;
  }): void {
    const chart = this.source.chart;
    if (!chart || !this.source.visible || this.source.boxes.length === 0) return;

    const timeScale = chart.timeScale();
    
    // OPTIMIZATION: Get visible time range and only render boxes that overlap
    const visibleRange = timeScale.getVisibleRange();
    if (!visibleRange) return;
    
    const visibleFrom = (visibleRange.from as number);
    const visibleTo = (visibleRange.to as number);
    
    // Filter boxes to only those that overlap with visible range
    const visibleBoxes = this.source.boxes.filter(box => {
      // Box is visible if it overlaps with [visibleFrom, visibleTo]
      return box.end >= visibleFrom && box.start <= visibleTo;
    });
    
    console.log('🎨 [SESSION RENDER] Drawing session zones:', {
      totalBoxes: this.source.boxes.length,
      visibleBoxes: visibleBoxes.length,
      visibleRange: { from: visibleFrom, to: visibleTo },
    });

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const hpr = scope.horizontalPixelRatio;
      const vpr = scope.verticalPixelRatio;
      const height = scope.bitmapSize.height;
      const width = scope.bitmapSize.width;

      for (const box of visibleBoxes) {
        // Snap band edges to real candles so market gaps (e.g. gold's midnight
        // break) don't push edges to the wrong place when a boundary has no bar.
        let startTime = box.start;
        let endTime = box.end;
        if (this.source.candleTimes.length > 0) {
          const s = this.source.firstAtOrAfter(box.start);
          const e = this.source.lastAtOrBefore(box.end);
          // Whole band falls inside a gap / outside loaded candles -> skip.
          if (s === null || e === null || s > e) continue;
          startTime = s;
          endTime = e;
        }

        const x1 = timeScale.timeToCoordinate(startTime as UTCTimestamp);
        const x2 = timeScale.timeToCoordinate(endTime as UTCTimestamp);
        if (x1 === null && x2 === null) continue;

        // Clamp edges to the visible canvas so partially-offscreen boxes still render.
        let left = (x1 ?? 0) * hpr;
        let right = (x2 ?? width / hpr) * hpr;
        if (left > right) [left, right] = [right, left];
        left = Math.max(0, Math.min(width, left));
        right = Math.max(0, Math.min(width, right));
        if (right - left < 0.5) continue;

        ctx.fillStyle = sessionColor(box.session);
        ctx.fillRect(left, 0, right - left, height);

        // Vertical divider lines at the session boundaries (start & end).
        const drawDivider = (x: number, isOpenStart: boolean) => {
          ctx.save();
          ctx.beginPath();
          ctx.setLineDash([4 * vpr, 4 * vpr]);
          ctx.lineWidth = Math.max(1, hpr);
          ctx.strokeStyle = isOpenStart
            ? "rgba(16, 185, 129, 0.65)"
            : "rgba(148, 163, 184, 0.45)";
          const px = Math.round(x) + 0.5;
          ctx.moveTo(px, 0);
          ctx.lineTo(px, height);
          ctx.stroke();
          ctx.restore();
        };

        if (x1 !== null) drawDivider(left, box.open);
        if (x2 !== null) drawDivider(right, false);

        // Session name label. Horizontal if the band is wide enough,
        // otherwise rotated vertically so even narrow bands (e.g. Sydney) show.
        const bandWidth = right - left;
        let label = sessionLabel(box.session);
        if (box.open) label += " •";

        const fontPx = 11 * vpr;
        const padX = 6 * hpr;
        const padY = 6 * vpr;

        ctx.save();
        ctx.font = `600 ${fontPx}px -apple-system, system-ui, sans-serif`;
        ctx.fillStyle = sessionLabelColor(box.session);

        const horizontalNeeded = ctx.measureText(label).width + padX * 2;

        if (bandWidth >= horizontalNeeded) {
          // Horizontal label at the top-left of the band.
          ctx.textBaseline = "top";
          ctx.textAlign = "left";
          ctx.fillText(label, left + padX, padY);
        } else if (bandWidth >= fontPx + 2 * hpr) {
          // Vertical (rotated) label down the band, truncated to the height.
          const maxTextHeight = height - padY * 2;
          if (ctx.measureText(label).width > maxTextHeight) {
            while (
              label.length > 1 &&
              ctx.measureText(`${label}…`).width > maxTextHeight
            ) {
              label = label.slice(0, -1);
            }
            label += "…";
          }
          ctx.translate(left + bandWidth / 2, padY);
          ctx.rotate(Math.PI / 2);
          ctx.textBaseline = "middle";
          ctx.textAlign = "left";
          ctx.fillText(label, 0, 0);
        }
        ctx.restore();
      }
    });
  }
}

class SessionZonesPaneView implements ISeriesPrimitivePaneView {
  private readonly _renderer: SessionZonesPaneRenderer;

  constructor(source: SessionZonesPrimitive) {
    this._renderer = new SessionZonesPaneRenderer(source);
  }

  // Draw beneath the candlesticks.
  zOrder(): "bottom" | "normal" | "top" {
    return "bottom";
  }

  renderer(): ISeriesPrimitivePaneRenderer {
    return this._renderer;
  }
}

/**
 * Series primitive that paints full-height shadow bands for trading sessions.
 * Attach to a candlestick series with `series.attachPrimitive(primitive)`.
 */
export class SessionZonesPrimitive implements ISeriesPrimitive<Time> {
  chart: IChartApi | null = null;
  series: ISeriesApi<SeriesType> | null = null;
  boxes: SessionZoneBox[] = [];
  visible = true;
  /** Sorted ascending list of candle times (unix seconds) currently on the chart. */
  candleTimes: number[] = [];

  private requestUpdate?: () => void;
  private readonly _paneViews: SessionZonesPaneView[];

  constructor() {
    this._paneViews = [new SessionZonesPaneView(this)];
  }

  attached(param: {
    chart: IChartApi;
    series: ISeriesApi<SeriesType>;
    requestUpdate: () => void;
  }): void {
    this.chart = param.chart;
    this.series = param.series;
    this.requestUpdate = param.requestUpdate;
  }

  detached(): void {
    this.chart = null;
    this.series = null;
    this.requestUpdate = undefined;
  }

  setBoxes(boxes: SessionZoneBox[]): void {
    this.boxes = boxes;
    this.requestUpdate?.();
  }

  setVisible(visible: boolean): void {
    this.visible = visible;
    this.requestUpdate?.();
  }

  /** Provide the candle times so band edges can snap to real bars (handles market gaps). */
  setCandleTimes(times: number[]): void {
    this.candleTimes = [...times].sort((a, b) => a - b);
    this.requestUpdate?.();
  }

  /** First candle time >= t, or null if none. */
  firstAtOrAfter(t: number): number | null {
    const arr = this.candleTimes;
    if (arr.length === 0) return null;
    let lo = 0;
    let hi = arr.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (arr[mid] < t) lo = mid + 1;
      else hi = mid;
    }
    return lo < arr.length ? arr[lo] : null;
  }

  /** Last candle time <= t, or null if none. */
  lastAtOrBefore(t: number): number | null {
    const arr = this.candleTimes;
    if (arr.length === 0) return null;
    let lo = 0;
    let hi = arr.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (arr[mid] <= t) lo = mid + 1;
      else hi = mid;
    }
    return lo > 0 ? arr[lo - 1] : null;
  }

  updateAllViews(): void {
    // Coordinates are recomputed on every draw, nothing cached to refresh here.
  }

  paneViews(): readonly ISeriesPrimitivePaneView[] {
    return this._paneViews;
  }
}
