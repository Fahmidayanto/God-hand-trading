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

export interface TradeOverlayEntry {
  type: string;
  entry_price: number;
  sl: number | null;
  tp: number | null;
  profit: number;
  entry_time_ts: number;
  exit_time_ts: number | null;
}

const GREEN_BG = "rgba(34, 197, 94, 0.15)";
const RED_BG = "rgba(239, 68, 68, 0.15)";

class TradesPaneRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly source: TradesOverlayPrimitive) {}

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
    const series = this.source.series;
    if (!chart || !series || !this.source.visible || this.source.trades.length === 0) return;

    const timeScale = chart.timeScale();
    const visibleRange = timeScale.getVisibleRange();
    if (!visibleRange) return;

    const visibleFrom = visibleRange.from as number;
    const visibleTo = visibleRange.to as number;

    const visibleTrades = this.source.trades.filter((t) => {
      return t.sl !== null && t.tp !== null;
    });
    
    // Debug: Check 2026 trades
    const trades2026 = visibleTrades.filter(t => new Date(t.entry_time_ts * 1000).getFullYear() === 2026);
    console.log('[TradesPrimitive] draw:', { 
      totalTrades: this.source.trades.length, 
      visibleTrades: visibleTrades.length,
      trades2026: trades2026.length,
      visibleRange: { from: visibleFrom, to: visibleTo, fromDate: new Date(visibleFrom * 1000).toISOString(), toDate: new Date(visibleTo * 1000).toISOString() }
    });
    
    if (trades2026.length > 0) {
      console.log('[TradesPrimitive] Sample 2026 trade:', {
        entry_time: new Date(trades2026[0].entry_time_ts * 1000).toISOString(),
        exit_time: trades2026[0].exit_time_ts ? new Date(trades2026[0].exit_time_ts * 1000).toISOString() : null,
        entry_price: trades2026[0].entry_price,
        sl: trades2026[0].sl,
        tp: trades2026[0].tp,
      });
    }

    if (visibleTrades.length === 0) return;

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const hpr = scope.horizontalPixelRatio;
      const vpr = scope.verticalPixelRatio;
      const width = scope.bitmapSize.width;
      const height = scope.bitmapSize.height;

      for (const trade of visibleTrades) {
        const exitTs = trade.exit_time_ts ?? this.source.lastCandleTime;
        if (exitTs === null) continue;

        const is2026Trade = new Date(trade.entry_time_ts * 1000).getFullYear() === 2026;
        
        const x1 = timeScale.timeToCoordinate(trade.entry_time_ts as UTCTimestamp);
        let x2 = timeScale.timeToCoordinate(exitTs as UTCTimestamp);
        
        // FALLBACK: If exit coordinate is null (exit time not in chart data),
        // extrapolate x2 coordinate based on entry coordinate and time difference
        if (x2 === null && x1 !== null) {
          // Get bar spacing from time scale options
          const tsOptions = timeScale.options();
          const barSpacing = tsOptions.barSpacing || 6; // Default 6 pixels per bar
          
          // Map timeframe to seconds per bar
          const timeframeToSeconds: { [key: string]: number } = {
            'M15': 900,   // 15 minutes
            'M30': 1800,  // 30 minutes
            'H1': 3600,   // 1 hour
            'H4': 14400,  // 4 hours
            'D1': 86400,  // 1 day
          };
          
          const secondsPerBar = timeframeToSeconds[this.source.timeframe] || 900;
          
          // Calculate time difference in bars
          const timeDiff = exitTs - trade.entry_time_ts;
          const barsCount = timeDiff / secondsPerBar;
          const pixelDiff = barsCount * barSpacing;
          
          // Extrapolate x2 from x1
          x2 = x1 + pixelDiff;
          
          if (is2026Trade) {
            console.log('[TradesPrimitive] 2026 trade: Extrapolated x2 coordinate', { 
              x1, 
              x2, 
              timeDiff,
              timeDiffHours: (timeDiff / 3600).toFixed(2),
              barsCount: barsCount.toFixed(2),
              pixelDiff: pixelDiff.toFixed(2),
              barSpacing,
              timeframe: this.source.timeframe,
              secondsPerBar,
              entryTime: new Date(trade.entry_time_ts * 1000).toISOString(),
              exitTime: new Date(exitTs * 1000).toISOString()
            });
          }
        }
        
        if (is2026Trade) {
          console.log('[TradesPrimitive] 2026 trade coords:', { 
            entryTime: new Date(trade.entry_time_ts * 1000).toISOString(),
            exitTime: exitTs ? new Date(exitTs * 1000).toISOString() : null,
            entryTs: trade.entry_time_ts,
            exitTs: exitTs,
            x1, 
            x2,
            visibleFrom,
            visibleTo,
            visibleFromDate: new Date(visibleFrom * 1000).toISOString(),
            visibleToDate: new Date(visibleTo * 1000).toISOString(),
            lastCandleTime: this.source.lastCandleTime,
            lastCandleDate: this.source.lastCandleTime ? new Date(this.source.lastCandleTime * 1000).toISOString() : null,
            exitBeyondLastCandle: exitTs > (this.source.lastCandleTime || 0),
            exitBeyondVisible: exitTs > visibleTo,
          });
        }
        
        if (x1 === null || x2 === null) {
          if (is2026Trade) {
            console.log('[TradesPrimitive] 2026 trade SKIP (null coords):', { entryTime: new Date(trade.entry_time_ts * 1000).toISOString(), x1, x2, exitTs });
          }
          continue;
        }

        const yEntry = series.priceToCoordinate(trade.entry_price);
        const yTP = trade.tp !== null ? series.priceToCoordinate(trade.tp) : null;
        const ySL = trade.sl !== null ? series.priceToCoordinate(trade.sl) : null;
        if (yEntry === null) continue;

        let left = x1 * hpr;
        let right = x2 * hpr;
        if (left > right) [left, right] = [right, left];
        left = Math.max(0, Math.min(width, left));
        right = Math.max(0, Math.min(width, right));
        if (right - left < 0.5) continue;

        const snapHeight = (y: number) => Math.max(0, Math.min(height, y * vpr));

        if (yTP !== null) {
          const top = snapHeight(Math.min(yEntry, yTP));
          const areaH = Math.abs(yTP - yEntry) * vpr;
          ctx.fillStyle = GREEN_BG;
          ctx.fillRect(left, top, right - left, areaH);
        }

        if (ySL !== null) {
          const top = snapHeight(Math.min(yEntry, ySL));
          const areaH = Math.abs(ySL - yEntry) * vpr;
          ctx.fillStyle = RED_BG;
          ctx.fillRect(left, top, right - left, areaH);
        }

        const lx1 = x1 * hpr;
        const lx2 = x2 * hpr;
        const lyEntry = yEntry * vpr;

        ctx.strokeStyle = '#3b82f6';
        ctx.lineWidth = Math.max(1, 2 * vpr);
        ctx.setLineDash([6 * hpr, 3 * hpr]);
        ctx.beginPath();
        ctx.moveTo(lx1, lyEntry);
        ctx.lineTo(lx2, lyEntry);
        ctx.stroke();

        if (yTP !== null) {
          const lyTP = yTP * vpr;
          ctx.strokeStyle = '#22c55e';
          ctx.lineWidth = Math.max(1, 1 * vpr);
          ctx.setLineDash([6 * hpr, 3 * hpr]);
          ctx.beginPath();
          ctx.moveTo(lx1, lyTP);
          ctx.lineTo(lx2, lyTP);
          ctx.stroke();
        }

        if (ySL !== null) {
          const lySL = ySL * vpr;
          ctx.strokeStyle = '#ef4444';
          ctx.lineWidth = Math.max(1, 1 * vpr);
          ctx.setLineDash([6 * hpr, 3 * hpr]);
          ctx.beginPath();
          ctx.moveTo(lx1, lySL);
          ctx.lineTo(lx2, lySL);
          ctx.stroke();
        }
      }

      ctx.setLineDash([]);
    });
  }
}

