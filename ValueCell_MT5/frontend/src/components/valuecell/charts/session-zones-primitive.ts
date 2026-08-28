import type {
  IChartApi,
  ISeriesApi,
  ISeriesPrimitive,
  IPrimitivePaneView,
  IPrimitivePaneRenderer,
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
 * Soft, clean semi-transparent fill color per trading session (Format 01).
 * Calibrated for maximum candlestick contrast on white/light chart canvas.
 */
export function sessionColor(session: string): string {
  switch (session) {
    case "Sydney":
      return "rgba(99, 102, 241, 0.035)"; // soft indigo
    case "Sydney_Tokyo_Overlap":
      return "rgba(168, 85, 247, 0.035)"; // soft purple
    case "Asia":
      return "rgba(236, 72, 153, 0.035)"; // soft pink/fuchsia
    case "Tokyo_London_Overlap":
      return "rgba(245, 158, 11, 0.04)"; // soft amber
    case "London":
      return "rgba(234, 179, 8, 0.045)"; // soft gold
    case "London_NewYork_Overlap":
      return "rgba(16, 185, 129, 0.06)"; // soft emerald (Prime session)
    case "NewYork":
      return "rgba(59, 130, 246, 0.04)"; // soft blue
    default:
      return "rgba(148, 163, 184, 0.03)"; // slate
  }
}

/** Solid vibrant theme color per session for pill badges and boundaries. */
export function sessionThemeColor(session: string): string {
  switch (session) {
    case "Sydney":
      return "#6366f1"; // indigo
    case "Sydney_Tokyo_Overlap":
      return "#a855f7"; // purple
    case "Asia":
      return "#ec4899"; // fuchsia
    case "Tokyo_London_Overlap":
      return "#f59e0b"; // amber
    case "London":
      return "#eab308"; // gold
    case "London_NewYork_Overlap":
      return "#10b981"; // emerald
    case "NewYork":
      return "#3b82f6"; // blue
    default:
      return "#64748b"; // slate
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
  return sessionThemeColor(session);
}

class SessionZonesPaneRenderer implements IPrimitivePaneRenderer {
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
        const bandWidth = right - left;
        if (bandWidth < 0.5) continue;

        const themeColor = sessionThemeColor(box.session);

        // 1. Fill clean translucent background band
        ctx.fillStyle = sessionColor(box.session);
        ctx.fillRect(left, 0, bandWidth, height);

        // 2. Vertical dashed divider line with vivid session theme color
        const drawDivider = (x: number, isOpenStart: boolean) => {
          ctx.save();
          ctx.beginPath();
          ctx.setLineDash([5 * vpr, 3.5 * vpr]);
          ctx.lineWidth = Math.max(1.5, 1.5 * hpr);
          ctx.strokeStyle = isOpenStart ? "#10b981" : themeColor;
          ctx.globalAlpha = isOpenStart ? 0.95 : 0.8;
          const px = Math.round(x) + 0.5;
          ctx.moveTo(px, 0);
          ctx.lineTo(px, height);
          ctx.stroke();
          ctx.restore();
        };

        if (x1 !== null) drawDivider(left, box.open);
        if (x2 !== null) drawDivider(right, false);

        // 3. Format 01: Top Header Pill Badge (Horizontal if wide, Vertical if narrow - strictly within boundary)
        let label = sessionLabel(box.session);
        if (box.open) label += " •";

        const fontPx = Math.round(10 * vpr);
        ctx.save();
        ctx.font = `700 ${fontPx}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;

        const textMetrics = ctx.measureText(label);
        const textW = textMetrics.width;
        const padX = 6 * hpr;
        const padY = 3.5 * vpr;
        const dotR = 2.5 * vpr;
        const pillW = textW + dotR * 2 + padX * 2 + 4 * hpr;
        const pillH = fontPx + padY * 2;
        const topY = 6 * vpr;
        const pillX = left + 4 * hpr;

        if (bandWidth >= pillW + 6 * hpr) {
          // A. Horizontal Pill Badge (when band is wide enough to fit without overflowing boundary)
          const radius = 4 * vpr;
          ctx.beginPath();
          ctx.roundRect(pillX, topY, pillW, pillH, radius);
          ctx.fillStyle = "#ffffff";
          ctx.fill();
          ctx.strokeStyle = themeColor;
          ctx.lineWidth = 1 * hpr;
          ctx.stroke();

          // Draw solid color dot
          ctx.beginPath();
          ctx.arc(pillX + padX + dotR, topY + pillH / 2, dotR, 0, Math.PI * 2);
          ctx.fillStyle = themeColor;
          ctx.fill();

          // Draw text label
          ctx.fillStyle = themeColor;
          ctx.textBaseline = "middle";
          ctx.textAlign = "left";
          ctx.fillText(label, pillX + padX + dotR * 2 + 3.5 * hpr, topY + pillH / 2 + 0.5 * vpr);
        } else if (bandWidth >= 12 * hpr) {
          // B. Vertical Pill Badge (strictly contained within narrow session boundary - ZERO overlap)
          const centerX = left + bandWidth / 2;
          const vertTopY = 6 * vpr;
          const vertPillH = textW + dotR * 2 + padX * 2 + 4 * hpr;
          const vertPillW = Math.min(bandWidth - 2 * hpr, pillH);

          ctx.save();
          ctx.translate(centerX, vertTopY);
          ctx.rotate(Math.PI / 2);

          const radius = 4 * vpr;
          ctx.beginPath();
          ctx.roundRect(0, -vertPillW / 2, vertPillH, vertPillW, radius);
          ctx.fillStyle = "#ffffff";
          ctx.fill();
          ctx.strokeStyle = themeColor;
          ctx.lineWidth = 1 * hpr;
          ctx.stroke();

          // Draw solid color dot
          ctx.beginPath();
          ctx.arc(padX + dotR, 0, dotR, 0, Math.PI * 2);
          ctx.fillStyle = themeColor;
          ctx.fill();

          // Draw text label (Full name, horizontal along rotated vertical axis)
          ctx.fillStyle = themeColor;
          ctx.textBaseline = "middle";
          ctx.textAlign = "left";
          ctx.fillText(label, padX + dotR * 2 + 3.5 * hpr, 0.5 * vpr);

          ctx.restore();
        }

        ctx.restore();
      }
    });
  }
}

class SessionZonesPaneView implements IPrimitivePaneView {
  private readonly _renderer: SessionZonesPaneRenderer;

  constructor(source: SessionZonesPrimitive) {
    this._renderer = new SessionZonesPaneRenderer(source);
  }

  // Draw beneath the candlesticks.
  zOrder(): "bottom" | "normal" | "top" {
    return "bottom";
  }

  renderer(): IPrimitivePaneRenderer {
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

  /** Provide the candle times so band edges can snap to real bars (handles market gaps).
   *  Data is already pre-sorted from API — skip redundant sort on every jump. */
  setCandleTimes(times: number[]): void {
    this.candleTimes = times;
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

  paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews;
  }
}
