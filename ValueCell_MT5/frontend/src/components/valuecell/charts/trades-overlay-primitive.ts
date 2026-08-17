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
  // ATR band info (optional) — drawn as a horizontal line + value label
  atr?: number | null;
  atr_start_ts?: number | null;
  atr_end_ts?: number | null;
}

const GREEN_BG = "rgba(34, 197, 94, 0.15)";
const RED_BG = "rgba(239, 68, 68, 0.15)";

class TradesPaneRenderer implements IPrimitivePaneRenderer {
  private lastLoggedKey = "";

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
    if (visibleTrades.length === 0) return;

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const hpr = scope.horizontalPixelRatio;
      const vpr = scope.verticalPixelRatio;
      const width = scope.bitmapSize.width;
      const height = scope.bitmapSize.height;

      let count2026 = 0;
      let skippedCount = 0;

      // Shared helpers for both the trade loop and the ATR band loop.
      const timeframeToSeconds: { [key: string]: number } = {
        'M15': 900,   // 15 minutes
        'M30': 1800,  // 30 minutes
        'H1': 3600,   // 1 hour
        'H4': 14400,  // 4 hours
        'D1': 86400,  // 1 day
      };
      const tsOptions = timeScale.options();

      for (const trade of visibleTrades) {
        const lastCandleTs = this.source.lastCandleTime;
        const isOpenTrade = trade.exit_time_ts === null;
        const secondsPerBar = timeframeToSeconds[this.source.timeframe] || 900;
        const barSpacing = tsOptions.barSpacing || 6;

        // If trade is closed (exit_time_ts !== null), use exact exit timestamp.
        // If trade is OPEN / RUNNING, project forward by 15 bars into the future so box, lines & targets are visible!
        const exitTs = !isOpenTrade
          ? trade.exit_time_ts!
          : (lastCandleTs !== null ? lastCandleTs + 15 * secondsPerBar : trade.entry_time_ts + 15 * secondsPerBar);
        if (exitTs === null) continue;

        const is2026Trade = new Date(trade.entry_time_ts * 1000).getFullYear() === 2026;
        if (is2026Trade) {
          count2026++;
        }

        let x1 = timeScale.timeToCoordinate(trade.entry_time_ts as UTCTimestamp);
        let x2 = timeScale.timeToCoordinate(exitTs as UTCTimestamp);

        const lastCandleX = lastCandleTs !== null ? timeScale.timeToCoordinate(lastCandleTs as UTCTimestamp) : null;

        // If x1 is null because entry is not in visible range
        if (x1 === null && lastCandleX !== null && lastCandleTs !== null) {
          const barsDiff = (trade.entry_time_ts - lastCandleTs) / secondsPerBar;
          x1 = (lastCandleX + barsDiff * barSpacing) as any;
        }

        // Extrapolate x2 if it's null (future candle / projection / off chart)
        if (x2 === null) {
          if (x1 !== null) {
            const barsDiff = (exitTs - trade.entry_time_ts) / secondsPerBar;
            x2 = (x1 + Math.max(1, barsDiff) * barSpacing) as any;
          } else if (lastCandleX !== null && lastCandleTs !== null) {
            const barsAhead = (exitTs - lastCandleTs) / secondsPerBar;
            x2 = (lastCandleX + barsAhead * barSpacing) as any;
          }
        }

        // Guard against closed past trades stretching beyond lastCandleX
        if (!isOpenTrade && lastCandleTs !== null && exitTs <= lastCandleTs && lastCandleX !== null && x2 !== null && x2 > lastCandleX) {
          x2 = lastCandleX;
        }
        
        if (x1 === null || x2 === null) {
          if (is2026Trade) {
            skippedCount++;
          }
          continue;
        }

        const yEntry = series.priceToCoordinate(trade.entry_price);
        let yTP = trade.tp !== null ? series.priceToCoordinate(trade.tp) : null;
        let ySL = trade.sl !== null ? series.priceToCoordinate(trade.sl) : null;
        if (yEntry === null) continue;

        // If TP or SL is off-screen (null from priceToCoordinate), extrapolate coordinate from known scale
        if (yTP === null && trade.tp !== null && ySL !== null && trade.sl !== null) {
          const pxPerUnit = Math.abs(ySL - yEntry) / (Math.abs(trade.sl - trade.entry_price) || 1);
          yTP = (trade.type === 'BUY' ? yEntry - Math.abs(trade.tp - trade.entry_price) * pxPerUnit : yEntry + Math.abs(trade.tp - trade.entry_price) * pxPerUnit) as any;
        } else if (ySL === null && trade.sl !== null && yTP !== null && trade.tp !== null) {
          const pxPerUnit = Math.abs(yTP - yEntry) / (Math.abs(trade.tp - trade.entry_price) || 1);
          ySL = (trade.type === 'BUY' ? yEntry + Math.abs(trade.sl - trade.entry_price) * pxPerUnit : yEntry - Math.abs(trade.sl - trade.entry_price) * pxPerUnit) as any;
        }

        let left = x1 * hpr;
        let right = x2 * hpr;
        if (left > right) [left, right] = [right, left];
        left = Math.max(0, Math.min(width, left));
        right = Math.max(0, Math.min(width, right));
        // ponytail: 0-bar trades (stopped same candle) get min 2px width instead of skip
        if (right - left < 2) right = left + 2;

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

        // ── Visual PnL Pill Badge ──
        // Render a sharp, readable pill badge displaying floating or realized PnL
        const pnl = trade.profit ?? 0;
        const isClosed = trade.exit_time_ts !== null;
        let pnlText = "";
        if (pnl > 0) {
          pnlText = `+$${pnl.toFixed(2)}${isClosed ? " (TP)" : ""}`;
        } else if (pnl < 0) {
          pnlText = `-$${Math.abs(pnl).toFixed(2)}${isClosed ? " (SL)" : ""}`;
        } else {
          pnlText = `$0.00${isClosed ? "" : " (Open)"}`;
        }

        ctx.font = `bold ${Math.max(10, 11 * vpr)}px monospace`;
        const pnlTextW = ctx.measureText(pnlText).width;
        
        // Position badge: For open trades, sit right near current active candle. For closed trades, at exit point.
        let badgeX = Math.min(width - pnlTextW - 12 * hpr, Math.max(8 * hpr, right - pnlTextW - 4 * hpr));
        if (!isClosed && lastCandleX !== null) {
          const liveX = lastCandleX * hpr + 8 * hpr;
          if (liveX + pnlTextW + 8 * hpr < width) {
            badgeX = liveX;
          }
        }
        const badgeY = lyEntry;

        const isWin = pnl >= 0;
        const badgeBg = isWin ? "rgba(16, 185, 129, 0.92)" : "rgba(239, 68, 68, 0.92)";
        const badgeBorder = isWin ? "#10b981" : "#ef4444";

        ctx.fillStyle = badgeBg;
        ctx.strokeStyle = badgeBorder;
        ctx.lineWidth = Math.max(1, 1 * vpr);
        ctx.beginPath();
        ctx.roundRect(badgeX - 4 * hpr, badgeY - 9 * vpr, pnlTextW + 8 * hpr, 18 * vpr, 4 * vpr);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#ffffff";
        ctx.textBaseline = "middle";
        ctx.fillText(pnlText, badgeX, badgeY);
      }

