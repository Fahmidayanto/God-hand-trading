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

export interface SupplyDemandZoneItem {
  id: string;
  type: "SUPPLY" | "DEMAND";
  topPrice: number;
  bottomPrice: number;
  startTime: number; // unix seconds (origin candle)
  endTime: number;   // unix seconds (mitigation candle or playhead)
  isMitigated: boolean;
  label?: string;
}

class SupplyDemandPaneRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly source: SupplyDemandPrimitive) {}

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
    if (!chart || !this.source.visible || this.source.zones.length === 0) return;

    const series = this.source.series;
    if (!series) return;

    const timeScale = chart.timeScale();
    const visibleRange = timeScale.getVisibleRange();
    if (!visibleRange) return;

    const visibleFrom = visibleRange.from as number;
    const visibleTo = visibleRange.to as number;

    // Viewport padding: only render zones that overlap with visible time range
    const padding = 14 * 24 * 3600; // 14 days
    const visibleZones = this.source.zones.filter((zone) => {
      return (
        zone.startTime <= visibleTo + padding &&
        zone.endTime >= visibleFrom - padding
      );
    });

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const hpr = scope.horizontalPixelRatio;
      const vpr = scope.verticalPixelRatio;

      for (const zone of visibleZones) {
        const x1 = timeScale.timeToCoordinate(zone.startTime as UTCTimestamp);
        let x2 = timeScale.timeToCoordinate(zone.endTime as UTCTimestamp);

        const yTop = series.priceToCoordinate(zone.topPrice);
        const yBottom = series.priceToCoordinate(zone.bottomPrice);

        if (x1 === null || yTop === null || yBottom === null) continue;

        let lx2: number;
        if (x2 !== null) {
          lx2 = x2 * hpr;
        } else {
          const lastTime = this.source.lastCandleTime;
          const lastX = lastTime ? timeScale.timeToCoordinate(lastTime as UTCTimestamp) : null;
          lx2 = lastX !== null ? (lastX + 100) * hpr : (x1 + 140) * hpr;
        }

        const lx1 = x1 * hpr;
        const lyTop = Math.min(yTop, yBottom) * vpr;
        const lyBottom = Math.max(yTop, yBottom) * vpr;
        const zoneWidth = Math.max(8 * hpr, lx2 - lx1);
        const zoneHeight = Math.max(3 * vpr, lyBottom - lyTop);

        const isSupply = zone.type === "SUPPLY";
        const isMitigated = zone.isMitigated;

        // Theme colors: Purple/Indigo for Supply (Resistance), Golden Amber for Demand (Support)
        // Eliminates visual collision with Red (SL) and Green (TP)
        const fillColor = isSupply
          ? isMitigated
            ? "rgba(168, 85, 247, 0.05)"
            : "rgba(168, 85, 247, 0.16)"
          : isMitigated
            ? "rgba(245, 158, 11, 0.05)"
            : "rgba(245, 158, 11, 0.16)";

        const borderColor = isSupply
          ? isMitigated
            ? "rgba(168, 85, 247, 0.35)"
            : "rgba(168, 85, 247, 0.90)"
          : isMitigated
            ? "rgba(245, 158, 11, 0.35)"
            : "rgba(245, 158, 11, 0.90)";

        ctx.save();

        // 1. Draw Shaded Rectangle Box
        ctx.fillStyle = fillColor;
        ctx.fillRect(lx1, lyTop, zoneWidth, zoneHeight);

        // 2. Draw Top and Bottom Boundary Lines
        ctx.strokeStyle = borderColor;
        ctx.lineWidth = Math.max(1, (isMitigated ? 1 : 1.5) * hpr);

        if (isMitigated) {
          ctx.setLineDash([4 * hpr, 4 * hpr]);
        } else {
          ctx.setLineDash([]);
        }

        // Top line
        ctx.beginPath();
        ctx.moveTo(lx1, lyTop);
        ctx.lineTo(lx1 + zoneWidth, lyTop);
        ctx.stroke();

        // Bottom line
        ctx.beginPath();
        ctx.moveTo(lx1, lyBottom);
        ctx.lineTo(lx1 + zoneWidth, lyBottom);
        ctx.stroke();

        // Left origin cap
        ctx.beginPath();
        ctx.moveTo(lx1, lyTop);
        ctx.lineTo(lx1, lyBottom);
        ctx.stroke();

        // 3. Draw Pill Label Badge at the Right Edge of Zone
        const labelText = zone.label || `${isSupply ? "SUPPLY" : "DEMAND"} [${zone.bottomPrice.toFixed(1)} - ${zone.topPrice.toFixed(1)}]${isMitigated ? " (Mitigated)" : ""}`;
        ctx.font = `600 ${Math.max(9, Math.round(9.5 * vpr))}px monospace`;
        const textWidth = ctx.measureText(labelText).width;
        const badgePaddingX = 5 * hpr;
        const badgeHeight = 15 * vpr;
        const badgeY = lyTop - badgeHeight - 2 * vpr;
        const badgeX = Math.max(lx1, lx1 + zoneWidth - textWidth - badgePaddingX * 2);

        // Badge Background
        ctx.fillStyle = "rgba(15, 23, 42, 0.90)";
        ctx.strokeStyle = borderColor;
        ctx.lineWidth = 1 * hpr;
        ctx.setLineDash([]);

        ctx.beginPath();
        ctx.roundRect
          ? ctx.roundRect(badgeX, badgeY, textWidth + badgePaddingX * 2, badgeHeight, 3 * hpr)
          : ctx.rect(badgeX, badgeY, textWidth + badgePaddingX * 2, badgeHeight);
        ctx.fill();
        ctx.stroke();

        // Badge Text
        ctx.fillStyle = isSupply
          ? isMitigated ? "rgba(216, 180, 254, 0.7)" : "#d8b4fe"
          : isMitigated ? "rgba(253, 230, 138, 0.7)" : "#fde68a";
        ctx.fillText(labelText, badgeX + badgePaddingX, badgeY + badgeHeight - 3.5 * vpr);

        ctx.restore();
      }
    });
  }
}

class SupplyDemandPaneView implements IPrimitivePaneView {
  private readonly _renderer: SupplyDemandPaneRenderer;

  constructor(source: SupplyDemandPrimitive) {
    this._renderer = new SupplyDemandPaneRenderer(source);
  }

  zOrder(): "bottom" | "normal" | "top" {
    return "bottom"; // Render behind candles so bars remain crisp and readable
  }

  renderer(): IPrimitivePaneRenderer {
    return this._renderer;
  }
}

export class SupplyDemandPrimitive implements ISeriesPrimitive<Time> {
  chart: IChartApi | null = null;
  series: ISeriesApi<SeriesType> | null = null;
  visible: boolean = true;
  zones: SupplyDemandZoneItem[] = [];
  lastCandleTime: number | null = null;

  private requestUpdate?: () => void;
  private readonly _paneViews: readonly IPrimitivePaneView[];

  constructor() {
    this._paneViews = [new SupplyDemandPaneView(this)];
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

  setZones(zones: SupplyDemandZoneItem[]): void {
    this.zones = zones;
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
