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

export type LiquidityLevelType = "PDH" | "PDL" | "PWH" | "PWL" | "ASIA_H" | "ASIA_L" | "LON_H" | "LON_L" | "NY_H" | "NY_L";
export type LiquidityLevelStatus = "UNTOUCHED" | "SWEPT" | "BROKEN";

export interface LiquidityLevelItem {
  id: string;
  type: LiquidityLevelType;
  price: number;
  startTime: number; // unix timestamp
  endTime: number;   // unix timestamp
  status: LiquidityLevelStatus;
  label?: string;
  periodLabel?: string; // e.g. "D-1", "W-1", "ASIA", "LON", "NY"
}

class LiquidityLevelsPaneRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly source: LiquidityLevelsPrimitive) {}

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
    if (!chart || !this.source.visible || this.source.levels.length === 0) return;

    const series = this.source.series;
    if (!series) return;

    const timeScale = chart.timeScale();
    const visibleRange = timeScale.getVisibleRange();
    if (!visibleRange) return;

    const visibleFrom = visibleRange.from as number;
    const visibleTo = visibleRange.to as number;

    const padding = 7 * 24 * 3600; // 7 hari buffer
    const visibleLevels = this.source.levels.filter((level) => {
      return (
        level.startTime <= visibleTo + padding &&
        level.endTime >= visibleFrom - padding
      );
    });

    if (visibleLevels.length === 0) return;

    const hoveredLevel = this.source.levels.find((l) => l.id === this.source.hoveredLevelId);
    const hoveredStartTime = hoveredLevel ? hoveredLevel.startTime : null;
    const hoveredPeriodLabel = hoveredLevel ? hoveredLevel.periodLabel : null;
    const isAnyHovered = Boolean(hoveredLevel !== undefined);

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const hpr = scope.horizontalPixelRatio;
      const vpr = scope.verticalPixelRatio;

      // Soft range bracket fill between paired levels (PDH/PDL, PWH/PWL, or Session H/L) of active hovered session
      if (hoveredLevel) {
        const pairLevels = visibleLevels.filter((l) => 
          hoveredPeriodLabel
            ? l.periodLabel === hoveredPeriodLabel
            : (hoveredStartTime !== null && l.startTime === hoveredStartTime)
        );
        const pdh = pairLevels.find((l) => l.type === "PDH" || l.type === "PWH" || l.type === "ASIA_H" || l.type === "LON_H" || l.type === "NY_H");
        const pdl = pairLevels.find((l) => l.type === "PDL" || l.type === "PWL" || l.type === "ASIA_L" || l.type === "LON_L" || l.type === "NY_L");
        if (pdh && pdl) {
          const isPairWeekly = pairLevels.some((l) => l.type === "PWH" || l.type === "PWL");
          const isPairSession = pairLevels.some((l) => l.type.includes("_H") || l.type.includes("_L"));
          const yH = series.priceToCoordinate(pdh.price);
          const yL = series.priceToCoordinate(pdl.price);
          const minStartTime = Math.min(pdh.startTime, pdl.startTime);
          const maxEndTime = Math.max(pdh.endTime, pdl.endTime);
          const x1 = timeScale.timeToCoordinate(minStartTime as UTCTimestamp);
          const x2 = timeScale.timeToCoordinate(maxEndTime as UTCTimestamp);
          if (yH !== null && yL !== null && x1 !== null) {
            const lyH = Math.round(yH * vpr) + 0.5;
            const lyL = Math.round(yL * vpr) + 0.5;
            const lx1 = x1 * hpr;
            const lx2Coord = (x2 !== null ? Math.max(x2 * hpr, lx1 + 40 * hpr) : (lx1 + 120 * hpr));

            ctx.save();
            ctx.fillStyle = isPairWeekly
              ? "rgba(192, 132, 252, 0.06)"
              : isPairSession
                ? "rgba(245, 158, 11, 0.05)"
                : "rgba(56, 189, 248, 0.05)";
            ctx.fillRect(lx1, Math.min(lyH, lyL), lx2Coord - lx1, Math.abs(lyL - lyH));
            ctx.restore();
          }
        }
      }

      for (const item of visibleLevels) {
        let x1 = timeScale.timeToCoordinate(item.startTime as UTCTimestamp);
        if (x1 === null && this.source.candleTimes.length > 0) {
          const found = this.source.candleTimes.find((t) => t >= item.startTime);
          if (found) {
            x1 = timeScale.timeToCoordinate(found as UTCTimestamp);
          }
        }

        let x2 = timeScale.timeToCoordinate(item.endTime as UTCTimestamp);
        if (x2 === null && this.source.candleTimes.length > 0) {
          for (let i = this.source.candleTimes.length - 1; i >= 0; i--) {
            if (this.source.candleTimes[i] <= item.endTime) {
              x2 = timeScale.timeToCoordinate(this.source.candleTimes[i] as UTCTimestamp);
              break;
            }
          }
        }

        const yRaw = series.priceToCoordinate(item.price);

        if (x1 === null || yRaw === null) continue;

        let lx2: number;
        if (x2 !== null) {
          lx2 = Math.max(x2 * hpr, x1 * hpr + 40 * hpr);
        } else {
          const lastTime = this.source.lastCandleTime;
          const lastX = lastTime ? timeScale.timeToCoordinate(lastTime as UTCTimestamp) : null;
          lx2 = lastX !== null ? (lastX + 60) * hpr : (x1 + 120) * hpr;
        }

        const lx1 = x1 * hpr;
        const ly = Math.round(yRaw * vpr) + 0.5;

        // Pasangan PDH & PDL atau Sesi H & L dari sesi yang sama ikut aktif menyala bersamaan
        const isDirectHover = item.id === this.source.hoveredLevelId;
        const isPairHover = Boolean(
          hoveredPeriodLabel
            ? item.periodLabel === hoveredPeriodLabel
            : (hoveredStartTime !== null && item.startTime === hoveredStartTime)
        );
        const isHovered = isDirectHover || isPairHover;
        const isDimmed = isAnyHovered && !isHovered;

        // Visual Specs Varian A (Executive Dashed Pill)
        let strokeColor: string;
        let lineWidth: number;
        let lineDash: number[];
        let pillBorderColor: string;
        let pillTitleColor: string;
        let tagBgColor: string;
        let tagTextColor: string;
        let tagText: string;

        const isWeekly = item.type === "PWH" || item.type === "PWL";
        const isSession = item.type.includes("_H") || item.type.includes("_L");
        const isHigh = item.type === "PDH" || item.type === "PWH" || item.type.endsWith("_H");

        // 1. Identitas Garis & Judul Pill (PWH/PWL: Royal Purple | Session: Amber Gold | PDH/PDL: Sky Blue / Royal Indigo)
        if (isWeekly) {
          if (isHigh) {
            pillBorderColor = item.status === "BROKEN" ? "rgba(192, 132, 252, 0.40)" : "#9333ea";
            pillTitleColor = item.status === "BROKEN" ? "rgba(216, 180, 254, 0.75)" : "#c084fc";
            strokeColor = item.status === "BROKEN" ? "rgba(192, 132, 252, 0.35)" : "rgba(192, 132, 252, 0.95)";
          } else {
            pillBorderColor = item.status === "BROKEN" ? "rgba(168, 85, 247, 0.40)" : "#7e22ce";
            pillTitleColor = item.status === "BROKEN" ? "rgba(192, 132, 252, 0.75)" : "#a855f7";
            strokeColor = item.status === "BROKEN" ? "rgba(168, 85, 247, 0.35)" : "rgba(168, 85, 247, 0.95)";
          }
        } else if (isSession) {
          if (isHigh) {
            pillBorderColor = item.status === "BROKEN" ? "rgba(245, 158, 11, 0.40)" : "#d97706";
            pillTitleColor = item.status === "BROKEN" ? "rgba(251, 191, 36, 0.75)" : "#fbbf24";
            strokeColor = item.status === "BROKEN" ? "rgba(245, 158, 11, 0.35)" : "rgba(245, 158, 11, 0.95)";
          } else {
            pillBorderColor = item.status === "BROKEN" ? "rgba(217, 119, 6, 0.40)" : "#b45309";
            pillTitleColor = item.status === "BROKEN" ? "rgba(245, 158, 11, 0.75)" : "#f59e0b";
            strokeColor = item.status === "BROKEN" ? "rgba(217, 119, 6, 0.35)" : "rgba(217, 119, 6, 0.95)";
          }
        } else {
          if (isHigh) {
            pillBorderColor = item.status === "BROKEN" ? "rgba(56, 189, 248, 0.40)" : "#0284c7";
            pillTitleColor = item.status === "BROKEN" ? "rgba(56, 189, 248, 0.75)" : "#38bdf8";
            strokeColor = item.status === "BROKEN" ? "rgba(56, 189, 248, 0.35)" : "rgba(56, 189, 248, 0.95)";
          } else {
            pillBorderColor = item.status === "BROKEN" ? "rgba(129, 140, 248, 0.40)" : "#6366f1";
            pillTitleColor = item.status === "BROKEN" ? "rgba(165, 180, 252, 0.75)" : "#a5b4fc";
            strokeColor = item.status === "BROKEN" ? "rgba(129, 140, 248, 0.35)" : "rgba(129, 140, 248, 0.95)";
          }
        }

        // 2. Garis Dash Pattern & Ketebalan
        if (item.status === "SWEPT") {
          strokeColor = "rgba(245, 158, 11, 0.95)"; // Amber Gold
          lineWidth = isWeekly ? 2.0 * hpr : isSession ? 1.5 * hpr : 1.5 * hpr;
          lineDash = isWeekly ? [6 * hpr, 4 * hpr] : [3 * hpr, 3 * hpr];
          pillBorderColor = "#f59e0b";
          pillTitleColor = "#fbbf24";
          tagBgColor = "rgba(245, 158, 11, 0.20)";
          tagTextColor = "#f59e0b";
          tagText = "SWEPT ⚡";
        } else if (item.status === "BROKEN") {
          if (isWeekly) {
            strokeColor = isHigh ? "rgba(192, 132, 252, 0.35)" : "rgba(168, 85, 247, 0.35)";
            pillBorderColor = isHigh ? "rgba(192, 132, 252, 0.45)" : "rgba(168, 85, 247, 0.45)";
            pillTitleColor = isHigh ? "rgba(216, 180, 254, 0.75)" : "rgba(192, 132, 252, 0.75)";
          } else if (isSession) {
            strokeColor = isHigh ? "rgba(245, 158, 11, 0.35)" : "rgba(217, 119, 6, 0.35)";
            pillBorderColor = isHigh ? "rgba(245, 158, 11, 0.45)" : "rgba(217, 119, 6, 0.45)";
            pillTitleColor = isHigh ? "rgba(251, 191, 36, 0.75)" : "rgba(245, 158, 11, 0.75)";
          } else {
            strokeColor = isHigh ? "rgba(56, 189, 248, 0.35)" : "rgba(129, 140, 248, 0.35)";
            pillBorderColor = isHigh ? "rgba(56, 189, 248, 0.45)" : "rgba(129, 140, 248, 0.45)";
            pillTitleColor = isHigh ? "rgba(56, 189, 248, 0.75)" : "rgba(165, 180, 252, 0.75)";
          }
          lineWidth = isWeekly ? 1.4 * hpr : 1.0 * hpr;
          lineDash = isWeekly ? [4 * hpr, 6 * hpr] : isSession ? [3 * hpr, 3 * hpr] : [2 * hpr, 4 * hpr];
          tagText = "BROKEN";
        } else {
          // UNTOUCHED / FRESH
          if (isWeekly) {
            strokeColor = isHigh ? "rgba(192, 132, 252, 0.95)" : "rgba(168, 85, 247, 0.95)";
            pillBorderColor = isHigh ? "#9333ea" : "#7e22ce";
            pillTitleColor = isHigh ? "#c084fc" : "#a855f7";
            tagBgColor = isHigh ? "rgba(192, 132, 252, 0.18)" : "rgba(168, 85, 247, 0.18)";
            tagTextColor = isHigh ? "#c084fc" : "#a855f7";
            lineWidth = 2.0 * hpr;
            lineDash = [10 * hpr, 5 * hpr];
          } else if (isSession) {
            strokeColor = isHigh ? "rgba(245, 158, 11, 0.95)" : "rgba(217, 119, 6, 0.95)";
            pillBorderColor = isHigh ? "#d97706" : "#b45309";
            pillTitleColor = isHigh ? "#fbbf24" : "#f59e0b";
            tagBgColor = "rgba(245, 158, 11, 0.18)";
            tagTextColor = "#fbbf24";
            lineWidth = 1.5 * hpr;
            lineDash = [4 * hpr, 4 * hpr];
          } else {
            strokeColor = isHigh ? "rgba(56, 189, 248, 0.95)" : "rgba(129, 140, 248, 0.95)";
            pillBorderColor = isHigh ? "#0284c7" : "#6366f1";
            pillTitleColor = isHigh ? "#38bdf8" : "#a5b4fc";
            tagBgColor = isHigh ? "rgba(56, 189, 248, 0.18)" : "rgba(129, 140, 248, 0.18)";
            tagTextColor = isHigh ? "#38bdf8" : "#818cf8";
            lineWidth = 1.5 * hpr;
            lineDash = [6 * hpr, 4 * hpr];
          }
        }

        // 3. Warna Khusus Kotak Tag Status (Traffic Light System)
        if (item.status === "SWEPT") {
          tagBgColor = "rgba(245, 158, 11, 0.22)";
          tagTextColor = "#f59e0b";
          tagText = "SWEPT ⚡";
        } else if (item.status === "BROKEN") {
          tagBgColor = "rgba(239, 68, 68, 0.22)";
          tagTextColor = "#ef4444";
          tagText = "BROKEN";
        } else {
          tagBgColor = "rgba(16, 185, 129, 0.20)";
          tagTextColor = "#10b981";
          tagText = "FRESH";
        }

        ctx.save();

        if (isDimmed) {
          ctx.globalAlpha = 0.22;
        }

        if (isHovered) {
          ctx.globalAlpha = 1.0;
          if (isWeekly) {
            ctx.shadowColor = isHigh ? "#c084fc" : "#a855f7";
            ctx.shadowBlur = 14 * hpr;
            lineWidth = 2.8 * hpr;
            lineDash = [12 * hpr, 4 * hpr];
          } else if (isSession) {
            ctx.shadowColor = "#f59e0b";
            ctx.shadowBlur = 12 * hpr;
            lineWidth = 2.4 * hpr;
            lineDash = [6 * hpr, 3 * hpr];
          } else {
            ctx.shadowColor = isHigh ? "#38bdf8" : "#818cf8";
            ctx.shadowBlur = 12 * hpr;
            lineWidth = 2.4 * hpr;
            lineDash = [8 * hpr, 3 * hpr];
          }
        }

        // 1. Draw Horizontal Line
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = lineWidth;
        ctx.setLineDash(lineDash);
        ctx.beginPath();
        ctx.moveTo(lx1, ly);
        ctx.lineTo(lx2, ly);
        ctx.stroke();

        // 2. Origin point dot at session start (wick origin)
        ctx.setLineDash([]);
        if (isHovered) {
          // Halo pulsing glow ring
          ctx.beginPath();
          ctx.arc(lx1, ly, 6 * hpr, 0, Math.PI * 2);
          ctx.fillStyle = isWeekly
            ? (isHigh ? "rgba(192, 132, 252, 0.32)" : "rgba(168, 85, 247, 0.32)")
            : isSession
              ? "rgba(245, 158, 11, 0.32)"
              : (isHigh ? "rgba(56, 189, 248, 0.32)" : "rgba(129, 140, 248, 0.32)");
          ctx.fill();
          ctx.strokeStyle = isWeekly
            ? (isHigh ? "#c084fc" : "#a855f7")
            : isSession
              ? "#f59e0b"
              : (isHigh ? "#38bdf8" : "#818cf8");
          ctx.lineWidth = 1.8 * hpr;
          ctx.stroke();

          // Center bright core
          ctx.beginPath();
          ctx.arc(lx1, ly, 2.5 * hpr, 0, Math.PI * 2);
          ctx.fillStyle = "#ffffff";
          ctx.fill();
        } else {
          ctx.fillStyle = strokeColor;
          ctx.beginPath();
          ctx.arc(lx1, ly, 2.5 * hpr, 0, Math.PI * 2);
          ctx.fill();
        }

        // 3. Draw Varian A Dual-Tag Pill Badge at the Right Edge
        const displayType = item.type.replace("_", " ");
        const titleText = `${displayType} ${item.price.toFixed(2)}`;
        const segWidth = lx2 - lx1;
        if (segWidth >= 30 * hpr) {
          const fontTitleSize = Math.max(9, Math.round(9.5 * vpr));
          const fontTagSize = Math.max(8, Math.round(8.5 * vpr));

          ctx.font = `700 ${fontTitleSize}px monospace`;
          const titleWidth = ctx.measureText(titleText).width;

          ctx.font = `800 ${fontTagSize}px monospace`;
          const tagWidth = ctx.measureText(tagText).width;

          const padX = 6 * hpr;
          const tagPadX = 5 * hpr;
          const tagGap = 6 * hpr;
          const pillHeight = 19 * vpr;
          const pillWidth = padX + titleWidth + tagGap + tagWidth + tagPadX * 2 + padX;
          const pillY = ly - pillHeight / 2;

          const hoverBorderColor = isWeekly
            ? (isHigh ? "#c084fc" : "#a855f7")
            : isSession
              ? "#f59e0b"
              : (isHigh ? "#38bdf8" : "#818cf8");

          if (segWidth >= pillWidth + 6 * hpr) {
            const pillX = lx2 - pillWidth;

            // Pill Container Card
            ctx.fillStyle = "rgba(15, 23, 42, 0.94)";
            ctx.strokeStyle = isHovered ? hoverBorderColor : pillBorderColor;
            ctx.lineWidth = isHovered ? 2 * hpr : 1.2 * hpr;

            ctx.beginPath();
            if (typeof ctx.roundRect === "function") {
              ctx.roundRect(pillX, pillY, pillWidth, pillHeight, 5 * hpr);
            } else {
              ctx.rect(pillX, pillY, pillWidth, pillHeight);
            }
            ctx.fill();
            ctx.stroke();

            // Pill Title Text
            ctx.font = `700 ${fontTitleSize}px monospace`;
            ctx.fillStyle = pillTitleColor;
            const titleX = pillX + padX;
            const textY = pillY + pillHeight / 2 + 3.5 * vpr;
            ctx.fillText(titleText, titleX, textY);

            // Mini Status Tag Capsule
            const tagX = titleX + titleWidth + tagGap;
            const tagH = 13 * vpr;
            const tagY = pillY + (pillHeight - tagH) / 2;
            const tagTotalW = tagWidth + tagPadX * 2;

            ctx.fillStyle = tagBgColor;
            ctx.beginPath();
            if (typeof ctx.roundRect === "function") {
              ctx.roundRect(tagX, tagY, tagTotalW, tagH, 3 * hpr);
            } else {
              ctx.rect(tagX, tagY, tagTotalW, tagH);
            }
            ctx.fill();

            ctx.font = `800 ${fontTagSize}px monospace`;
            ctx.fillStyle = tagTextColor;
            ctx.fillText(tagText, tagX + tagPadX, tagY + tagH - 3 * vpr);
          } else {
            // Compact Badge untuk rentang zoom menengah
            const compactText = `${displayType} ${item.price.toFixed(1)}`;
            const textW = ctx.measureText(compactText).width;
            const dotR = 2.5 * hpr;
            const compactW = 6 * hpr + textW + 5 * hpr + dotR * 2 + 5 * hpr;
            const compactX = Math.max(lx1 + 4 * hpr, lx2 - compactW);

            ctx.fillStyle = "rgba(15, 23, 42, 0.94)";
            ctx.strokeStyle = isHovered ? hoverBorderColor : pillBorderColor;
            ctx.lineWidth = isHovered ? 2 * hpr : 1 * hpr;

            ctx.beginPath();
            if (typeof ctx.roundRect === "function") {
              ctx.roundRect(compactX, pillY, compactW, pillHeight, 4 * hpr);
            } else {
              ctx.rect(compactX, pillY, compactW, pillHeight);
            }
            ctx.fill();
            ctx.stroke();

            ctx.font = `700 ${fontTitleSize}px monospace`;
            ctx.fillStyle = pillTitleColor;
            ctx.fillText(compactText, compactX + 5 * hpr, pillY + pillHeight / 2 + 3.5 * vpr);

            // Dot status khusus
            ctx.fillStyle = tagTextColor;
            ctx.beginPath();
            ctx.arc(compactX + compactW - 6 * hpr, pillY + pillHeight / 2, dotR, 0, Math.PI * 2);
            ctx.fill();
          }
        }

        ctx.restore();
      }
    });
  }
}

