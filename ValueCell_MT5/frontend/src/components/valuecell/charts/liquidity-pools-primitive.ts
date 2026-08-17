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

export interface LiquidityPoolItem {
  id: string;
  type: "BSL" | "SSL"; // Buy-Side Liquidity (Equal Highs / Tops) vs Sell-Side Liquidity (Equal Lows / Bottoms)
  price: number;
  startTime: number;   // unix seconds (origin pivot time)
  endTime: number;     // unix seconds (sweep time or current playhead)
  isSwept: boolean;    // true if price has pierced/swept the liquidity level
  label?: string;
}

class LiquidityPoolsPaneRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly source: LiquidityPoolsPrimitive) {}

  draw(target: {
    useBitmapCoordinateSpace: (
      cb: (scope: {
        context: CanvasRenderingContext2D;
        bitmapSize: { width: number; height: number };
        horizontalPixelRatio: number;
        verticalPixelRatio: number;
      }) => void
    ) => void;
  }): void {
    const chart = this.source.chart;
    if (!chart || !this.source.visible || this.source.pools.length === 0) return;

    const series = this.source.series;
    if (!series) return;

    const timeScale = chart.timeScale();
    const visibleRange = timeScale.getVisibleRange();
    if (!visibleRange) return;

    const visibleFrom = visibleRange.from as number;
    const visibleTo = visibleRange.to as number;

    const padding = 14 * 24 * 3600; // 14 days
    const visiblePools = this.source.pools.filter((pool) => {
      return (
        pool.startTime <= visibleTo + padding &&
        pool.endTime >= visibleFrom - padding
      );
    });

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const hpr = scope.horizontalPixelRatio;
      const vpr = scope.verticalPixelRatio;

      for (const pool of visiblePools) {
        const x1 = timeScale.timeToCoordinate(pool.startTime as UTCTimestamp);
        let x2 = timeScale.timeToCoordinate(pool.endTime as UTCTimestamp);
        const yRaw = series.priceToCoordinate(pool.price);

        if (x1 === null || yRaw === null) continue;

        let lx2: number;
        if (x2 !== null) {
          lx2 = x2 * hpr;
        } else {
          const lastTime = this.source.lastCandleTime;
          const lastX = lastTime ? timeScale.timeToCoordinate(lastTime as UTCTimestamp) : null;
          lx2 = lastX !== null ? (lastX + 90) * hpr : (x1 + 120) * hpr;
        }

        const lx1 = x1 * hpr;
        const ly = Math.round(yRaw * vpr) + 0.5;
        const isBsl = pool.type === "BSL";
        const isSwept = pool.isSwept;

        // Distinct Colors: Cyan/Ice Blue (#38bdf8) for BSL, Warm Coral/Orange (#fb923c) for SSL
        const strokeColor = isBsl
          ? isSwept ? "rgba(56, 189, 248, 0.35)" : "rgba(56, 189, 248, 0.90)"
          : isSwept ? "rgba(251, 146, 60, 0.35)" : "rgba(251, 146, 60, 0.90)";

        const badgeTextColor = isBsl
          ? isSwept ? "rgba(186, 230, 253, 0.7)" : "#7dd3fc"
          : isSwept ? "rgba(254, 215, 170, 0.7)" : "#fdba74";

        ctx.save();

        // 1. Draw Horizontal Liquidity Target Line
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = Math.max(1, (isSwept ? 1 : 1.5) * hpr);

        if (isSwept) {
          ctx.setLineDash([2 * hpr, 4 * hpr]); // subtle dotted when swept
        } else {
          ctx.setLineDash([6 * hpr, 3 * hpr]); // prominent dashed when active target
        }

        ctx.beginPath();
        ctx.moveTo(lx1, ly);
        ctx.lineTo(lx2, ly);
        ctx.stroke();

        // Origin marker (small dot on the pivot point)
        ctx.setLineDash([]);
        ctx.fillStyle = strokeColor;
        ctx.beginPath();
        ctx.arc(lx1, ly, 2.5 * hpr, 0, Math.PI * 2);
        ctx.fill();

        // 2. Draw Pill Badge at the Right Edge of the Pool Line
        const defaultLabel = `${isBsl ? "🎯 BSL" : "🎯 SSL"} [${pool.price.toFixed(2)}]${isSwept ? " (Swept)" : ""}`;
        const labelText = pool.label || defaultLabel;

        ctx.font = `600 ${Math.max(9, Math.round(9.5 * vpr))}px monospace`;
        const textWidth = ctx.measureText(labelText).width;
        const badgePaddingX = 5 * hpr;
        const badgeHeight = 15 * vpr;
        const badgeY = ly - badgeHeight / 2;
        const badgeX = Math.max(lx1, lx2 - textWidth - badgePaddingX * 2);

        // Badge Container
        ctx.fillStyle = "rgba(15, 23, 42, 0.92)";
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = 1 * hpr;
        ctx.setLineDash([]);

        ctx.beginPath();
        ctx.roundRect
          ? ctx.roundRect(badgeX, badgeY, textWidth + badgePaddingX * 2, badgeHeight, 3 * hpr)
          : ctx.rect(badgeX, badgeY, textWidth + badgePaddingX * 2, badgeHeight);
        ctx.fill();
        ctx.stroke();

        // Badge Text
        ctx.fillStyle = badgeTextColor;
        ctx.fillText(labelText, badgeX + badgePaddingX, badgeY + badgeHeight - 3.5 * vpr);

        ctx.restore();
      }
    });
  }
}

class LiquidityPoolsPaneView implements IPrimitivePaneView {
  private readonly _renderer: LiquidityPoolsPaneRenderer;

  constructor(source: LiquidityPoolsPrimitive) {
    this._renderer = new LiquidityPoolsPaneRenderer(source);
  }

  zOrder(): "bottom" | "normal" | "top" {
    return "normal"; // Render crisply over grid and behind tooltips
  }

  renderer(): IPrimitivePaneRenderer {
    return this._renderer;
  }
}

export class LiquidityPoolsPrimitive implements ISeriesPrimitive<Time> {
  chart: IChartApi | null = null;
  series: ISeriesApi<SeriesType> | null = null;
  visible: boolean = true;
  pools: LiquidityPoolItem[] = [];
  lastCandleTime: number | null = null;

  private requestUpdate?: () => void;
  private readonly _paneViews: readonly IPrimitivePaneView[];

  constructor() {
    this._paneViews = [new LiquidityPoolsPaneView(this)];
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

  paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews;
  }

  setPools(pools: LiquidityPoolItem[]): void {
    this.pools = pools;
    this.requestUpdate?.();
  }

  setVisible(visible: boolean): void {
    if (this.visible !== visible) {
      this.visible = visible;
      this.requestUpdate?.();
    }
  }

  setLastCandleTime(time: number | null): void {
    this.lastCandleTime = time;
    this.requestUpdate?.();
  }

  updateAllViews(): void {
    this.requestUpdate?.();
  }
}