class TradesPaneView implements IPrimitivePaneView {
  private readonly _renderer: TradesPaneRenderer;

  constructor(source: TradesOverlayPrimitive) {
    this._renderer = new TradesPaneRenderer(source);
  }

  zOrder(): "bottom" | "normal" | "top" {
    return "normal";
  }

  renderer(): IPrimitivePaneRenderer {
    return this._renderer;
  }
}

export class TradesOverlayPrimitive implements ISeriesPrimitive<Time> {
  chart: IChartApi | null = null;
  series: ISeriesApi<SeriesType> | null = null;
  trades: TradeOverlayEntry[] = [];
  visible = true;
  lastCandleTime: number | null = null;
  timeframe: string = 'M15'; // Default M15

  private requestUpdate?: () => void;
  private readonly _paneViews: TradesPaneView[];

  constructor() {
    this._paneViews = [new TradesPaneView(this)];
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

  setTrades(trades: TradeOverlayEntry[]): void {
    this.trades = trades;
    this.requestUpdate?.();
  }

  setVisible(visible: boolean): void {
    this.visible = visible;
    this.requestUpdate?.();
  }

  setLastCandleTime(ts: number | null): void {
    this.lastCandleTime = ts;
    this.requestUpdate?.();
  }

  setTimeframe(timeframe: string): void {
    this.timeframe = timeframe;
    this.requestUpdate?.();
  }

  updateAllViews(): void {}

  paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews;
  }
}