      // ── ATR band: horizontal line from atr_start_ts to atr_end_ts + value label ──
      // Drawn after trades so it sits on top, but with a translucent fill so it
      // never hides the candles. Position is adaptive: if the ATR price collides
      // with an existing SL/TP/entry line, shift it to a clear area.
      for (const trade of visibleTrades) {
        if (trade.atr == null || trade.atr_start_ts == null || trade.atr_end_ts == null) continue;

        // Anchor on the entry (atr_end_ts) and measure exactly `period` bars to
        // the left. This keeps the band exactly 14 candles wide even when the
        // start falls off the left edge of the visible range (during replay).
        const ax2 = timeScale.timeToCoordinate(trade.atr_end_ts as UTCTimestamp);
        if (ax2 === null) continue;
        const atrSecondsPerBar = timeframeToSeconds[this.source.timeframe] || 900;
        const atrBarSpacing = tsOptions.barSpacing || 6;
        const bars = Math.max(1, Math.round((trade.atr_end_ts - trade.atr_start_ts) / atrSecondsPerBar));
        const atrWidthPx = bars * atrBarSpacing;
        const aleftRaw = ax2 - atrWidthPx;
        const arightRaw = ax2;

        // ATR line sits at the top of the visible price range, above the candles.
        // Use the entry price + ATR as a natural anchor, then nudge away from
        // any occupied price (SL/TP/entry) to avoid overlap.
        const basePrice = trade.entry_price + trade.atr;
        let atrPrice = basePrice;
        const occupied = [trade.entry_price, trade.sl, trade.tp].filter((p): p is number => p !== null);
        const minGap = trade.atr * 0.15; // 15% of ATR as minimum separation
        let guard = 0;
        while (occupied.some(p => Math.abs(p - atrPrice) < minGap) && guard < 20) {
          atrPrice += minGap; // shift up until clear
          guard++;
        }

        const yAtr = series.priceToCoordinate(atrPrice);
        if (yAtr === null) continue;

        let aleft = aleftRaw * hpr;
        let aright = arightRaw * hpr;
        if (aleft > aright) [aleft, aright] = [aright, aleft];
        aleft = Math.max(0, Math.min(width, aleft));
        aright = Math.max(0, Math.min(width, aright));
        if (aright - aleft < 2) aright = aleft + 2;

        const lyAtr = yAtr * vpr;

        // Translucent band fill (subtle, doesn't hide candles)
        ctx.fillStyle = 'rgba(34, 211, 238, 0.06)';
        ctx.fillRect(aleft, lyAtr - 10 * vpr, aright - aleft, 20 * vpr);

        // Solid ATR line
        ctx.strokeStyle = '#22d3ee';
        ctx.lineWidth = Math.max(1, 2 * vpr);
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(aleft, lyAtr);
        ctx.lineTo(aright, lyAtr);
        ctx.stroke();

        // Value label above the line (centered on the band)
        const labelText = `ATR $${trade.atr.toFixed(2)}`;
        ctx.font = `${Math.max(10, 11 * vpr)}px monospace`;
        const textW = ctx.measureText(labelText).width;
        const labelX = aleft + (aright - aleft) / 2 - textW / 2;
        const labelY = lyAtr - 8 * vpr;

        // Label background pill
        ctx.fillStyle = 'rgba(14, 116, 144, 0.9)';
        ctx.strokeStyle = '#22d3ee';
        ctx.lineWidth = Math.max(1, 1 * vpr);
        ctx.beginPath();
        ctx.roundRect(labelX - 4 * hpr, labelY - 12 * vpr, textW + 8 * hpr, 16 * vpr, 4 * vpr);
        ctx.fill();
        ctx.stroke();

        // Label text
        ctx.fillStyle = '#ffffff';
        ctx.textBaseline = 'middle';
        ctx.fillText(labelText, labelX, labelY);
      }

      ctx.setLineDash([]);

      const active2026 = count2026 - skippedCount;
      if (count2026 > 0) {
        const logKey = `${active2026}_${skippedCount}`;
        if (this.lastLoggedKey !== logKey) {
          console.log(`✅ [TradesPrimitive] 2026 trades rendered: ${active2026} active, ${skippedCount} skipped`);
          this.lastLoggedKey = logKey;
        }
      }
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