class LiquidityLevelsPaneView implements IPrimitivePaneView {
  private readonly _renderer: LiquidityLevelsPaneRenderer;

  constructor(source: LiquidityLevelsPrimitive) {
    this._renderer = new LiquidityLevelsPaneRenderer(source);
  }

  zOrder(): "bottom" | "normal" | "top" {
    return "normal";
  }

  renderer(): IPrimitivePaneRenderer {
    return this._renderer;
  }
}

export class LiquidityLevelsPrimitive implements ISeriesPrimitive<Time> {
  chart: IChartApi | null = null;
  series: ISeriesApi<SeriesType> | null = null;
  visible: boolean = true;
  levels: LiquidityLevelItem[] = [];
  lastCandleTime: number | null = null;
  hoveredLevelId: string | null = null;
  candleTimes: number[] = [];

  private requestUpdate?: () => void;
  private readonly _paneViews: readonly IPrimitivePaneView[];

  constructor() {
    this._paneViews = [new LiquidityLevelsPaneView(this)];
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

  setCandleTimes(times: number[]): void {
    this.candleTimes = times;
  }

  setLevels(levels: LiquidityLevelItem[]): void {
    this.levels = levels;
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

  setHoveredPoint(point: { x: number; y: number } | null): void {
    let newHoveredId: string | null = null;
    if (point && this.series && this.chart && this.visible && this.levels.length > 0) {
      const series = this.series;
      const timeScale = this.chart.timeScale();
      const curY = point.y;
      const curX = point.x;

      let minDistance = Infinity;
      for (const item of this.levels) {
        const yCoord = series.priceToCoordinate(item.price);
        let x1 = timeScale.timeToCoordinate(item.startTime as UTCTimestamp);
        if (x1 === null && this.candleTimes.length > 0) {
          const found = this.candleTimes.find((t) => t >= item.startTime);
          if (found) {
            x1 = timeScale.timeToCoordinate(found as UTCTimestamp);
          }
        }

        let x2 = timeScale.timeToCoordinate(item.endTime as UTCTimestamp);
        if (x2 === null && this.candleTimes.length > 0) {
          for (let i = this.candleTimes.length - 1; i >= 0; i--) {
            if (this.candleTimes[i] <= item.endTime) {
              x2 = timeScale.timeToCoordinate(this.candleTimes[i] as UTCTimestamp);
              break;
            }
          }
        }

        if (yCoord === null || x1 === null) continue;

        const lx1 = x1;
        const lx2 = x2 !== null ? Math.max(x2, x1 + 40) : (x1 + 120);

        if (curX >= lx1 - 20 && curX <= lx2 + 90) {
          const dist = Math.abs(curY - yCoord);
          if (dist <= 14 && dist < minDistance) {
            minDistance = dist;
            newHoveredId = item.id;
          }
        }
      }
    }

    if (this.hoveredLevelId !== newHoveredId) {
      this.hoveredLevelId = newHoveredId;
      this.requestUpdate?.();
    }
  }

  updateAllViews(): void {
    this.requestUpdate?.();
  }
}

