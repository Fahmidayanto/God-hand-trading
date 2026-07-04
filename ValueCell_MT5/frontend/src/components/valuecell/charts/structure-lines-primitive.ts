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

export interface StructureLineItem {
  price: number;
  startTime: number; // unix seconds
  endTime: number; // unix seconds
  color: string;
  lineWidth: number;
  lineStyle: number; // 0 = Solid, 1 = Dashed, 2 = Dotted (matches LineStyle enum)
  label: string;
  isResistance: boolean;
}

class StructureLinesPaneRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly source: StructureLinesPrimitive) {}

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
    if (!chart || !this.source.visible || this.source.lines.length === 0) return;

    const series = this.source.series;
    if (!series) return;

    const timeScale = chart.timeScale();
    const visibleRange = timeScale.getVisibleRange();
    if (!visibleRange) return;

    const visibleFrom = visibleRange.from as number;
    const visibleTo = visibleRange.to as number;

    // Filter lines: only draw if they overlap with the visible range plus padding
    const padding = 5 * 24 * 3600; // 5 days padding
    const visibleLines = this.source.lines.filter((line) => {
      return (
        line.startTime <= visibleTo + padding &&
        line.endTime >= visibleFrom - padding
      );
    });

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const hpr = scope.horizontalPixelRatio;
      const vpr = scope.verticalPixelRatio;

      for (const line of visibleLines) {
        const x1 = timeScale.timeToCoordinate(line.startTime as UTCTimestamp);
        const x2 = timeScale.timeToCoordinate(line.endTime as UTCTimestamp);
        const yRaw = series.priceToCoordinate(line.price);

        if (x1 === null || x2 === null || yRaw === null) continue;

        // Convert to physical bitmap coordinates
        const lx1 = x1 * hpr;
        const lx2 = x2 * hpr;
        const ly = Math.round(yRaw * vpr) + 0.5; // Offset 0.5 for sharp 1px lines

        // 1. Draw horizontal line segment
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(lx1, ly);
        ctx.lineTo(lx2, ly);
        ctx.strokeStyle = line.color;
        ctx.lineWidth = line.lineWidth * hpr;

        if (line.lineStyle === 1) {
          // Dashed (1 = LineStyle.Dashed)
          ctx.setLineDash([4 * hpr, 4 * hpr]);
        } else if (line.lineStyle === 2) {
          // Dotted (2 = LineStyle.Dotted)
          ctx.setLineDash([1 * hpr, 3 * hpr]);
        } else {
          ctx.setLineDash([]);
        }
        ctx.stroke();
        ctx.restore();

        // 2. Draw text label at midpoint of segment
        if (line.label) {
          const midX = (lx1 + lx2) / 2;

          ctx.save();
          ctx.font = `600 ${Math.round(9 * vpr)}px monospace`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";

          const textWidth = ctx.measureText(line.label).width;
          const textHeight = 10 * vpr;
          // Offset above for resistance, below for support
          const offsetY = line.isResistance ? -8 * vpr : 8 * vpr;
          const labelY = ly + offsetY;

          // Draw dark background rectangle
          ctx.fillStyle = "rgba(17, 24, 39, 0.85)";
          ctx.fillRect(
            midX - textWidth / 2 - 4 * hpr,
            labelY - textHeight / 2 - 2 * vpr,
            textWidth + 8 * hpr,
            textHeight + 4 * vpr
          );

          // Draw rectangle borders
          ctx.strokeStyle = line.color;
          ctx.lineWidth = 1 * hpr;
          ctx.strokeRect(
            midX - textWidth / 2 - 4 * hpr,
            labelY - textHeight / 2 - 2 * vpr,
            textWidth + 8 * hpr,
            textHeight + 4 * vpr
          );

          // Draw the text label
          ctx.fillStyle = line.color;
          ctx.fillText(line.label, midX, labelY);
          ctx.restore();
        }
      }
    });
  }
}

class StructureLinesPaneView implements IPrimitivePaneView {
  private readonly _renderer: StructureLinesPaneRenderer;

  constructor(private readonly source: StructureLinesPrimitive) {
    this._renderer = new StructureLinesPaneRenderer(source);
  }

  renderer(): IPrimitivePaneRenderer {
    return this._renderer;
  }
}

/**
 * Custom series primitive that renders structure lines (BoS/CHoCH/HH/LL) and labels
 * directly onto the chart's canvas. Highly optimized to handle 1000+ lines.
 */
export class StructureLinesPrimitive implements ISeriesPrimitive<Time> {
  chart: IChartApi | null = null;
  series: ISeriesApi<SeriesType> | null = null;
  lines: StructureLineItem[] = [];
  visible = true;

  private requestUpdate?: () => void;
  private readonly _paneViews: StructureLinesPaneView[];

  constructor() {
    this._paneViews = [new StructureLinesPaneView(this)];
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

  setLines(lines: StructureLineItem[]): void {
    this.lines = lines;
    this.requestUpdate?.();
  }

  setVisible(visible: boolean): void {
    this.visible = visible;
    this.requestUpdate?.();
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews;
  }
}
