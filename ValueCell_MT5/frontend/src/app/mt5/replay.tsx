import { useEffect, useRef, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import {
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  CandlestickSeries,
  LineSeries,
  LineStyle,
} from "lightweight-charts";
import { Play, Pause, SkipForward, Square, Loader2, Calendar, CalendarDays, X, Rewind, Settings, Target, ChartNoAxesCombined, CircleDollarSign, Trophy, TrendingDown, TrendingUp, Trash2, Sliders, Layers, GripVertical, Minimize2, Maximize2 } from "lucide-react";
import {
  StructureLinesPrimitive,
  type StructureLineItem,
} from "@/components/valuecell/charts/structure-lines-primitive";
import {
  TradesOverlayPrimitive,
  type TradeOverlayEntry,
} from "@/components/valuecell/charts/trades-overlay-primitive";
import {
  SessionZonesPrimitive,
  type SessionZoneBox,
} from "@/components/valuecell/charts/session-zones-primitive";
import {
  SupplyDemandPrimitive,
  type SupplyDemandZoneItem,
} from "@/components/valuecell/charts/supply-demand-primitive";
import {
  LiquidityPoolsPrimitive,
  type LiquidityPoolItem,
} from "@/components/valuecell/charts/liquidity-pools-primitive";
import { useSessionZones } from "@/api/mt5_agents";
import { followReplayPlayhead } from "./replay-chart";

// ── Types ────────────────────────────────────────────────────────────────────

interface ReplayCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema200: number | null;
}

interface StructureEvent {
  type: string;
  direction: string;
  price: number;
  time: number;
  timeframe: string;
  status: string;
  previous_price: number | null;
  previous_time: number | null;
}

interface ReplayTrade {
  ticket: number;
  type: string;
  status: string;
  reject_reason: string | null;
  entry_price: number | null;
  exit_price: number | null;
  sl: number | null;
  tp: number | null;
  net_profit: number | null;
  session: string;
  entry_time: number | null;
  exit_time: number | null;
  lot_size: number | null;
}

interface ReplayData {
  candles: ReplayCandle[];
  structures: StructureEvent[];
  trades: ReplayTrade[];
  available_months: { year: number; month: number }[];
  meta: {
    timeframe: string;
    date_from: string;
    date_to: string;
    total_candles: number;
    total_structures: number;
    total_trades: number;
  };
}

export interface PositionPlanner {
  type: "long" | "short";
  entryPrice: number;
  entryTime: number;
  exitTime?: number;
  durationBars?: number;
  slPrice: number;
  tpPrice: number;
  lotSize: number;
  riskRewardRatio: number;
  riskAmountUsd?: number;
  isAutoRisk?: boolean;
}

interface EntryFilterParams {
  entry_choch: boolean;
  entry_bos: boolean;
  entry_bos_cycle_2_plus: boolean;
  max_bos_cycle: number;
  h1_ema200_filter: boolean;
  h4_ema_filter: boolean;
  ema_slope_filter: boolean;
  body_ratio_filter: boolean;
  session_filter: boolean;
  ema_stretch_filter: boolean; // 🛡️ Filter Regangan EMA (EMA Stretch > 3.5x ATR)
  bos_cycle_filter: boolean;   // 🛡️ Filter Siklus BOS (BOS Cycle >= 4)
}

// ── Constants ────────────────────────────────────────────────────────────────

const SPEED_MAP: Record<string, number> = {
  "1x": 400,
  "2x": 200,
  "3x": 100,
  "5x": 50,
  "10x": 20,
};

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const STRUCTURE_COLORS: Record<string, string> = {
  HH: "#22d3ee",
  HL: "#a3e635",
  LH: "#f97316",
  LL: "#ef4444",
  CHOCH: "#c084fc",
  BOS: "#facc15",
};

const DEFAULT_ENTRY_FILTER_PARAMS: EntryFilterParams = {
  entry_choch: true,
  entry_bos: true,
  entry_bos_cycle_2_plus: true,
  max_bos_cycle: 2,
  h1_ema200_filter: true,
  h4_ema_filter: true,
  ema_slope_filter: true,
  body_ratio_filter: true,
  session_filter: true,
  ema_stretch_filter: true,
  bos_cycle_filter: true,
};

function getSimpleMovingAverage(candles: ReplayCandle[], endIndex: number, period: number) {
  if (endIndex < period - 1) return null;

  let total = 0;
  for (let index = endIndex - period + 1; index <= endIndex; index += 1) {
    total += candles[index].close;
  }
  return total / period;
}

function getEntryStructureInfo(entryTime: number, structures: StructureEvent[]) {
  let latestType = "";
  let bosCycle = 0;

  for (const event of structures) {
    if (event.time > entryTime) break;
    const type = event.type?.toUpperCase() ?? "";
    if (type.includes("CHOCH")) {
      latestType = "CHOCH";
      bosCycle = 0;
    } else if (type.includes("BOS")) {
      latestType = "BOS";
      bosCycle += 1;
    }
  }

  return { latestType, bosCycle };
}

function getLastAcceptedLL(entryTime: number, structures: StructureEvent[]) {
  let lastAcceptedLL: number | null = null;
  for (const event of structures) {
    if (event.time > entryTime) break;
    if (event.type?.toUpperCase() === "LL") lastAcceptedLL = event.price;
  }
  return lastAcceptedLL;
}

function getLastAcceptedHH(entryTime: number, structures: StructureEvent[]) {
  let lastAcceptedHH: number | null = null;
  for (const event of structures) {
    if (event.time > entryTime) break;
    if (event.type?.toUpperCase() === "HH") lastAcceptedHH = event.price;
  }
  return lastAcceptedHH;
}

function getCandleAtOrBefore(candles: ReplayCandle[], time: number) {
  for (let index = candles.length - 1; index >= 0; index--) {
    if (candles[index].time <= time) return candles[index];
  }
  return null;
}

function getCandleIndexAtOrBefore(candles: ReplayCandle[], time: number) {
  for (let index = candles.length - 1; index >= 0; index--) {
    if (candles[index].time <= time) return index;
  }
  return -1;
}

function passesEAEntryFilters(
  trade: ReplayTrade,
  m15Candles: ReplayCandle[],
  h1Candles: ReplayCandle[],
  h4Candles: ReplayCandle[],
  params: EntryFilterParams,
) {
  const entryTime = trade.entry_time;
  if (entryTime === null) return false;

  const isBuy = trade.type.toUpperCase() === "BUY";
  const m15Index = getCandleIndexAtOrBefore(m15Candles, entryTime);
  // The EA evaluates rates[1], the last fully closed M15 bar, rather than the bar forming at entry.
  const m15Candle = m15Index > 0 ? m15Candles[m15Index - 1] : null;
  const h1Candle = getCandleAtOrBefore(h1Candles, entryTime);
  const h4Index = getCandleIndexAtOrBefore(h4Candles, entryTime);
  const h4Candle = h4Index >= 0 ? h4Candles[h4Index] : null;

  if (params.h1_ema200_filter) {
    if (h1Candle?.ema200 === null || h1Candle?.ema200 === undefined) return false;
    if (isBuy ? h1Candle.close <= h1Candle.ema200 : h1Candle.close >= h1Candle.ema200) return false;
  }

  if (params.h4_ema_filter && h4Candle?.ema200 !== null && h4Candle?.ema200 !== undefined) {
    // Matches the EA: MathMax(ema * 0.0025, 500 * _Point), where XAUUSD _Point is 0.01.
    const gapThreshold = Math.max(h4Candle.ema200 * 0.0025, 5);
    if (isBuy ? h4Candle.close <= h4Candle.ema200 + gapThreshold : h4Candle.close >= h4Candle.ema200 - gapThreshold) return false;
  }

  if (params.ema_slope_filter) {
    const previousCandle = m15Index > 1 ? m15Candles[m15Index - 2] : null;
    if (m15Candle?.ema200 === null || m15Candle?.ema200 === undefined || previousCandle?.ema200 === null || previousCandle?.ema200 === undefined) return false;
    if (isBuy ? m15Candle.ema200 <= previousCandle.ema200 : m15Candle.ema200 >= previousCandle.ema200) return false;
  }

  if (params.body_ratio_filter) {
    if (!m15Candle) return false;
    const range = m15Candle.high - m15Candle.low;
    if (range > 0) {
      const bodyRatio = Math.abs(m15Candle.close - m15Candle.open) / range;
      let effectiveMinBodyRatio = 0.4;

      // Mirror the EA's H4 stretch-aware body-ratio override. A moderate,
      // aligned H4 trend with 16-hour momentum lowers the threshold to 15%.
      const h4MomentumCandle = h4Index >= 4 ? h4Candles[h4Index - 4] : null;
      if (h4Candle?.ema200 !== null && h4Candle?.ema200 !== undefined && h4MomentumCandle) {
        const h4GapPercent = ((h4Candle.close - h4Candle.ema200) / h4Candle.ema200) * 100;
        const h4Momentum = h4Candle.close - h4MomentumCandle.close;
        const aligned = isBuy ? h4GapPercent > 0 : h4GapPercent < 0;
        const momentumAligned = isBuy ? h4Momentum > 2 : h4Momentum < -2;
        const isModerateTrend = Math.abs(h4GapPercent) >= 0.5 && Math.abs(h4GapPercent) <= 1.8;
        if (isModerateTrend && aligned && momentumAligned) effectiveMinBodyRatio = 0.15;
      }

      if (bodyRatio < effectiveMinBodyRatio) return false;
    }
  }

  if (params.session_filter && new Date(entryTime * 1000).getUTCHours() === 1) return false;

  return true;
}

function filterTradesByEntryParams(
  trades: ReplayTrade[],
  structures: StructureEvent[],
  params: EntryFilterParams,
  m15Candles: ReplayCandle[],
  h1Candles: ReplayCandle[],
  h4Candles: ReplayCandle[],
) {
  return trades.filter((trade) => {
    if (trade.status?.toUpperCase() !== "EXECUTED") return false;
    const entryTime = trade.entry_time;
    if (entryTime === null) return false;

    const { latestType, bosCycle } = getEntryStructureInfo(entryTime, structures);
    const matchesStructureFilter = latestType === "CHOCH"
      ? params.entry_choch
      : latestType === "BOS"
        && (bosCycle === 1
          ? params.entry_bos
          : bosCycle >= 2
            && params.entry_bos_cycle_2_plus
            && (params.max_bos_cycle === 0 || bosCycle <= params.max_bos_cycle));

    return matchesStructureFilter && passesEAEntryFilters(trade, m15Candles, h1Candles, h4Candles, params);
  });
}

function getReplayFilterRejectReason(
  trade: ReplayTrade,
  structures: StructureEvent[],
  m15Candles: ReplayCandle[],
  h1Candles: ReplayCandle[],
  h4Candles: ReplayCandle[],
  params: EntryFilterParams,
) {
  const entryTime = trade.entry_time;
  if (entryTime === null) return "Missing entry time";

  const { latestType, bosCycle } = getEntryStructureInfo(entryTime, structures);
  if (latestType === "CHOCH" && !params.entry_choch) return "CHoCH Filter (Disabled)";
  if (latestType === "BOS") {
    if (bosCycle === 1 && !params.entry_bos) return "BOS 1 Filter (Disabled)";
    if (bosCycle >= 2 && !params.entry_bos_cycle_2_plus) return "BOS 2+ Filter (Disabled)";
    if (params.max_bos_cycle > 0 && bosCycle > params.max_bos_cycle) return `Max BOS Cycle Limit (${params.max_bos_cycle})`;
  }

  const isBuy = trade.type.toUpperCase() === "BUY";
  const m15Index = getCandleIndexAtOrBefore(m15Candles, entryTime);
  const m15Candle = m15Index > 0 ? m15Candles[m15Index - 1] : null;
  const h1Candle = getCandleAtOrBefore(h1Candles, entryTime);
  const h4Candle = getCandleAtOrBefore(h4Candles, entryTime);

  if (params.session_filter && new Date(entryTime * 1000).getUTCHours() === 1) return "Session Filter (01:00 UTC)";
  if (params.h1_ema200_filter && (h1Candle?.ema200 === null || h1Candle?.ema200 === undefined || (isBuy ? h1Candle.close <= h1Candle.ema200 : h1Candle.close >= h1Candle.ema200))) return "H1 EMA200 Filter";
  if (params.h4_ema_filter && h4Candle?.ema200 !== null && h4Candle?.ema200 !== undefined) {
    const gapThreshold = Math.max(h4Candle.ema200 * 0.0025, 5);
    if (isBuy ? h4Candle.close <= h4Candle.ema200 + gapThreshold : h4Candle.close >= h4Candle.ema200 - gapThreshold) return "H4 EMA Filter";
  }
  if (params.ema_slope_filter) {
    const previousCandle = m15Index > 1 ? m15Candles[m15Index - 2] : null;
    if (m15Candle?.ema200 === null || m15Candle?.ema200 === undefined || previousCandle?.ema200 === null || previousCandle?.ema200 === undefined || (isBuy ? m15Candle.ema200 <= previousCandle.ema200 : m15Candle.ema200 >= previousCandle.ema200)) return "EMA Slope Filter";
  }
  if (params.body_ratio_filter && !passesEAEntryFilters({ ...trade }, m15Candles, h1Candles, h4Candles, { ...params, h1_ema200_filter: false, h4_ema_filter: false, ema_slope_filter: false, session_filter: false })) return "Body Ratio Filter";
  return trade.reject_reason || "Filter Rejection";
}

function createLocalStructureCandidateTrades(
  data: ReplayData,
  m15Candles: ReplayCandle[],
  h1Candles: ReplayCandle[],
  h4Candles: ReplayCandle[],
  params: EntryFilterParams,
): ReplayTrade[] {
  const closeByTime = new Map(data.candles.map((candle) => [candle.time, candle.close]));
  const existingTradeTimes = (data.trades || []).map((t) => t.entry_time ?? 0);

  return data.structures.flatMap((event) => {
    const typeUpper = event.type?.toUpperCase() ?? "";
    const isChoch = typeUpper.includes("CHOCH");
    const isBos = typeUpper.includes("BOS");
    if (!isChoch && !isBos) return [];

    // Avoid duplicating trades that already exist in DB data.trades (within 900 seconds / 1 candle)
    const hasExistingTrade = existingTradeTimes.some(
      (entryTime) => Math.abs(entryTime - event.time) <= 900
    );
    if (hasExistingTrade) return [];

    const entryPrice = closeByTime.get(event.time);
    const direction = event.direction?.toUpperCase() ?? "";
    if (entryPrice === undefined || (!direction.includes("BULL") && !direction.includes("BEAR"))) return [];

    const candidate: ReplayTrade = {
      ticket: -event.time,
      type: direction.includes("BULL") ? "BUY" : "SELL",
      status: "EXECUTED",
      reject_reason: null,
      entry_price: entryPrice,
      exit_price: null,
      sl: null,
      tp: null,
      net_profit: null,
      session: isChoch ? "CHOCH" : "BOS",
      entry_time: event.time,
      exit_time: null,
      lot_size: 0.01,
    };

    const { latestType, bosCycle } = getEntryStructureInfo(event.time, data.structures);
    const matchesStructureFilter = latestType === "CHOCH"
      ? params.entry_choch
      : latestType === "BOS"
        && (bosCycle === 1
          ? params.entry_bos
          : bosCycle >= 2
            && params.entry_bos_cycle_2_plus
            && (params.max_bos_cycle === 0 || bosCycle <= params.max_bos_cycle));

    const passesFilters = matchesStructureFilter && passesEAEntryFilters(candidate, m15Candles, h1Candles, h4Candles, params);
    return [{
      ...candidate,
      status: passesFilters ? "EXECUTED" : "REJECTED",
      reject_reason: passesFilters ? null : getReplayFilterRejectReason(candidate, data.structures, m15Candles, h1Candles, h4Candles, params),
    }];
  });
}

function getProcessedReplayTrades(
  data: ReplayData,
  structures: StructureEvent[],
  params: EntryFilterParams,
  m15Candles: ReplayCandle[],
  h1Candles: ReplayCandle[],
  h4Candles: ReplayCandle[],
  isLLMActive?: boolean,
): { executedTrades: ReplayTrade[]; rejectedTrades: ReplayTrade[] } {
  // When LLM mode is active, trades are governed exclusively by live LLM session decisions.
  // We completely isolate the session from static database EA backtest trades and EA candidate filters.
  if (isLLMActive) {
    return { executedTrades: [], rejectedTrades: [] };
  }

  const executedTrades: ReplayTrade[] = [];
  const rejectedTrades: ReplayTrade[] = [];

  const allCandidates = [
    ...data.trades,
    ...createLocalStructureCandidateTrades(data, m15Candles, h1Candles, h4Candles, params),
  ];

  for (const trade of allCandidates) {
    if (trade.entry_time === null) continue;

    if (trade.status?.toUpperCase() === "REJECTED") {
      rejectedTrades.push({
        ...trade,
        status: "REJECTED",
        reject_reason: trade.reject_reason || getReplayFilterRejectReason(trade, structures, m15Candles, h1Candles, h4Candles, params),
      });
      continue;
    }

    const { latestType, bosCycle } = getEntryStructureInfo(trade.entry_time, structures);
    const matchesStructureFilter = latestType === "CHOCH"
      ? params.entry_choch
      : latestType === "BOS"
        && (bosCycle === 1
          ? params.entry_bos
          : bosCycle >= 2
            && params.entry_bos_cycle_2_plus
            && (params.max_bos_cycle === 0 || bosCycle <= params.max_bos_cycle));

    const passesFilters = matchesStructureFilter && passesEAEntryFilters(trade, m15Candles, h1Candles, h4Candles, params);

    if (passesFilters) {
      executedTrades.push(trade);
    } else {
      rejectedTrades.push({
        ...trade,
        status: "REJECTED",
        reject_reason: getReplayFilterRejectReason(trade, structures, m15Candles, h1Candles, h4Candles, params),
      });
    }
  }

  return { executedTrades, rejectedTrades };
}

function EntryToggle({
  label,
  description,
  checked,
  onChange,
  disabled = false,
  disabledReason,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
  disabledReason?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-4 px-1 py-3 transition-opacity",
        disabled && "opacity-50"
      )}
      title={disabled ? disabledReason : undefined}
    >
      <div className="min-w-0">
        <div className="text-xs font-semibold text-slate-200">{label}</div>
        {description && <div className="mt-0.5 text-[10px] text-slate-500">{description}</div>}
        {disabled && disabledReason && (
          <div className="mt-0.5 text-[9px] text-amber-400/80">⚠️ {disabledReason}</div>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={onChange}
        disabled={disabled}
        className={cn(
          "relative h-5 w-9 shrink-0 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70",
          checked ? "border-cyan-400/50 bg-cyan-500/25" : "border-slate-700 bg-slate-900",
          disabled && "cursor-not-allowed"
        )}
      >
        <span
          className={cn(
            "absolute left-0.5 top-0.5 h-3.5 w-3.5 rounded-full transition-transform",
            checked ? "translate-x-4 bg-cyan-300" : "translate-x-0 bg-slate-500",
            disabled && "bg-slate-700"
          )}
        />
      </button>
    </div>
  );
}

function StructureSchemaMap({ params }: { params: EntryFilterParams }) {
  const nodes = [
    { label: "CHoCH", x: 48, y: 24, active: params.entry_choch },
    { label: "BOS 1", x: 104, y: 20, active: params.entry_bos },
    { label: "BOS 2", x: 160, y: 20, active: params.entry_bos_cycle_2_plus && (params.max_bos_cycle === 0 || params.max_bos_cycle >= 2) },
    { label: "BOS 3+", x: 216, y: 20, active: params.entry_bos_cycle_2_plus && (params.max_bos_cycle === 0 || params.max_bos_cycle >= 3) },
  ];

  return (
    <div className="relative h-28 overflow-hidden rounded-lg border border-slate-800/80 bg-slate-950/70">
      <div className="absolute inset-x-0 bottom-0 h-16 opacity-50 [background-image:linear-gradient(rgba(30,41,59,.55)_1px,transparent_1px),linear-gradient(90deg,rgba(30,41,59,.55)_1px,transparent_1px)] [background-size:28px_16px] [transform:perspective(180px)_rotateX(58deg)] [transform-origin:bottom]" />
      <svg viewBox="0 0 320 82" className="absolute left-1/2 top-3 h-[74px] w-[290px] -translate-x-1/2" aria-hidden="true">
        <path d="M20 58 L48 24 L76 48 L104 20 L132 46 L160 20 L188 46 L216 20 L244 46 L272 20" fill="none" stroke="rgb(51 65 85)" strokeWidth="1.5" />
        {nodes.map((node) => (
          <g key={node.label}>
            <text x={node.x} y="8" textAnchor="middle" className={cn("text-[8px] font-bold uppercase", node.active ? "fill-cyan-300" : "fill-slate-600")}>
              {node.label}
            </text>
            <circle cx={node.x} cy={node.y} r="4" className={node.active ? "fill-cyan-400" : "fill-slate-700"} />
            {node.active && <circle cx={node.x} cy={node.y} r="7" fill="none" stroke="rgb(34 211 238 / .22)" strokeWidth="3" />}
          </g>
        ))}
      </svg>
    </div>
  );
}

// ── API helper ───────────────────────────────────────────────────────────────

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function fetchReplayData(
  yearFrom: number, monthFrom: number,
  yearTo: number, monthTo: number,
  timeframe: string
): Promise<ReplayData> {
  const url = `${BASE_URL}/trading/replay?year_from=${yearFrom}&month_from=${monthFrom}&year_to=${yearTo}&month_to=${monthTo}&timeframe=${timeframe}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

// ── Strategy Info Tooltip ───────────────────────────────────────────────────

interface StrategyTooltipProps {
  fungsi: string;
  contoh: string;
}

function StrategyTooltip({ fungsi, contoh }: StrategyTooltipProps) {
  return (
    <div className="group relative inline-block ml-1.5 align-middle cursor-help">
      <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-slate-800 text-[10px] text-slate-400 font-bold border border-slate-700/80 hover:bg-slate-700 hover:text-cyan-400 transition-colors">
        ?
      </span>
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 hidden group-hover:block bg-slate-950/95 border border-slate-800 rounded-xl text-[11px] text-slate-300 shadow-2xl backdrop-blur-md z-30 transition-all pointer-events-none">
        <div className="font-bold text-cyan-400 mb-1">Fungsi:</div>
        <div className="mb-2 leading-relaxed text-slate-200">{fungsi}</div>
        <div className="font-bold text-purple-400 mb-0.5">Contoh:</div>
        <div className="leading-relaxed text-slate-400">{contoh}</div>
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-950/95" />
      </div>
    </div>
  );
}

// ── Custom Dropdown Component ────────────────────────────────────────────────

const SELECT_ACCENTS = {
  blue: { border: "var(--neon-blue)", bg: "rgba(59,130,246,0.2)", text: "#93c5fd", shadow: "rgba(59,130,246,0.25)" },
  purple: { border: "var(--neon-purple)", bg: "rgba(139,92,246,0.2)", text: "#c4b5fd", shadow: "rgba(139,92,246,0.25)" },
};

interface CustomSelectProps<T> {
  value: T;
  onChange: (val: T) => void;
  options: T[];
  getLabel: (val: T) => string;
  accent: "blue" | "purple";
  className?: string;
}

function CustomSelect<T extends string | number>({
  value,
  onChange,
  options,
  getLabel,
  accent,
  className,
}: CustomSelectProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  const c = SELECT_ACCENTS[accent];

  return (
    <div ref={containerRef} className={cn("relative select-none z-[100] group", className)}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1.5 border rounded-lg text-xs font-semibold text-white transition-all cursor-pointer whitespace-nowrap outline-none",
          className ? "w-full justify-between" : ""
        )}
        style={{
          backgroundColor: c.bg,
          borderColor: c.border,
          boxShadow: `0 0 12px ${c.shadow}`,
        }}
      >
        <span>{getLabel(value)}</span>
        <span className="ml-0.5 text-[9px] opacity-80">▾</span>
      </button>

      {isOpen && (
        <div
          className="absolute top-[calc(100%+6px)] right-0 min-w-[140px] bg-[var(--bg-surface,#0f172a)] border border-[var(--glass-border,rgba(255,255,255,0.1))] rounded-[10px] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.5)] z-[110]"
        >
          {options.map((opt) => {
            const active = opt === value;
            return (
              <div
                key={opt}
                onClick={() => {
                  onChange(opt);
                  setIsOpen(false);
                }}
                className="px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer text-[var(--text-secondary,#cbd5e1)] hover:bg-[var(--bg-elevated,rgba(255,255,255,0.05))] hover:text-white"
                style={
                  active
                    ? {
                      backgroundColor: c.bg,
                      borderColor: c.border,
                      color: c.text,
                      boxShadow: `0 0 12px ${c.shadow}`,
                    }
                    : undefined
                }
              >
                {getLabel(opt)}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Component ────────────────────────────────────────────────────────────────

const getActualLotSize = (t: any): number => {
  const entry = t.entry_price ?? 0;
  const exit = t.exit_price ?? 0;
  const netProfit = t.net_profit ?? 0;
  const priceDiff = Math.abs(exit - entry);

  if (priceDiff > 0.01) {
    const calculatedLot = Math.abs(netProfit) / (priceDiff * 100);
    const roundedLot = Math.round(calculatedLot * 100) / 100;
    if (roundedLot >= 0.01 && roundedLot <= 50.0) {
      return roundedLot;
    }
  }
  return t.lot_size ?? 0.05;
};

// ponytail: flat object params with defaults — no class, no registry
interface StrategyParams {
  trailing_distance: number;   // USD, default 30.00 (3000 poin)
  tp_trigger: number;          // USD, default 10.00 (1000 poin)
  tp_ekspansi: number;         // USD, default 20.00 (2000 poin)
  max_ekspansi: number;        // 0 = unlimited
  enable_breakeven: boolean;
  breakeven_trigger: number;   // USD profit from entry, default 15.00 (1500 poin)
  breakeven_buffer: number;    // USD above entry, default 1.00 (100 poin)
  lot_override: number;        // 0.00 = Auto
  initial_tp_dist: number;     // USD, default 30.00 (3000 poin)
  sl_safety_buffer: number;    // USD, default 10.00 (1000 poin)
  force_24h_close: boolean;
  initial_balance: number;     // USD, default 1000.00
  // ATR-based adaptive SL/TP
  use_atr_sltp: boolean;       // toggle ATR mode
  atr_period: number;          // ATR lookback, default 14
  atr_sl_multiplier: number;   // SL = ATR * multiplier, default 1.5
  atr_tp_multiplier: number;   // TP = ATR * multiplier, default 2.0
  show_supply_demand: boolean; // Visual Supply & Demand (Resistance & Support) Zones
  show_liquidity_pools: boolean; // Visual Buy-Side (BSL) & Sell-Side (SSL) Liquidity Pools
}

export const DEFAULT_STRATEGY_PARAMS: StrategyParams = {
  trailing_distance: 30.00,
  tp_trigger: 10.00,
  tp_ekspansi: 20.00,
  max_ekspansi: 0,
  enable_breakeven: false,
  breakeven_trigger: 15.00,
  breakeven_buffer: 1.00,
  lot_override: 0.05,
  initial_tp_dist: 30.00,
  sl_safety_buffer: 10.00,
  force_24h_close: false,
  initial_balance: 1000.00,
  use_atr_sltp: false,
  atr_period: 14,
  atr_sl_multiplier: 1.5,
  atr_tp_multiplier: 2.0,
  show_supply_demand: true,
  show_liquidity_pools: true,
};

const INITIAL_BALANCE = 1000.00;

// Calculate ATR (Average True Range) from candles up to a given time.
// Returns the ATR value in price units (e.g. $ for XAUUSD), or null if
// there aren't enough candles.
const calculateATR = (
  candles: any[],
  upToTime: number,
  period: number = 14,
): number | null => {
  const prior = candles.filter(c => c.time <= upToTime);
  if (prior.length < period + 1) return null;

  const trueRanges: number[] = [];
  for (let i = 1; i < prior.length; i++) {
    const c = prior[i];
    const prevClose = prior[i - 1].close;
    const tr = Math.max(
      c.high - c.low,
      Math.abs(c.high - prevClose),
      Math.abs(c.low - prevClose),
    );
    trueRanges.push(tr);
  }
  if (trueRanges.length < period) return null;

  // Simple average of the last `period` true ranges (Wilder smoothing is
  // overkill for a replay tool — ponytail: plain average is fine).
  const slice = trueRanges.slice(-period);
  const sum = slice.reduce((acc, v) => acc + v, 0);
  return sum / period;
};

/**
 * Calculate active and historical Supply & Demand zones from price structure.
 * - Supply Zone: Originates from Swing High (HH/LH) peak or Bearish Displacement base.
 * - Demand Zone: Originates from Swing Low (LL/HL) valley or Bullish Displacement base.
 * Extends forward until mitigated by subsequent price action.
 */
export function calculateSupplyDemandZones(
  candles: ReplayCandle[],
  structures: StructureEvent[],
  currentCandleTime: number,
  lookbackCount: number = 80,
): SupplyDemandZoneItem[] {
  if (!candles || candles.length === 0 || !structures || structures.length === 0) return [];

  const rawZones: SupplyDemandZoneItem[] = [];
  const maxTime = currentCandleTime;

  // Filter structure events up to current time
  const relevantEvents = structures
    .filter((s) => s.time <= maxTime)
    .slice(-lookbackCount);

  for (const s of relevantEvents) {
    const typeUpper = (s.type || "").toUpperCase();
    const dirUpper = (s.direction || "").toUpperCase();

    const isHhLh = typeUpper.includes("HH") || typeUpper.includes("LH");
    const isHlLl = typeUpper.includes("HL") || typeUpper.includes("LL");
    const isChochBos = typeUpper.includes("CHOCH") || typeUpper.includes("BOS");

    if (!isHhLh && !isHlLl && !isChochBos) continue;

    const isSupply = isHhLh || (isChochBos && dirUpper.includes("BEAR"));
    const isDemand = isHlLl || (isChochBos && dirUpper.includes("BULL"));
    if (!isSupply && !isDemand) continue;

    // Find closest origin candle by timestamp
    let originCandle: ReplayCandle | null = null;
    let candleIdx = -1;

    for (let i = 0; i < candles.length; i++) {
      if (Math.abs(candles[i].time - s.time) <= 1800) {
        originCandle = candles[i];
        candleIdx = i;
        break;
      }
      if (candles[i].time > s.time) {
        candleIdx = Math.max(0, i - 1);
        originCandle = candles[candleIdx];
        break;
      }
    }

    if (!originCandle) continue;

    const startTime = s.time;
    let topPrice = 0;
    let bottomPrice = 0;
    const type: "SUPPLY" | "DEMAND" = isSupply ? "SUPPLY" : "DEMAND";

    if (isSupply) {
      // Supply Zone: Originates from swing high peak down to candle body
      topPrice = Math.max(originCandle.high, s.price);
      const bodyMax = Math.max(originCandle.open, originCandle.close);
      const zoneThickness = Math.max(1.8, (originCandle.high - originCandle.low) * 0.45);
      bottomPrice = Math.max(originCandle.low, Math.min(bodyMax, topPrice - zoneThickness));
      if (topPrice - bottomPrice < 1.2) bottomPrice = topPrice - 1.8;
    } else {
      // Demand Zone: Originates from swing low valley up to candle body
      bottomPrice = Math.min(originCandle.low, s.price);
      const bodyMin = Math.min(originCandle.open, originCandle.close);
      const zoneThickness = Math.max(1.8, (originCandle.high - originCandle.low) * 0.45);
      topPrice = Math.min(originCandle.high, Math.max(bodyMin, bottomPrice + zoneThickness));
      if (topPrice - bottomPrice < 1.2) topPrice = bottomPrice + 1.8;
    }

    // Check mitigation by subsequent candles up to current playhead
    let isMitigated = false;
    let endTime = maxTime;

    const startScanIdx = candleIdx + 1;
    for (let i = startScanIdx; i < candles.length; i++) {
      const c = candles[i];
      if (c.time > maxTime) break;

      if (isSupply) {
        if (c.high > topPrice) {
          isMitigated = true;
          endTime = c.time;
          break;
        }
      } else {
        if (c.low < bottomPrice) {
          isMitigated = true;
          endTime = c.time;
          break;
        }
      }
    }

    rawZones.push({
      id: `${type}-${startTime}-${topPrice.toFixed(1)}`,
      type,
      topPrice,
      bottomPrice,
      startTime,
      endTime,
      isMitigated,
      label: `${type} [${bottomPrice.toFixed(1)} - ${topPrice.toFixed(1)}]`,
    });
  }

  // De-duplicate overlapping zones at nearly identical price levels (within 0.6 points)
  const uniqueZones: SupplyDemandZoneItem[] = [];
  const sorted = [...rawZones].sort((a, b) => b.startTime - a.startTime); // newest first

  for (const zone of sorted) {
    const isDuplicate = uniqueZones.some(
      (existing) =>
        existing.type === zone.type &&
        Math.abs(existing.topPrice - zone.topPrice) <= 0.6 &&
        Math.abs(existing.bottomPrice - zone.bottomPrice) <= 0.6
    );
    if (!isDuplicate) {
      uniqueZones.push(zone);
    }
  }

  return uniqueZones.reverse();
}

/**
 * Calculate active and swept Buy-Side Liquidity (BSL) and Sell-Side Liquidity (SSL) pools.
 * - BSL: Located at previous Swing Highs (HH/LH) & Equal Highs (EQH) where Buy Stops & Short SLs reside.
 * - SSL: Located at previous Swing Lows (LL/HL) & Equal Lows (EQL) where Sell Stops & Long SLs reside.
 */
export function calculateLiquidityPools(
  candles: ReplayCandle[],
  structures: StructureEvent[],
  currentCandleTime: number,
  lookbackCount: number = 80,
): LiquidityPoolItem[] {
  if (!candles || candles.length === 0 || !structures || structures.length === 0) return [];

  const rawPools: LiquidityPoolItem[] = [];
  const maxTime = currentCandleTime;

  const relevantEvents = structures
    .filter((s) => s.time <= maxTime)
    .slice(-lookbackCount);

  for (let idx = 0; idx < relevantEvents.length; idx++) {
    const s = relevantEvents[idx];
    const typeUpper = (s.type || "").toUpperCase();

    const isHigh = typeUpper.includes("HH") || typeUpper.includes("LH");
    const isLow = typeUpper.includes("LL") || typeUpper.includes("HL");
    if (!isHigh && !isLow) continue;

    const poolType: "BSL" | "SSL" = isHigh ? "BSL" : "SSL";
    const price = s.price;
    const startTime = s.time;

    // Check if there is an Equal High / Equal Low within 0.30 points
    const hasEqualLevel = relevantEvents.some(
      (other, oIdx) =>
        oIdx !== idx &&
        ((isHigh && (other.type?.toUpperCase().includes("HH") || other.type?.toUpperCase().includes("LH"))) ||
         (isLow && (other.type?.toUpperCase().includes("LL") || other.type?.toUpperCase().includes("HL")))) &&
        Math.abs(other.price - price) <= 0.30 &&
        Math.abs(other.time - startTime) > 1800
    );

    // Find candle index where this structure formed
    const candleIdx = candles.findIndex((c) => Math.abs(c.time - startTime) <= 1800 || c.time >= startTime);
    const startScanIdx = candleIdx >= 0 ? candleIdx + 1 : 0;

    // Check if price has swept this liquidity level
    let isSwept = false;
    let endTime = maxTime;

    for (let i = startScanIdx; i < candles.length; i++) {
      const c = candles[i];
      if (c.time > maxTime) break;

      if (isHigh) {
        if (c.high >= price + 0.15) {
          isSwept = true;
          endTime = c.time;
          break;
        }
      } else {
        if (c.low <= price - 0.15) {
          isSwept = true;
          endTime = c.time;
          break;
        }
      }
    }

    const labelPrefix = hasEqualLevel ? (isHigh ? "🎯 EQH" : "🎯 EQL") : (isHigh ? "🎯 BSL" : "🎯 SSL");
    rawPools.push({
      id: `${poolType}-${startTime}-${price.toFixed(2)}`,
      type: poolType,
      price,
      startTime,
      endTime,
      isSwept,
      label: `${labelPrefix} [${price.toFixed(2)}]`,
    });
  }

  // De-duplicate pools within 0.35 points, keeping the most recent
  const uniquePools: LiquidityPoolItem[] = [];
  const sorted = [...rawPools].sort((a, b) => b.startTime - a.startTime);

  for (const pool of sorted) {
    const isDup = uniquePools.some(
      (existing) =>
        existing.type === pool.type &&
        Math.abs(existing.price - pool.price) <= 0.35
    );
    if (!isDup) {
      uniquePools.push(pool);
    }
  }

  return uniquePools.reverse();
}

const simulateTrailingSLTP = (
  t: any,
  candles: any[],
  currentCandleTime: number,
  structures: StructureEvent[],
  params: StrategyParams = DEFAULT_STRATEGY_PARAMS
): {
  initialSL: number;
  initialTP: number;
  sl: number | null;
  tp: number | null;
  beTriggered: boolean;
  isClosedSimulated: boolean;
  exitPriceSimulated: number | null;
  exitTimeSimulated: number | null;
  expansionCount: number;
} => {
  const typeLower = (t.type ?? "").toLowerCase();
  const entryPrice = t.entry_price ?? 0;

  // ATR-based adaptive SL/TP: distance scales with volatility so it stays
  // proportional whether price is at 1000 or 5000.
  let initialSL: number;
  let initialTP: number;
  if (params.use_atr_sltp) {
    const atr = calculateATR(candles, t.entry_time ?? 0, params.atr_period);
    if (atr !== null && atr > 0) {
      const slDist = atr * params.atr_sl_multiplier;
      const tpDist = atr * params.atr_tp_multiplier;
      initialSL = typeLower === "buy" ? entryPrice - slDist : entryPrice + slDist;
      initialTP = typeLower === "buy" ? entryPrice + tpDist : entryPrice - tpDist;
    } else {
      // Fallback if not enough candles for ATR
      const slDistance = Math.max(15.00, Math.min(30.00, Math.abs(entryPrice - (typeLower === "buy" ? entryPrice - params.trailing_distance : entryPrice + params.trailing_distance))));
      initialSL = typeLower === "buy" ? entryPrice - slDistance : entryPrice + slDistance;
      initialTP = params.initial_tp_dist > 0
        ? (typeLower === "buy" ? entryPrice + params.initial_tp_dist : entryPrice - params.initial_tp_dist)
        : (typeLower === "buy" ? entryPrice + 30.00 : entryPrice - 30.00);
    }
  } else {
    const structuralSL = (typeLower === "buy"
      ? getLastAcceptedLL(t.entry_time ?? 0, structures)
      : t.sl) ?? (typeLower === "buy"
      ? entryPrice - params.trailing_distance
      : entryPrice + params.trailing_distance);
    const bufferedSL = typeLower === "buy"
      ? structuralSL - params.sl_safety_buffer
      : structuralSL + params.sl_safety_buffer;
    const slDistance = Math.max(15.00, Math.min(30.00, Math.abs(entryPrice - bufferedSL)));
    initialSL = typeLower === "buy" ? entryPrice - slDistance : entryPrice + slDistance;

    initialTP = params.initial_tp_dist > 0
      ? (typeLower === "buy" ? entryPrice + params.initial_tp_dist : entryPrice - params.initial_tp_dist)
      : (t.tp ?? (typeLower === "buy" ? entryPrice + 30.00 : entryPrice - 30.00));
  }

  let currentSL = initialSL;
  let currentTP = initialTP;

  // Compute effective Break-Even buffer
  let effectiveBuffer = params.breakeven_buffer;

  const activeCandles = candles.filter(c => c.time >= (t.entry_time ?? 0) && c.time <= currentCandleTime);
  let expansionCount = 0;
  let beTriggered = false;
  let isClosedSimulated = false;
  let exitPriceSimulated: number | null = null;
  let exitTimeSimulated: number | null = null;

  for (const c of activeCandles) {
    const price = c.close;

    // Force 24h Close
    if (params.force_24h_close && (c.time - (t.entry_time ?? 0)) >= 86400) {
      isClosedSimulated = true;
      exitPriceSimulated = price;
      exitTimeSimulated = c.time;
      break;
    }

    if (typeLower === "buy") {
      // 1. Check if stopped out by SL first
      if (c.low <= currentSL) {
        isClosedSimulated = true;
        exitPriceSimulated = currentSL;
        exitTimeSimulated = c.time;
        break;
      }

      // 2. Check if hits TP
      if (currentTP !== null && c.high >= currentTP) {
        isClosedSimulated = true;
        exitPriceSimulated = currentTP;
        exitTimeSimulated = c.time;
        break;
      }

      // Check if BE is triggered using candle High price
      if (params.enable_breakeven && c.high - entryPrice >= params.breakeven_trigger) {
        beTriggered = true;
      }

      // Trailing SL
      const targetSL = price - params.trailing_distance;
      const minSL = entryPrice - params.trailing_distance;
      const maxSL = price - 1.50;
      let newSL = Math.max(minSL, Math.min(maxSL, targetSL));

      // Break-even floor: once triggered, SL cannot go below entry + effectiveBuffer
      if (beTriggered) {
        newSL = Math.max(newSL, entryPrice + effectiveBuffer);
      }

      newSL = Math.max(currentSL, newSL);

      if (Math.abs(newSL - currentSL) >= 0.10) currentSL = newSL;

      // TP expansion (respect max_ekspansi limit)
      const canExpand = params.max_ekspansi === 0 || expansionCount < params.max_ekspansi;
      if (canExpand && currentTP - price <= params.tp_trigger) {
        const expandedTP = price + params.tp_ekspansi;
        if (expandedTP > currentTP) {
          currentTP = expandedTP;
          expansionCount++;
        }
      }
    } else if (typeLower === "sell") {
      // 1. Check if stopped out by SL first
      if (c.high >= currentSL) {
        isClosedSimulated = true;
        exitPriceSimulated = currentSL;
        exitTimeSimulated = c.time;
        break;
      }

      // 2. Check if hits TP
      if (currentTP !== null && c.low <= currentTP) {
        isClosedSimulated = true;
        exitPriceSimulated = currentTP;
        exitTimeSimulated = c.time;
        break;
      }

      // Check if BE is triggered using candle Low price
      if (params.enable_breakeven && entryPrice - c.low >= params.breakeven_trigger) {
        beTriggered = true;
      }

      // Trailing SL
      const targetSL = price + params.trailing_distance;
      const minSL = entryPrice + params.trailing_distance;
      const maxSL = price + 1.50;
      let newSL = Math.min(minSL, Math.max(maxSL, targetSL));

      // Break-even floor: once triggered, SL cannot go above entry - effectiveBuffer
      if (beTriggered) {
        newSL = Math.min(newSL, entryPrice - effectiveBuffer);
      }

      newSL = Math.min(currentSL, newSL);

      if (Math.abs(newSL - currentSL) >= 0.10) currentSL = newSL;

      // TP expansion (respect max_ekspansi limit)
      const canExpand = params.max_ekspansi === 0 || expansionCount < params.max_ekspansi;
      if (canExpand && price - currentTP <= params.tp_trigger) {
        const expandedTP = price - params.tp_ekspansi;
        if (expandedTP < currentTP) {
          currentTP = expandedTP;
          expansionCount++;
        }
      }
    }
  }

  return {
    initialSL,
    initialTP,
    sl: currentSL,
    tp: currentTP,
    beTriggered,
    isClosedSimulated,
    exitPriceSimulated,
    exitTimeSimulated,
    expansionCount,
  };
};

export default function ReplayTrades() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const emaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ma20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ma50SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<any> | null>(null);
  const structurePrimitiveRef = useRef<StructureLinesPrimitive | null>(null);
  const tradesPrimitiveRef = useRef<TradesOverlayPrimitive | null>(null);
  const sessionZonesPrimitiveRef = useRef<SessionZonesPrimitive | null>(null);
  const supplyDemandPrimitiveRef = useRef<SupplyDemandPrimitive | null>(null);
  const liquidityPoolsPrimitiveRef = useRef<LiquidityPoolsPrimitive | null>(null);
  const candleTimeArrayRef = useRef<number[]>([]);
  const candleTimeMapRef = useRef<Map<number, ReplayCandle>>(new Map());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Filter state
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;
  const [dbMonths, setDbMonths] = useState<{ year: number; month: number }[]>([]);
  const [yearFrom, setYearFrom] = useState(currentYear);
  const [monthFrom, setMonthFrom] = useState(1);
  const [yearTo, setYearTo] = useState(currentYear);
  const [monthTo, setMonthTo] = useState(currentMonth);
  const [activeTimeframe, setActiveTimeframe] = useState("M15");

  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [allReplayData, setAllReplayData] = useState<Record<string, ReplayData>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadProgress, setLoadProgress] = useState({
    visible: false,
    percent: 0,
    step: "",
  });

  const [hoveredInfo, setHoveredInfo] = useState<{
    time: string | null;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    hoveredPrice: number | null;
  } | null>(null);

  // ── Playback state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [speed, setSpeed] = useState<string>("1x");

  // ── Strategy params state
  const [strategyParams, setStrategyParams] = useState({ ...DEFAULT_STRATEGY_PARAMS });
  const [entryFilterParams, setEntryFilterParams] = useState({ ...DEFAULT_ENTRY_FILTER_PARAMS });
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [scenarioName, setScenarioName] = useState("");
  const [isStrategyPanelOpen, setIsStrategyPanelOpen] = useState(false);
  const [initialBalanceInput, setInitialBalanceInput] = useState(String(DEFAULT_STRATEGY_PARAMS.initial_balance));
  const [maxBosCycleInput, setMaxBosCycleInput] = useState(String(DEFAULT_ENTRY_FILTER_PARAMS.max_bos_cycle));
  const [lotSizeInput, setLotSizeInput] = useState(String(DEFAULT_STRATEGY_PARAMS.lot_override));
  const [atrPeriodInput, setAtrPeriodInput] = useState(String(DEFAULT_STRATEGY_PARAMS.atr_period));
  const [atrSlMultInput, setAtrSlMultInput] = useState(String(DEFAULT_STRATEGY_PARAMS.atr_sl_multiplier));
  const [atrTpMultInput, setAtrTpMultInput] = useState(String(DEFAULT_STRATEGY_PARAMS.atr_tp_multiplier));
  // LLM trade setup (replay)
  const [useLLMSetup, setUseLLMSetup] = useState(false);
  const [llmRecommendation, setLlmRecommendation] = useState<any | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  // Decision engine toggle: "rule" (SmartRuleEngine) or "llm" (LLMDecisionEngine)
  const [decisionEngine, setDecisionEngine] = useState<"rule" | "llm">("rule");
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  // LLM-executed positions — kept separate so they survive replay re-renders.
  const [llmPositions, setLlmPositions] = useState<any[]>([]);
  const [isMa20Visible, setIsMa20Visible] = useState(true);
  const [isMa50Visible, setIsMa50Visible] = useState(true);

  // ── Position Planner (TradingView Style)
  const [plannerTool, setPlannerTool] = useState<"none" | "long" | "short">("none");
  const [selectedRrRatio, setSelectedRrRatio] = useState<number>(2.0);
  const [activePlanner, setActivePlanner] = useState<PositionPlanner | null>(null);

  const plannerToolRef = useRef<"none" | "long" | "short">("none");
  const selectedRrRatioRef = useRef<number>(2.0);
  const replayDataRef = useRef<ReplayData | null>(null);
  const allReplayDataRef = useRef<Record<string, ReplayData>>({});
  const strategyParamsRef = useRef<StrategyParams>(DEFAULT_STRATEGY_PARAMS);
  const activePlannerRef = useRef<PositionPlanner | null>(null);
  const currentIndexRef = useRef<number>(0);

  useEffect(() => {
    currentIndexRef.current = currentIndex;
  }, [currentIndex]);

  useEffect(() => {
    plannerToolRef.current = plannerTool;
  }, [plannerTool]);

  useEffect(() => {
    selectedRrRatioRef.current = selectedRrRatio;
  }, [selectedRrRatio]);

  useEffect(() => {
    replayDataRef.current = replayData;
  }, [replayData]);

  useEffect(() => {
    allReplayDataRef.current = allReplayData;
  }, [allReplayData]);

  useEffect(() => {
    strategyParamsRef.current = strategyParams;
  }, [strategyParams]);

  useEffect(() => {
    activePlannerRef.current = activePlanner;
  }, [activePlanner]);

  // ── Position Planner Input Strings (Free delete & typing) ────────────────────
  const [plannerEntryInput, setPlannerEntryInput] = useState("");
  const [plannerTpInput, setPlannerTpInput] = useState("");
  const [plannerSlInput, setPlannerSlInput] = useState("");
  const [plannerLotInput, setPlannerLotInput] = useState("");
  const [plannerRiskInput, setPlannerRiskInput] = useState("");

  useEffect(() => {
    if (activePlanner) {
      if (document.activeElement?.getAttribute("data-planner-input") !== "entry") {
        setPlannerEntryInput(activePlanner.entryPrice.toFixed(2));
      }
      if (document.activeElement?.getAttribute("data-planner-input") !== "tp") {
        setPlannerTpInput(activePlanner.tpPrice.toFixed(2));
      }
      if (document.activeElement?.getAttribute("data-planner-input") !== "sl") {
        setPlannerSlInput(activePlanner.slPrice.toFixed(2));
      }
      if (document.activeElement?.getAttribute("data-planner-input") !== "lot") {
        setPlannerLotInput(activePlanner.lotSize.toFixed(2));
      }
      if (document.activeElement?.getAttribute("data-planner-input") !== "risk") {
        setPlannerRiskInput(String(activePlanner.riskAmountUsd || 100));
      }
    }
  }, [
    activePlanner?.entryPrice,
    activePlanner?.tpPrice,
    activePlanner?.slPrice,
    activePlanner?.lotSize,
    activePlanner?.riskAmountUsd,
    activePlanner?.type,
  ]);

  // ── Draggable Floating Panels State ─────────────────────────────────────────
  const [toolbarPos, setToolbarPos] = useState<{ x: number; y: number }>({ x: 24, y: 64 });
  const [hudCardPos, setHudCardPos] = useState<{ x: number; y: number }>({ x: 24, y: 124 });
  const [isHudMinimized, setIsHudMinimized] = useState(false);

  const isDraggingToolbarRef = useRef(false);
  const toolbarDragOffsetRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  const handleToolbarMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    isDraggingToolbarRef.current = true;
    toolbarDragOffsetRef.current = {
      x: e.clientX - toolbarPos.x,
      y: e.clientY - toolbarPos.y,
    };
    e.stopPropagation();
  };

  const isDraggingHudRef = useRef(false);
  const hudDragOffsetRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  const handleHudMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    isDraggingHudRef.current = true;
    hudDragOffsetRef.current = {
      x: e.clientX - hudCardPos.x,
      y: e.clientY - hudCardPos.y,
    };
    e.stopPropagation();
  };

  useEffect(() => {
    const handleGlobalMouseMove = (e: MouseEvent) => {
      if (isDraggingToolbarRef.current) {
        const newX = Math.max(10, Math.min(window.innerWidth - 260, e.clientX - toolbarDragOffsetRef.current.x));
        const newY = Math.max(10, Math.min(window.innerHeight - 60, e.clientY - toolbarDragOffsetRef.current.y));
        setToolbarPos({ x: newX, y: newY });
      }
      if (isDraggingHudRef.current) {
        const newX = Math.max(10, Math.min(window.innerWidth - 380, e.clientX - hudDragOffsetRef.current.x));
        const newY = Math.max(10, Math.min(window.innerHeight - 80, e.clientY - hudDragOffsetRef.current.y));
        setHudCardPos({ x: newX, y: newY });
      }
    };

    const handleGlobalMouseUp = () => {
      isDraggingToolbarRef.current = false;
      isDraggingHudRef.current = false;
    };

    window.addEventListener("mousemove", handleGlobalMouseMove);
    window.addEventListener("mouseup", handleGlobalMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleGlobalMouseMove);
      window.removeEventListener("mouseup", handleGlobalMouseUp);
    };
  }, [toolbarPos, hudCardPos]);

  // ── Position Planner Interactive Helpers ─────────────────────────────────────
  const updatePlannerEntry = (newEntry: number) => {
    setActivePlanner((prev) => {
      if (!prev) return null;
      const slDist = Math.abs(prev.entryPrice - prev.slPrice);
      const tpDist = Math.abs(prev.tpPrice - prev.entryPrice);
      const newSL = prev.type === "long" ? newEntry - slDist : newEntry + slDist;
      const newTP = prev.type === "long" ? newEntry + tpDist : newEntry - tpDist;
      return {
        ...prev,
        entryPrice: newEntry,
        slPrice: newSL,
        tpPrice: newTP,
      };
    });
  };

  const updatePlannerSLPrice = (newSL: number) => {
    setActivePlanner((prev) => {
      if (!prev) return null;
      const slDist = Math.max(1, Math.abs(prev.entryPrice - newSL));
      const validSL = prev.type === "long" ? prev.entryPrice - slDist : prev.entryPrice + slDist;
      // Keep TP fixed in place when SL is moved!
      const tpDist = Math.abs(prev.tpPrice - prev.entryPrice);
      const newRR = Number((tpDist / slDist).toFixed(2));
      let newLot = prev.lotSize;
      if (prev.isAutoRisk && prev.riskAmountUsd) {
        newLot = Math.max(0.01, Math.min(50, Number((prev.riskAmountUsd / (slDist * 100)).toFixed(2))));
      }
      return {
        ...prev,
        slPrice: validSL,
        riskRewardRatio: newRR,
        lotSize: newLot,
      };
    });
  };

  const adjustPlannerSLDistance = (deltaUsd: number) => {
    setActivePlanner((prev) => {
      if (!prev) return null;
      const currentSlDist = Math.abs(prev.entryPrice - prev.slPrice);
      const newSlDist = Math.max(2, currentSlDist + deltaUsd);
      const newSL = prev.type === "long" ? prev.entryPrice - newSlDist : prev.entryPrice + newSlDist;
      // Keep TP fixed in place!
      const tpDist = Math.abs(prev.tpPrice - prev.entryPrice);
      const newRR = Number((tpDist / newSlDist).toFixed(2));
      let newLot = prev.lotSize;
      if (prev.isAutoRisk && prev.riskAmountUsd) {
        newLot = Math.max(0.01, Math.min(50, Number((prev.riskAmountUsd / (newSlDist * 100)).toFixed(2))));
      }
      return {
        ...prev,
        slPrice: newSL,
        riskRewardRatio: newRR,
        lotSize: newLot,
      };
    });
  };

  const updatePlannerTPPrice = (newTP: number) => {
    setActivePlanner((prev) => {
      if (!prev) return null;
      const slDist = Math.max(1, Math.abs(prev.entryPrice - prev.slPrice));
      const tpDist = Math.max(1, Math.abs(newTP - prev.entryPrice));
      const validTP = prev.type === "long" ? prev.entryPrice + tpDist : prev.entryPrice - tpDist;
      const newRR = Number((tpDist / slDist).toFixed(2));
      return {
        ...prev,
        tpPrice: validTP,
        riskRewardRatio: newRR,
      };
    });
  };

  const adjustPlannerTPDistance = (deltaUsd: number) => {
    setActivePlanner((prev) => {
      if (!prev) return null;
      const slDist = Math.max(1, Math.abs(prev.entryPrice - prev.slPrice));
      const currentTpDist = Math.abs(prev.tpPrice - prev.entryPrice);
      const newTpDist = Math.max(2, currentTpDist + deltaUsd);
      const newTP = prev.type === "long" ? prev.entryPrice + newTpDist : prev.entryPrice - newTpDist;
      const newRR = Number((newTpDist / slDist).toFixed(2));
      return {
        ...prev,
        tpPrice: newTP,
        riskRewardRatio: newRR,
      };
    });
  };

  const snapPlannerStructure = () => {
    setActivePlanner((prev) => {
      if (!prev || !replayData) return prev;
      const currentStructures = replayData.structures ?? [];
      if (prev.type === "long") {
        const lastLL = getLastAcceptedLL(prev.entryTime, currentStructures);
        if (lastLL !== null) {
          const slPrice = lastLL - 2.00;
          const slDist = Math.max(5, prev.entryPrice - slPrice);
          const finalSL = prev.entryPrice - slDist;
          const finalTP = prev.entryPrice + (slDist * prev.riskRewardRatio);
          let newLot = prev.lotSize;
          if (prev.isAutoRisk && prev.riskAmountUsd) {
            newLot = Math.max(0.01, Math.min(50, Number((prev.riskAmountUsd / (slDist * 100)).toFixed(2))));
          }
          return { ...prev, slPrice: finalSL, tpPrice: finalTP, lotSize: newLot };
        }
      } else {
        const lastHH = getLastAcceptedHH(prev.entryTime, currentStructures);
        if (lastHH !== null) {
          const slPrice = lastHH + 2.00;
          const slDist = Math.max(5, slPrice - prev.entryPrice);
          const finalSL = prev.entryPrice + slDist;
          const finalTP = prev.entryPrice - (slDist * prev.riskRewardRatio);
          let newLot = prev.lotSize;
          if (prev.isAutoRisk && prev.riskAmountUsd) {
            newLot = Math.max(0.01, Math.min(50, Number((prev.riskAmountUsd / (slDist * 100)).toFixed(2))));
          }
          return { ...prev, slPrice: finalSL, tpPrice: finalTP, lotSize: newLot };
        }
      }
      return prev;
    });
  };

  const togglePlannerType = () => {
    setActivePlanner((prev) => {
      if (!prev) return null;
      const nextType = prev.type === "long" ? "short" : "long";
      const slDist = Math.abs(prev.entryPrice - prev.slPrice);
      const tpDist = Math.abs(prev.tpPrice - prev.entryPrice);
      const newSL = nextType === "long" ? prev.entryPrice - slDist : prev.entryPrice + slDist;
      const newTP = nextType === "long" ? prev.entryPrice + tpDist : prev.entryPrice - tpDist;
      return {
        ...prev,
        type: nextType,
        slPrice: newSL,
        tpPrice: newTP,
      };
    });
  };

  const updatePlannerLot = (lot: number) => {
    setActivePlanner((prev) => (prev ? { ...prev, lotSize: lot, isAutoRisk: false } : null));
  };

  const updatePlannerRiskAmount = (riskUsd: number) => {
    setActivePlanner((prev) => {
      if (!prev) return null;
      const slDist = Math.max(1, Math.abs(prev.entryPrice - prev.slPrice));
      const calculatedLot = Math.max(0.01, Math.min(50, Number((riskUsd / (slDist * 100)).toFixed(2))));
      return {
        ...prev,
        riskAmountUsd: riskUsd,
        lotSize: calculatedLot,
        isAutoRisk: true,
      };
    });
  };

  // ── Drag & Drop Position Lines & 2D Free Move on Chart Canvas ───────────────
  const [dragMode, setDragMode] = useState<"none" | "tp" | "sl" | "entry" | "width" | "move">("none");
  const dragModeRef = useRef<"none" | "tp" | "sl" | "entry" | "width" | "move">("none");
  const [hoveredDragTarget, setHoveredDragTarget] = useState<"none" | "tp" | "sl" | "entry" | "width" | "move">("none");
  const [dragMousePos, setDragMousePos] = useState<{ x: number; y: number } | null>(null);

  const dragStartRef = useRef<{
    mouseX: number;
    mouseY: number;
    entryPrice: number;
    slPrice: number;
    tpPrice: number;
    entryTime: number;
    exitTime: number;
    durationBars: number;
  } | null>(null);

  const getTimeToCanvasX = (time: number): number | null => {
    if (!chartRef.current) return null;
    const timeScale = chartRef.current.timeScale();
    const x = timeScale.timeToCoordinate(time as any);
    if (x !== null) return x;

    // Extrapolate for future time from current active candle
    const currentData = replayDataRef.current;
    if (!currentData || currentData.candles.length === 0) return null;
    const curIdx = currentIndexRef.current;
    const activeIdx = Math.max(0, Math.min(curIdx > 0 ? curIdx - 1 : currentData.candles.length - 1, currentData.candles.length - 1));
    const lastCandle = currentData.candles[activeIdx];
    if (!lastCandle) return null;

    const lastCandleX = timeScale.timeToCoordinate(lastCandle.time as any);
    if (lastCandleX === null) return null;

    const barSpacing = (timeScale.options() as any)?.barSpacing || 6;
    const secondsPerBar = activeTimeframe === "H4" ? 14400 : activeTimeframe === "H1" ? 3600 : activeTimeframe === "M30" ? 1800 : 900;
    const barsAhead = (time - lastCandle.time) / secondsPerBar;
    return lastCandleX + barsAhead * barSpacing;
  };

  const handleChartMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!activePlannerRef.current || !candleSeriesRef.current || !chartContainerRef.current) return;
    const rect = chartContainerRef.current.getBoundingClientRect();
    const mouseY = e.clientY - rect.top;
    const mouseX = e.clientX - rect.left;

    const entryY = candleSeriesRef.current.priceToCoordinate(activePlannerRef.current.entryPrice);
    const tpY = candleSeriesRef.current.priceToCoordinate(activePlannerRef.current.tpPrice);
    const slY = candleSeriesRef.current.priceToCoordinate(activePlannerRef.current.slPrice);
    const exitTs = activePlannerRef.current.exitTime ?? (activePlannerRef.current.entryTime + (activePlannerRef.current.durationBars || 15) * 900);
    const entryX = getTimeToCanvasX(activePlannerRef.current.entryTime);
    const exitX = getTimeToCanvasX(exitTs);

    const minY = Math.min(tpY ?? 9999, slY ?? 9999, entryY ?? 9999);
    const maxY = Math.max(tpY ?? -9999, slY ?? -9999, entryY ?? -9999);
    const minX = Math.min(entryX ?? -9999, exitX ?? -9999);
    const maxX = Math.max(entryX ?? 9999, exitX ?? 9999);

    dragStartRef.current = {
      mouseX,
      mouseY,
      entryPrice: activePlannerRef.current.entryPrice,
      slPrice: activePlannerRef.current.slPrice,
      tpPrice: activePlannerRef.current.tpPrice,
      entryTime: activePlannerRef.current.entryTime,
      exitTime: exitTs,
      durationBars: activePlannerRef.current.durationBars || 15,
    };

    if (exitX !== null && Math.abs(mouseX - exitX) <= 14 && mouseY >= minY - 10 && mouseY <= maxY + 10) {
      dragModeRef.current = "width";
      setDragMode("width");
      chartRef.current?.applyOptions({ handleScroll: false, handleScale: false });
      e.stopPropagation();
    } else if (tpY !== null && Math.abs(mouseY - tpY) <= 12) {
      dragModeRef.current = "tp";
      setDragMode("tp");
      chartRef.current?.applyOptions({ handleScroll: false, handleScale: false });
      e.stopPropagation();
    } else if (slY !== null && Math.abs(mouseY - slY) <= 12) {
      dragModeRef.current = "sl";
      setDragMode("sl");
      chartRef.current?.applyOptions({ handleScroll: false, handleScale: false });
      e.stopPropagation();
    } else if (minX !== -9999 && maxX !== 9999 && mouseX >= minX - 12 && mouseX <= maxX + 12 && mouseY >= minY - 10 && mouseY <= maxY + 10) {
      dragModeRef.current = "move";
      setDragMode("move");
      chartRef.current?.applyOptions({ handleScroll: false, handleScale: false });
      e.stopPropagation();
    }
  };

  const handleChartMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!activePlannerRef.current || !candleSeriesRef.current || !chartContainerRef.current) return;
    const rect = chartContainerRef.current.getBoundingClientRect();
    const mouseY = e.clientY - rect.top;
    const mouseX = e.clientX - rect.left;

    if (dragModeRef.current !== "none") {
      setDragMousePos({ x: mouseX, y: mouseY });

      if (dragModeRef.current === "width" && dragStartRef.current) {
        const currentStart = dragStartRef.current;
        const tsOptions = chartRef.current?.timeScale().options() as any;
        const barSpacing = tsOptions?.barSpacing || 6;
        const secondsPerBar = activeTimeframe === "H4" ? 14400 : activeTimeframe === "H1" ? 3600 : activeTimeframe === "M30" ? 1800 : 900;

        const pixelDeltaX = mouseX - currentStart.mouseX;
        const barsDelta = Math.round(pixelDeltaX / barSpacing);
        const newDurationBars = Math.max(2, currentStart.durationBars + barsDelta);
        const newExitTime = currentStart.entryTime + newDurationBars * secondsPerBar;

        setActivePlanner((prev) => (prev ? { ...prev, exitTime: newExitTime, durationBars: newDurationBars } : null));
        return;
      }

      if (dragModeRef.current === "move" && dragStartRef.current) {
        const price = candleSeriesRef.current.coordinateToPrice(mouseY);
        const currentStart = dragStartRef.current;

        const initialEntryPrice = currentStart.entryPrice;
        const slOffset = currentStart.slPrice - initialEntryPrice;
        const tpOffset = currentStart.tpPrice - initialEntryPrice;

        const newEntryPrice = price !== null ? price : initialEntryPrice;
        const newSlPrice = newEntryPrice + slOffset;
        const newTpPrice = newEntryPrice + tpOffset;

        const tsOptions = chartRef.current?.timeScale().options() as any;
        const barSpacing = tsOptions?.barSpacing || 6;
        const secondsPerBar = activeTimeframe === "H4" ? 14400 : activeTimeframe === "H1" ? 3600 : activeTimeframe === "M30" ? 1800 : 900;

        const pixelDeltaX = mouseX - currentStart.mouseX;
        const barsDelta = Math.round(pixelDeltaX / barSpacing);
        const timeDelta = barsDelta * secondsPerBar;

        const newEntryTime = Math.max(0, currentStart.entryTime + timeDelta);
        const newExitTime = Math.max(newEntryTime + secondsPerBar, currentStart.exitTime + timeDelta);

        setActivePlanner((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            entryPrice: newEntryPrice,
            slPrice: newSlPrice,
            tpPrice: newTpPrice,
            entryTime: newEntryTime,
            exitTime: newExitTime,
          };
        });
        return;
      }

      const price = candleSeriesRef.current.coordinateToPrice(mouseY);
      if (price === null) return;

      if (dragModeRef.current === "tp") {
        updatePlannerTPPrice(price);
      } else if (dragModeRef.current === "sl") {
        updatePlannerSLPrice(price);
      }
      return;
    }

    const entryY = candleSeriesRef.current.priceToCoordinate(activePlannerRef.current.entryPrice);
    const tpY = candleSeriesRef.current.priceToCoordinate(activePlannerRef.current.tpPrice);
    const slY = candleSeriesRef.current.priceToCoordinate(activePlannerRef.current.slPrice);
    const exitTs = activePlannerRef.current.exitTime ?? (activePlannerRef.current.entryTime + (activePlannerRef.current.durationBars || 15) * 900);
    const entryX = getTimeToCanvasX(activePlannerRef.current.entryTime);
    const exitX = getTimeToCanvasX(exitTs);

    const minY = Math.min(tpY ?? 9999, slY ?? 9999, entryY ?? 9999);
    const maxY = Math.max(tpY ?? -9999, slY ?? -9999, entryY ?? -9999);
    const minX = Math.min(entryX ?? -9999, exitX ?? -9999);
    const maxX = Math.max(entryX ?? 9999, exitX ?? 9999);

    if (exitX !== null && Math.abs(mouseX - exitX) <= 14 && mouseY >= minY - 10 && mouseY <= maxY + 10) {
      setHoveredDragTarget("width");
      setDragMousePos({ x: mouseX, y: mouseY });
    } else if (tpY !== null && Math.abs(mouseY - tpY) <= 14) {
      setHoveredDragTarget("tp");
      setDragMousePos({ x: mouseX, y: mouseY });
    } else if (slY !== null && Math.abs(mouseY - slY) <= 14) {
      setHoveredDragTarget("sl");
      setDragMousePos({ x: mouseX, y: mouseY });
    } else if (minX !== -9999 && maxX !== 9999 && mouseX >= minX - 12 && mouseX <= maxX + 12 && mouseY >= minY - 10 && mouseY <= maxY + 10) {
      setHoveredDragTarget("move");
      setDragMousePos({ x: mouseX, y: mouseY });
    } else {
      if (hoveredDragTarget !== "none") setHoveredDragTarget("none");
      if (dragMousePos !== null) setDragMousePos(null);
    }
  };

  const handleChartMouseUp = () => {
    if (dragModeRef.current !== "none") {
      dragModeRef.current = "none";
      setDragMode("none");
      dragStartRef.current = null;
      chartRef.current?.applyOptions({ handleScroll: true, handleScale: true });
    }
  };

  const handleChartMouseLeave = () => {
    if (dragModeRef.current !== "none") {
      dragModeRef.current = "none";
      setDragMode("none");
      dragStartRef.current = null;
      chartRef.current?.applyOptions({ handleScroll: true, handleScale: true });
    }
    setHoveredDragTarget("none");
    setDragMousePos(null);
  };


  const getFilteredTrades = useCallback(
    (data: ReplayData) => {
      const m15Data = allReplayData.M15 ?? (data.meta.timeframe === "M15" ? data : null);
      const h1Data = allReplayData.H1 ?? (data.meta.timeframe === "H1" ? data : null);
      const h4Data = allReplayData.H4 ?? (data.meta.timeframe === "H4" ? data : null);
      const m15Candles = m15Data?.candles ?? [];
      const h1Candles = h1Data?.candles ?? [];
      const h4Candles = h4Data?.candles ?? [];

      const { executedTrades } = getProcessedReplayTrades(
        data,
        data.structures,
        entryFilterParams,
        m15Candles,
        h1Candles,
        h4Candles,
      );
      return executedTrades;
    },
    [allReplayData, entryFilterParams]
  );

  // Running stats
  const [runningProfit, setRunningProfit] = useState(0);
  const [tradeStats, setTradeStats] = useState({ total: 0, wins: 0, losses: 0 });
  const [activePositions, setActivePositions] = useState<any[]>([]);

  // ── LLM Trade Setup: request recommendation from backend ──
  const llmAbortControllerRef = useRef<AbortController | null>(null);

  const cancelLLMSetup = useCallback(() => {
    if (llmAbortControllerRef.current) {
      llmAbortControllerRef.current.abort();
      llmAbortControllerRef.current = null;
    }
    setLlmLoading(false);
    setDecisionLoading(false);
  }, []);

  const requestLLMSetup = useCallback(async (structureEvent?: any) => {
    if (!replayData || currentIndex === 0) {
      setDecisionError("Pilih candle terlebih dahulu");
      return;
    }

    // Cancel any previous pending LLM request
    if (llmAbortControllerRef.current) {
      llmAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    llmAbortControllerRef.current = controller;

    let entryTs: number;
    let entryPrice: number;
    let structure: string;

    const candle = currentIndex > 0 ? (replayData.candles[currentIndex - 1] || replayData.candles[0]) : replayData.candles[0];

    if (structureEvent) {
      entryTs = structureEvent.time ?? candle?.time ?? 0;
      entryPrice = structureEvent.price ?? candle?.close ?? 0;
      const dir = structureEvent.direction ? ` (${structureEvent.direction})` : "";
      structure = `${structureEvent.type || "STRUCTURE"}${dir}`;
    } else {
      const active = activePositions.find(p => !p.is_closed && !p.is_rejected);
      if (active) {
        entryTs = active.entry_time ?? candle?.time ?? 0;
        entryPrice = active.entry_price ?? candle?.close ?? 0;
        structure = active.signal_type || "ACTIVE_TRADE";
      } else {
        entryTs = candle?.time ?? 0;
        entryPrice = candle?.close ?? 0;
        const latestStruct = [...replayData.structures]
          .reverse()
          .find(s => s.time <= entryTs);
        if (latestStruct) {
          const dir = latestStruct.direction ? ` (${latestStruct.direction})` : "";
          structure = `${latestStruct.type || "STRUCTURE"}${dir}`;
        } else {
          structure = "MANUAL_REPLAY_ANALYSIS";
        }
      }
    }

    setLlmLoading(true);
    setDecisionLoading(true);
    setDecisionError(null);
    setLlmRecommendation(null);

    try {
      // Compute ATR for volatility context
      const atr = calculateATR(replayData.candles, entryTs, strategyParams.atr_period);
      const priorCandles = replayData.candles.filter(c => c.time <= entryTs).slice(-30);
      const localCandles = priorCandles.slice(-10);
      const candlesSummary = priorCandles.length > 0
        ? `recent 10-bar local pullback: high=${Math.max(...localCandles.map(c => c.high)).toFixed(2)}, low=${Math.min(...localCandles.map(c => c.low)).toFixed(2)} | 30-bar range: swingHigh=${Math.max(...priorCandles.map(c => c.high)).toFixed(2)}, swingLow=${Math.min(...priorCandles.map(c => c.low)).toFixed(2)}, lastClose=${priorCandles[priorCandles.length - 1].close.toFixed(2)}`
        : "no prior candles";

      // Calculate live multi-timeframe indicator data & candle quality
      const loadedMap = allReplayDataRef.current || allReplayData;
      const m15Candles = loadedMap.M15?.candles ?? replayData.candles;
      let h1Candles = loadedMap.H1?.candles ?? [];
      let h4Candles = loadedMap.H4?.candles ?? [];

      // Auto-fetch H1 on-the-fly if not yet present in memory
      if (h1Candles.length === 0) {
        try {
          const h1Data = await fetchReplayData(yearFrom, monthFrom, yearTo, monthTo, "H1");
          if (h1Data?.candles && h1Data.candles.length > 0) {
            h1Candles = h1Data.candles;
            setAllReplayData(prev => ({ ...prev, H1: h1Data }));
            allReplayDataRef.current = { ...allReplayDataRef.current, H1: h1Data };
          }
        } catch (err) {
          console.warn("[LLM Setup] Auto-fetch H1 candles fallback warning:", err);
        }
      }

      // Auto-fetch H4 on-the-fly if not yet present in memory
      if (h4Candles.length === 0) {
        try {
          const h4Data = await fetchReplayData(yearFrom, monthFrom, yearTo, monthTo, "H4");
          if (h4Data?.candles && h4Data.candles.length > 0) {
            h4Candles = h4Data.candles;
            setAllReplayData(prev => ({ ...prev, H4: h4Data }));
            allReplayDataRef.current = { ...allReplayDataRef.current, H4: h4Data };
          }
        } catch (err) {
          console.warn("[LLM Setup] Auto-fetch H4 candles fallback warning:", err);
        }
      }

      const m15Index = getCandleIndexAtOrBefore(m15Candles, entryTs);
      const m15Candle = m15Index > 0 ? m15Candles[m15Index - 1] : (m15Index >= 0 ? m15Candles[m15Index] : null);
      const m15Ema = m15Candle?.ema200 ?? null;
      const range = m15Candle ? m15Candle.high - m15Candle.low : 0;
      const bodyRatioPct = (m15Candle && range > 0)
        ? Math.round((Math.abs(m15Candle.close - m15Candle.open) / range) * 100)
        : null;

      const h1Candle = getCandleAtOrBefore(h1Candles, entryTs);
      const h1Ema = h1Candle?.ema200 ?? null;
      const h4Index = getCandleIndexAtOrBefore(h4Candles, entryTs);
      const h4Candle = h4Index >= 0 ? h4Candles[h4Index] : null;
      const h4Ema = h4Candle?.ema200 ?? null;

      const utcHour = new Date(entryTs * 1000).getUTCHours();
      let sessionName = "Asian / Rollover Session (00:00 - 06:00 UTC)";
      if (utcHour >= 7 && utcHour < 12) sessionName = "London Session (07:00 - 12:00 UTC)";
      else if (utcHour >= 12 && utcHour < 16) sessionName = "London / NY Overlap Peak (12:00 - 16:00 UTC)";
      else if (utcHour >= 16 && utcHour < 21) sessionName = "New York Session (16:00 - 21:00 UTC)";

      // Extract SMC obstacles (Supply/Demand & Liquidity Pools) for LLM high-probability TP
      const sdZones = calculateSupplyDemandZones(replayData.candles, replayData.structures, entryTs);
      const activeSupply = sdZones.filter(z => z.type === "SUPPLY" && !z.isMitigated && z.bottomPrice > entryPrice).sort((a, b) => a.bottomPrice - b.bottomPrice)[0];
      const activeDemand = sdZones.filter(z => z.type === "DEMAND" && !z.isMitigated && z.topPrice < entryPrice).sort((a, b) => b.topPrice - a.topPrice)[0];

      const pools = calculateLiquidityPools(replayData.candles, replayData.structures, entryTs);
      const activeBsl = pools.filter(p => p.type === "BSL" && !p.isSwept && p.price > entryPrice).sort((a, b) => a.price - b.price)[0];
      const activeSsl = pools.filter(p => p.type === "SSL" && !p.isSwept && p.price < entryPrice).sort((a, b) => b.price - a.price)[0];

      // Calculate Structure Cycle and EMA Stretch Ratio for Exhaustion Analysis
      const { latestType, bosCycle } = getEntryStructureInfo(entryTs, replayData.structures);
      const isChoch = structure.toUpperCase().includes("CHOCH") || latestType === "CHOCH";
      const currentBos = Math.max(1, bosCycle);
      const emaStretchRatio = m15Ema && atr && atr > 0 ? Number((Math.abs(entryPrice - m15Ema) / atr).toFixed(2)) : null;

      let exhaustionStage = `FRESH_CYCLE (BOS #${currentBos} - Konfirmasi Awal Tren Baru)`;
      if (isChoch) {
        exhaustionStage = "REVERSAL_SHIFT (CHOCH - Awal Pembalikan Arah / Siklus #0)";
      } else if (bosCycle >= 4 || (emaStretchRatio !== null && emaStretchRatio > 3.5)) {
        exhaustionStage = `OVEREXTENDED (BOS #${currentBos}, Regangan EMA ${emaStretchRatio ?? "n/a"}x ATR - Risiko Kelelahan Tinggi)`;
      } else if (bosCycle >= 2) {
        exhaustionStage = `MID_CYCLE (BOS #${bosCycle}, Regangan EMA ${emaStretchRatio ?? "n/a"}x ATR - Ekspansi Sehat)`;
      }

      const marketContext = {
        m15_ema200: m15Ema ? Number(m15Ema.toFixed(2)) : null,
        m15_trend: m15Ema && m15Candle ? (m15Candle.close > m15Ema ? `BULLISH (Price above M15 EMA200 $${m15Ema.toFixed(2)})` : `BEARISH (Price below M15 EMA200 $${m15Ema.toFixed(2)})`) : "NEUTRAL",
        h1_ema200: h1Ema ? Number(h1Ema.toFixed(2)) : null,
        h1_trend: h1Ema && h1Candle ? (h1Candle.close > h1Ema ? `BULLISH (Close $${h1Candle.close.toFixed(2)} > EMA $${h1Ema.toFixed(2)})` : `BEARISH (Close $${h1Candle.close.toFixed(2)} < EMA $${h1Ema.toFixed(2)})`) : "NEUTRAL / UNKNOWN",
        h4_ema200: h4Ema ? Number(h4Ema.toFixed(2)) : null,
        h4_trend: h4Ema && h4Candle ? (h4Candle.close > h4Ema ? `BULLISH (Close $${h4Candle.close.toFixed(2)} > EMA $${h4Ema.toFixed(2)})` : `BEARISH (Close $${h4Candle.close.toFixed(2)} < EMA $${h4Ema.toFixed(2)})`) : "NEUTRAL / UNKNOWN",
        candle_body_ratio_pct: bodyRatioPct,
        candle_quality: bodyRatioPct && bodyRatioPct >= 50 ? `STRONG IMPULSE (${bodyRatioPct}% Body)` : (bodyRatioPct ? `MODERATE (${bodyRatioPct}% Body)` : "NORMAL"),
        session_name: sessionName,
        utc_hour: utcHour,
        nearest_supply_zone: activeSupply ? { bottom: activeSupply.bottomPrice, top: activeSupply.topPrice, label: activeSupply.label } : null,
        nearest_demand_zone: activeDemand ? { bottom: activeDemand.bottomPrice, top: activeDemand.topPrice, label: activeDemand.label } : null,
        nearest_bsl_target: activeBsl ? { price: activeBsl.price, label: activeBsl.label } : null,
        nearest_ssl_target: activeSsl ? { price: activeSsl.price, label: activeSsl.label } : null,
        is_choch_reversal: isChoch,
        bos_cycle_count: isChoch ? 0 : (bosCycle || 1),
        ema_stretch_ratio: emaStretchRatio,
        exhaustion_stage: exhaustionStage,
      };

      const payload = {
        structure,
        entry_price: entryPrice,
        atr,
        balance: strategyParams.initial_balance ?? 1000,
        risk_pct: strategyParams.risk_pct || 2.0,
        news: "no news",
        timeframe: activeTimeframe,
        candles_summary: candlesSummary,
        market_context: marketContext,
        ea_filters: {
          h1_ema200: entryFilterParams.h1_ema200_filter,
          h4_ema: entryFilterParams.h4_ema_filter,
          ema_slope: entryFilterParams.ema_slope_filter,
          body_ratio: entryFilterParams.body_ratio_filter,
          session: entryFilterParams.session_filter,
          ema_stretch_filter: entryFilterParams.ema_stretch_filter,
          bos_cycle_filter: entryFilterParams.bos_cycle_filter,
        },
      };

      const res = await fetch(`${BASE_URL}/trading/llm-setup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errBody.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      if (!controller.signal.aborted) {
        setLlmRecommendation({
          ...data,
          engine_used: "llm",
          signal: data.signal,
          entry_price: data.entry_price || entryPrice,
          sl_price: data.sl_price ?? data.sl,
          tp_price: data.tp_price ?? data.tp1 ?? data.tp,
          sl: data.sl_price ?? data.sl,
          tp1: data.tp_price ?? data.tp1 ?? data.tp,
          lot_size: data.lot_size,
          confidence: data.confidence,
          reasoning: data.reasoning,
          cycle_stage: data.cycle_stage || exhaustionStage,
        });
      }
    } catch (e: any) {
      if (e?.name === "AbortError" || controller.signal.aborted) {
        console.log("🛑 Permintaan rekomendasi LLM dibatalkan.");
        return;
      }
      console.error("LLM setup request failed:", e);
      setDecisionError(e?.message || "Gagal memanggil LLM");
      setLlmRecommendation({
        signal: "HOLD",
        confidence: 0,
        sl_price: 0,
        tp_price: 0,
        lot_size: 0,
        reasoning: `Gagal memanggil LLM: ${e?.message || e}`,
      });
    } finally {
      if (llmAbortControllerRef.current === controller) {
        llmAbortControllerRef.current = null;
        setLlmLoading(false);
        setDecisionLoading(false);
      }
    }
  }, [replayData, currentIndex, activePositions, strategyParams, activeTimeframe, entryFilterParams, allReplayData, yearFrom, monthFrom, yearTo, monthTo]);

  // Decision Engine (Rule | LLM) toggle dispatcher
  // ── Decision Engine (SmartRuleEngine vs LLMDecisionEngine 7-Step Reasoning) ──
  const requestDecisionSetup = useCallback(async () => {
    if (!replayData || currentIndex === 0) {
      setDecisionError("Pilih candle terlebih dahulu");
      return;
    }

    setDecisionLoading(true);
    setLlmLoading(true);
    setDecisionError(null);
    setLlmRecommendation(null);

    try {
      // Ensure H1 & H4 candles exist in memory
      const loadedMap = allReplayDataRef.current || allReplayData;
      let h1Candles = loadedMap.H1?.candles ?? [];
      let h4Candles = loadedMap.H4?.candles ?? [];

      if (h1Candles.length === 0) {
        try {
          const h1Data = await fetchReplayData(yearFrom, monthFrom, yearTo, monthTo, "H1");
          if (h1Data?.candles && h1Data.candles.length > 0) {
            h1Candles = h1Data.candles;
            setAllReplayData(prev => ({ ...prev, H1: h1Data }));
            allReplayDataRef.current = { ...allReplayDataRef.current, H1: h1Data };
          }
        } catch (err) {
          console.warn("[Decision Setup] Auto-fetch H1 candles warning:", err);
        }
      }

      if (h4Candles.length === 0) {
        try {
          const h4Data = await fetchReplayData(yearFrom, monthFrom, yearTo, monthTo, "H4");
          if (h4Data?.candles && h4Data.candles.length > 0) {
            h4Candles = h4Data.candles;
            setAllReplayData(prev => ({ ...prev, H4: h4Data }));
            allReplayDataRef.current = { ...allReplayDataRef.current, H4: h4Data };
          }
        } catch (err) {
          console.warn("[Decision Setup] Auto-fetch H4 candles warning:", err);
        }
      }

      const m15Slice = (replayData.candles || []).slice(0, currentIndex);
      const currentCandle = m15Slice[m15Slice.length - 1] || replayData.candles[0];
      const anchorTs = new Date(currentCandle.time * 1000).toISOString();

      const m15Bars = (replayData.candles || []).slice(0, Math.max(currentIndex, 60)).map((c) => ({
        time: new Date(c.time * 1000).toISOString(),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));

      const h1Bars = (h1Candles.length > 0 ? h1Candles : (replayData.candles || [])).slice(0, Math.max(Math.floor(currentIndex / 4) + 1, 60)).map((c) => ({
        time: new Date(c.time * 1000).toISOString(),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));

      const h4Bars = (h4Candles.length > 0 ? h4Candles : (replayData.candles || [])).slice(0, Math.max(Math.floor(currentIndex / 16) + 1, 60)).map((c) => ({
        time: new Date(c.time * 1000).toISOString(),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));

      const engineType = decisionEngine === "llm" ? "llm" : "rule";
      const payload = {
        symbol: "XAUUSD",
        anchor_timestamp: anchorTs,
        engine: engineType,
        ohlc: { M15: m15Bars, H1: h1Bars, H4: h4Bars },
        balance: Number(strategyParams.initial_balance) || 1000.0,
        risk_pct: strategyParams.risk_pct || 1.0,
      };

      const res = await fetch(`${BASE_URL}/replay/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errBody.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setLlmRecommendation({
        ...data,
        engine_used: engineType,
        signal: data.signal,
        entry_price: data.entry_price || currentCandle.close,
        sl_price: data.sl,
        tp_price: data.tp1,
        sl: data.sl,
        tp1: data.tp1,
        tp2: data.tp2,
        lot_size: data.lot_size,
        rr_ratio: data.rr_ratio,
        confidence: data.confidence,
        reasoning: data.reasoning,
        confluences: data.confluences || [],
        block_reason: data.block_reason,
        regime: data.regime,
        event_proximity: data.event_proximity,
      });
    } catch (err: any) {
      console.error("Decision setup failed:", err);
      setDecisionError(err?.message || "Gagal meminta decision setup");
      setLlmRecommendation({
        signal: "HOLD",
        confidence: 0,
        sl_price: 0,
        tp_price: 0,
        lot_size: 0,
        reasoning: `Gagal memanggil LLM 7-Step Reasoning: ${err?.message || err}`,
      });
    } finally {
      setDecisionLoading(false);
      setLlmLoading(false);
    }
  }, [replayData, currentIndex, allReplayData, decisionEngine, strategyParams, yearFrom, monthFrom, yearTo, monthTo]);

  // ── LLM Trade Setup: execute the recommendation ──
  const executeLLMSetup = useCallback(() => {
    if (!llmRecommendation) return;
    const isTradeable = (llmRecommendation.signal === "BUY" || llmRecommendation.signal === "SELL") && (llmRecommendation.sl_price ?? llmRecommendation.sl ?? 0) > 0;
    if (!isTradeable) return;
    if (!replayData) return;

    const rec = llmRecommendation;
    const entryTs = currentIndex > 0 ? (replayData.candles[currentIndex - 1]?.time ?? 0) : (replayData.candles[0]?.time ?? 0);
    const candleClose = currentIndex > 0 ? (replayData.candles[currentIndex - 1]?.close ?? 0) : (replayData.candles[0]?.close ?? 0);
    const entryPrice = rec.entry_price && rec.entry_price > 0 ? rec.entry_price : candleClose;
    const slPrice = rec.sl_price ?? rec.sl ?? 0;
    const tpPrice = rec.tp_price ?? rec.tp1 ?? 0;
    const lotSize = Math.max(0.01, Number((rec.lot_size || 0.01).toFixed(2)));

    const llmPos = {
      ticket: `LLM-${entryTs}`,
      type: rec.signal,
      entry_time: entryTs,
      lot_size: lotSize,
      entry_price: entryPrice,
      current_price: entryPrice,
      sl: slPrice,
      tp: tpPrice,
      original_sl: slPrice,
      original_tp: tpPrice,
      status: "Running",
      pnl: 0,
      be_trigger_price: null,
      is_be_active: false,
      tp_trigger_price: null,
      is_tp_maxed: false,
      is_llm: true,
      reasoning: rec.reasoning,
    };

    setLlmPositions((prev) => {
      if (prev.some(p => p.entry_time === entryTs)) return prev;
      return [...prev, llmPos];
    });

    setActivePositions((prev) => {
      if (prev.some(p => p.entry_time === entryTs && p.is_llm)) return prev;
      return [llmPos, ...prev];
    });

    console.log("✅ LLM setup executed:", rec);
    setLlmRecommendation(null);
  }, [llmRecommendation, replayData, currentIndex]);

  // ── LLM Trade Setup: reject or handle HOLD recommendation ──
  const rejectLLMSetup = useCallback((reason = "Ditolak oleh User") => {
    if (!llmRecommendation || !replayData) {
      setLlmRecommendation(null);
      return;
    }
    const entryTs = currentIndex > 0 ? (replayData.candles[currentIndex - 1]?.time ?? 0) : (replayData.candles[0]?.time ?? 0);
    const entryPrice = currentIndex > 0 ? (replayData.candles[currentIndex - 1]?.close ?? 0) : (replayData.candles[0]?.close ?? 0);
    const rec = llmRecommendation;

    const rejectedPos = {
      ticket: `LLM-${entryTs}`,
      type: rec.signal === "HOLD" ? "HOLD" : rec.signal,
      entry_time: entryTs,
      lot_size: rec.lot_size ?? 0.01,
      entry_price: entryPrice,
      current_price: null,
      sl: null,
      tp: null,
      original_sl: null,
      original_tp: null,
      status: "Rejected",
      reject_reason: rec.signal === "HOLD" ? (rec.reasoning || "Ditolak oleh LLM (HOLD)") : reason,
      pnl: 0,
      is_rejected: true,
      is_llm: true,
    };

    setLlmPositions((prev) => {
      if (prev.some(p => p.entry_time === entryTs)) return prev;
      return [...prev, rejectedPos];
    });

    setActivePositions((prev) => {
      if (prev.some(p => p.entry_time === entryTs && p.is_llm)) return prev;
      return [rejectedPos, ...prev];
    });

    console.log("❌ LLM setup rejected:", rejectedPos);
    setLlmRecommendation(null);
  }, [llmRecommendation, replayData, currentIndex]);

  // ── Auto-trigger LLM Trade Setup on CHoCH & BOS ──
  const processedLLMEventsRef = useRef<Set<number>>(new Set());
  const [autoDecisionEnabled, setAutoDecisionEnabled] = useState(true);

  useEffect(() => {
    const isLLMActive = useLLMSetup || decisionEngine === "llm";
    if (!isLLMActive || !autoDecisionEnabled || !replayData || currentIndex === 0) return;
    if (llmLoading || decisionLoading) return;

    const candle = replayData.candles[currentIndex - 1];
    if (!candle) return;

    // Cari CHoCH atau BOS event terbaru yang belum diproses dan ≤ current candle
    const event = [...replayData.structures]
      .reverse()
      .find((s) => {
        const t = (s.type || "").toUpperCase();
        const isStructure = t.includes("CHOCH") || t.includes("BOS");
        return isStructure && s.time <= candle.time && !processedLLMEventsRef.current.has(s.time ?? 0);
      });
    if (!event) return;

    const key = event.time ?? 0;
    processedLLMEventsRef.current.add(key);
    if (useLLMSetup) {
      console.log(`🤖 Auto LLM Trade Setup (SL/TP/Lot) triggered by ${event.type} @ ${new Date(key * 1000).toISOString()}`);
      requestLLMSetup(event);
    } else if (decisionEngine === "llm") {
      console.log(`🧠 Auto LLM 7-Step Reasoning triggered by ${event.type} @ ${new Date(key * 1000).toISOString()}`);
      requestDecisionSetup();
    }
  }, [useLLMSetup, decisionEngine, autoDecisionEnabled, replayData, currentIndex, llmLoading, decisionLoading, requestLLMSetup, requestDecisionSetup]);

  // ── Auto-sync Entry Filter toggles ──
  const isAutoDecisionActive = autoDecisionEnabled && (decisionEngine === "llm" || useLLMSetup);
  useEffect(() => {
    if (isAutoDecisionActive && entryFilterParams.entry_choch) {
      setEntryFilterParams((prev) => ({
        ...prev,
        entry_choch: false,
        entry_bos: false,
        entry_bos_cycle_2_plus: false,
      }));
    }
  }, [isAutoDecisionActive]); // eslint-disable-line react-hooks/exhaustive-deps

  // Monthly summary stats
  const [monthlyPNL, setMonthlyPNL] = useState<any[]>([]);
  const [monthlySummaryYearFilter, setMonthlySummaryYearFilter] = useState<string>("2026");
  const [monthlySummaryPerformanceFilter, setMonthlySummaryPerformanceFilter] = useState<string>("all");
  const [isYearDropdownOpen, setIsYearDropdownOpen] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalTitle, setModalTitle] = useState("");
  const [isLoadingTrades, setIsLoadingTrades] = useState(false);
  const [selectedMonthTrades, setSelectedMonthTrades] = useState<any[]>([]);
  const availableYears = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"];

  // ── Session Zones ──────────────────────────────────────────────────────────
  const sessionFromDate = `${yearFrom}-${String(monthFrom).padStart(2, "0")}-01`;
  const { data: sessionZonesData } = useSessionZones(sessionFromDate, "XAUUSD");
  useEffect(() => {
    const primitive = sessionZonesPrimitiveRef.current;
    if (!primitive || !sessionZonesData?.zones?.length) return;
    const boxes: SessionZoneBox[] = sessionZonesData.zones.map((z) => ({
      start: z.start_time,
      end: z.end_time,
      session: z.session,
      open: z.status === "OPEN",
    }));
    primitive.setBoxes(boxes);
  }, [sessionZonesData]);

  const stopPlayback = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsPlaying(false);
    cancelLLMSetup();
  }, [cancelLLMSetup]);

  const handleStop = useCallback(() => {
    stopPlayback();
    cancelLLMSetup();
    setCurrentIndex(0);
    setRunningProfit(0);
    setTradeStats({ total: 0, wins: 0, losses: 0 });
    setActivePositions([]);
    // Reset LLM auto-trigger dedup so re-running the replay re-triggers on the
    // same CHoCH/BOS structures.
    processedLLMEventsRef.current.clear();
    setLlmRecommendation(null);
    setLlmPositions([]);

    // Clear chart series
    candleSeriesRef.current?.setData([]);
    emaSeriesRef.current?.setData([]);
    ma20SeriesRef.current?.setData([]);
    ma50SeriesRef.current?.setData([]);
    structurePrimitiveRef.current?.setLines([]);
    tradesPrimitiveRef.current?.setTrades([]);
  }, [stopPlayback, cancelLLMSetup]);

  const yearOptions = Array.from({ length: currentYear - 2018 + 1 }, (_, i) => 2018 + i);

  // Derived available years from dbMonths
  const availableYearsFrom = dbMonths.length > 0
    ? Array.from(new Set(dbMonths.map(d => d.year))).sort((a, b) => a - b)
    : yearOptions;

  const availableMonthsFrom = dbMonths.length > 0
    ? dbMonths.filter(d => d.year === yearFrom).map(d => d.month).sort((a, b) => a - b)
    : Array.from({ length: 12 }, (_, i) => i + 1);

  const availableYearsTo = dbMonths.length > 0
    ? Array.from(new Set(dbMonths.map(d => d.year))).filter(y => y >= yearFrom).sort((a, b) => a - b)
    : yearOptions.filter(y => y >= yearFrom);

  const availableMonthsTo = dbMonths.length > 0
    ? dbMonths.filter(d => d.year === yearTo && (yearTo > yearFrom || d.month >= monthFrom)).map(d => d.month).sort((a, b) => a - b)
    : Array.from({ length: 12 }, (_, i) => i + 1).filter(m => yearTo > yearFrom || m >= monthFrom);

  // ── Init chart ───────────────────────────────────────────────────────────

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(100,116,139,0.1)" },
        horzLines: { color: "rgba(100,116,139,0.1)" },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: "rgba(100,116,139,0.2)" },
      timeScale: {
        borderColor: "rgba(100,116,139,0.2)",
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 18,
        fixLeftEdge: false,
        fixRightEdge: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
    });

    candleSeriesRef.current = chart.addSeries(CandlestickSeries, {
      upColor: "#22d3ee",
      downColor: "#f43f5e",
      borderUpColor: "#22d3ee",
      borderDownColor: "#f43f5e",
      wickUpColor: "#22d3ee",
      wickDownColor: "#f43f5e",
    });

    // Init markers plugin
    markersPluginRef.current = createSeriesMarkers(candleSeriesRef.current, []);

    // Init structure lines primitive
    try {
      const structPrimitive = new StructureLinesPrimitive();
      (candleSeriesRef.current as any).attachPrimitive(structPrimitive);
      structurePrimitiveRef.current = structPrimitive;
    } catch (e) {
      console.warn("Could not attach structure lines primitive in replay:", e);
    }

    // Init trades overlay primitive
    try {
      const tradesPrimitive = new TradesOverlayPrimitive();
      (candleSeriesRef.current as any).attachPrimitive(tradesPrimitive);
      tradesPrimitiveRef.current = tradesPrimitive;
    } catch (e) {
      console.warn("Could not attach trades overlay primitive in replay:", e);
    }

    // Init session zones primitive (background color bands per trading session)
    try {
      const sessionPrimitive = new SessionZonesPrimitive();
      (candleSeriesRef.current as any).attachPrimitive(sessionPrimitive);
      sessionZonesPrimitiveRef.current = sessionPrimitive;
    } catch (e) {
      console.warn("Could not attach session zones primitive in replay:", e);
    }

    // Init supply demand zones primitive (SMC Resistance & Support Zones)
    try {
      const sdPrimitive = new SupplyDemandPrimitive();
      (candleSeriesRef.current as any).attachPrimitive(sdPrimitive);
      supplyDemandPrimitiveRef.current = sdPrimitive;
    } catch (e) {
      console.warn("Could not attach supply demand primitive in replay:", e);
    }

    // Init liquidity pools primitive (BSL / SSL & Equal Highs/Lows)
    try {
      const lpPrimitive = new LiquidityPoolsPrimitive();
      (candleSeriesRef.current as any).attachPrimitive(lpPrimitive);
      liquidityPoolsPrimitiveRef.current = lpPrimitive;
    } catch (e) {
      console.warn("Could not attach liquidity pools primitive in replay:", e);
    }

    emaSeriesRef.current = chart.addSeries(LineSeries, {
      color: "#facc15",
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      priceLineVisible: false,
    });
    ma20SeriesRef.current = chart.addSeries(LineSeries, {
      color: "#22d3ee",
      lineWidth: 1,
      priceLineVisible: false,
      visible: isMa20Visible,
    });
    ma50SeriesRef.current = chart.addSeries(LineSeries, {
      color: "#fb923c",
      lineWidth: 1,
      priceLineVisible: false,
      visible: isMa50Visible,
    });

    chartRef.current = chart;

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.point || !candleSeriesRef.current) {
        setHoveredInfo(null);
        return;
      }

      const price = candleSeriesRef.current.coordinateToPrice(param.point.y);
      const data = param.seriesData.get(candleSeriesRef.current);
      if (data) {
        const candleData = data as any;
        let timeStr = "";
        if (typeof param.time === "number") {
          timeStr = new Date(param.time * 1000).toISOString().slice(0, 16).replace("T", " ");
        } else if (typeof param.time === "string") {
          timeStr = param.time;
        } else {
          const timeObj = param.time as any;
          if (timeObj && timeObj.year) {
            timeStr = `${timeObj.year}-${String(timeObj.month).padStart(2, "0")}-${String(timeObj.day).padStart(2, "0")}`;
          }
        }

        setHoveredInfo({
          time: timeStr,
          open: candleData.open ?? null,
          high: candleData.high ?? null,
          low: candleData.low ?? null,
          close: candleData.close ?? null,
          hoveredPrice: price ?? null,
        });
      } else {
        setHoveredInfo({
          time: null,
          open: null,
          high: null,
          low: null,
          close: null,
          hoveredPrice: price ?? null,
        });
      }
    });

    chart.subscribeClick((param) => {
      if (plannerToolRef.current === "none") return;
      if (!param.point || !candleSeriesRef.current) return;

      const price = candleSeriesRef.current.coordinateToPrice(param.point.y);
      if (price === null) return;

      const time = typeof param.time === "number" ? param.time : (replayDataRef.current?.candles[0]?.time ?? Math.floor(Date.now() / 1000));
      const currentStructures = replayDataRef.current?.structures ?? [];
      const lot = strategyParamsRef.current.lot_override > 0 ? strategyParamsRef.current.lot_override : 0.05;
      const ratio = selectedRrRatioRef.current;

      if (plannerToolRef.current === "long") {
        const lastLL = getLastAcceptedLL(time, currentStructures);
        const slPrice = lastLL ? lastLL - 2.00 : price - 30.00;
        const slDist = Math.max(5.00, price - slPrice);
        const finalSL = price - slDist;
        const finalTP = price + (slDist * ratio);

        setActivePlanner({
          type: "long",
          entryPrice: price,
          entryTime: time,
          slPrice: finalSL,
          tpPrice: finalTP,
          lotSize: lot,
          riskRewardRatio: ratio,
        });
        setPlannerTool("none");
      } else if (plannerToolRef.current === "short") {
        const lastHH = getLastAcceptedHH(time, currentStructures);
        const slPrice = lastHH ? lastHH + 2.00 : price + 30.00;
        const slDist = Math.max(5.00, slPrice - price);
        const finalSL = price + slDist;
        const finalTP = price - (slDist * ratio);

        setActivePlanner({
          type: "short",
          entryPrice: price,
          entryTime: time,
          slPrice: finalSL,
          tpPrice: finalTP,
          lotSize: lot,
          riskRewardRatio: ratio,
        });
        setPlannerTool("none");
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    });
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, []);

  useEffect(() => {
    ma20SeriesRef.current?.applyOptions({ visible: isMa20Visible });
  }, [isMa20Visible]);

  useEffect(() => {
    ma50SeriesRef.current?.applyOptions({ visible: isMa50Visible });
  }, [isMa50Visible]);

  // ── Fetch Available Months ───────────────────────────────────────────────
  useEffect(() => {
    const loadMonths = async () => {
      try {
        const res = await fetch(`${BASE_URL}/trading/replay/months`);
        if (res.ok) {
          const data = await res.json();
          setDbMonths(data);

          if (data.length > 0) {
            const monthsData = data as { year: number; month: number }[];
            // Sort to find min/max
            const sorted = [...monthsData].sort((a, b) => (a.year * 12 + a.month) - (b.year * 12 + b.month));
            const first = sorted[0];
            const last = sorted[sorted.length - 1];

            // Check if currentYear is present in the database data
            const hasCurrentYear = monthsData.some(d => d.year === currentYear);
            if (hasCurrentYear) {
              setYearFrom(currentYear);
              // Find the first available month of the current year in the data
              const firstMonthOfCurrentYear = [...monthsData]
                .filter(d => d.year === currentYear)
                .sort((a, b) => a.month - b.month)[0].month;
              setMonthFrom(firstMonthOfCurrentYear);
            } else {
              setYearFrom(first.year);
              setMonthFrom(first.month);
            }

            setYearTo(last.year);
            setMonthTo(last.month);
          }
        }
      } catch (e) {
        console.error("Failed to load available months:", e);
      }
    };
    loadMonths();
  }, []);

  // Load Monthly Performance Summary on mount
  useEffect(() => {
    const loadMonthlyPNL = async () => {
      try {
        const response = await fetch(`${BASE_URL}/performance/monthly-pnl`);
        if (response.ok) {
          const res = await response.json();
          setMonthlyPNL(res.data && Array.isArray(res.data) ? res.data : []);
        }
      } catch (error) {
        console.error("Error loading monthly P&L:", error);
      }
    };
    loadMonthlyPNL();
  }, []);

  // Load saved scenarios on mount
  useEffect(() => {
    fetch(`${BASE_URL}/scenarios`)
      .then(r => r.ok ? r.json() : [])
      .then(setScenarios)
      .catch(() => {});
  }, []);

  // Re-simulate active positions and chart markers whenever strategy parameters change
  useEffect(() => {
    if (!replayData || currentIndex === 0) return;
    const activeIdx = Math.max(0, currentIndex - 1);
    const candle = replayData.candles[activeIdx];
    if (!candle) return;

    let profit = 0;
    let total = 0;
    let wins = 0;
    let losses = 0;
    const activePosList: any[] = [];

    const m15Data = allReplayData.M15 ?? (replayData.meta.timeframe === "M15" ? replayData : null);
    const h1Data = allReplayData.H1 ?? (replayData.meta.timeframe === "H1" ? replayData : null);
    const h4Data = allReplayData.H4 ?? (replayData.meta.timeframe === "H4" ? replayData : null);
    const m15Candles = m15Data?.candles ?? [];
    const h1Candles = h1Data?.candles ?? [];
    const h4Candles = h4Data?.candles ?? [];

    const { executedTrades, rejectedTrades } = getProcessedReplayTrades(
      replayData,
      replayData.structures,
      entryFilterParams,
      m15Candles,
      h1Candles,
      h4Candles,
      useLLMSetup || decisionEngine === "llm",
    );

    const llmEntryTimes = new Set(llmPositions.map(p => p.entry_time ?? 0));
    for (const trade of rejectedTrades) {
      if ((trade.entry_time ?? 0) > candle.time) continue;
      if (llmEntryTimes.has(trade.entry_time ?? 0)) continue;
      activePosList.push({
        ticket: trade.ticket,
        type: trade.type,
        entry_time: trade.entry_time,
        lot_size: trade.lot_size ?? 0,
        entry_price: trade.entry_price ?? 0,
        current_price: null,
        sl: null,
        tp: null,
        original_sl: null,
        original_tp: null,
        status: "Rejected",
        reject_reason: trade.reject_reason,
        pnl: 0,
        is_rejected: true,
      });
    }

    const filteredTrades = executedTrades;
    for (const t of filteredTrades) {
      const entryTs = t.entry_time ?? 0;
      if (entryTs <= candle.time) {
        total++;
        const exitTs = t.exit_time;

        const actualLot = getActualLotSize(t);
        const lotSize = strategyParams.lot_override > 0 ? strategyParams.lot_override : actualLot;

        const simTime = exitTs !== null ? Math.min(candle.time, exitTs) : candle.time;
        const dynamicLevels = simulateTrailingSLTP(t, replayData.candles, simTime, replayData.structures, strategyParams);
        const isClosedOriginal = exitTs !== null && exitTs <= candle.time;

        if (dynamicLevels.isClosedSimulated || isClosedOriginal) {
          // Closed trade: use net profit (scaled or simulated)
          let tradeProfit = 0;
          const exitPrice = dynamicLevels.isClosedSimulated
            ? (dynamicLevels.exitPriceSimulated ?? (t.entry_price ?? 0))
            : (t.exit_price ?? (t.entry_price ?? 0));
          if (dynamicLevels.isClosedSimulated) {
            const entryPrice = t.entry_price ?? 0;
            const typeLower = t.type.toLowerCase();
            if (typeLower === "buy") {
              tradeProfit = (exitPrice - entryPrice) * lotSize * 100;
            } else {
              tradeProfit = (entryPrice - exitPrice) * lotSize * 100;
            }
          } else {
            tradeProfit = t.net_profit ?? 0;
            if (strategyParams.lot_override > 0 && actualLot > 0) {
              tradeProfit = (tradeProfit * strategyParams.lot_override) / actualLot;
            }
          }
          profit += tradeProfit;
          if (tradeProfit > 0) wins++;
          else if (tradeProfit < 0) losses++;
          // Tetap tampilkan di tabel dengan flag is_closed
          activePosList.push({
            ticket: t.ticket,
            type: t.type,
            entry_time: t.entry_time,
            lot_size: lotSize,
            entry_price: t.entry_price ?? 0,
            current_price: exitPrice,
            sl: dynamicLevels.sl,
            tp: dynamicLevels.tp,
            original_sl: dynamicLevels.initialSL,
            original_tp: dynamicLevels.initialTP,
            status: "Closed",
            pnl: tradeProfit,
            be_trigger_price: null,
            is_be_active: false,
            tp_trigger_price: null,
            is_tp_maxed: false,
            is_closed: true,
          });
        } else {
          // Open trade: calculate running floating PnL
          const entryPrice = t.entry_price ?? 0;
          const typeLower = t.type.toLowerCase();

          let floatingPnL = 0;
          if (typeLower === "buy") {
            floatingPnL = (candle.close - entryPrice) * lotSize * 100;
          } else if (typeLower === "sell") {
            floatingPnL = (entryPrice - candle.close) * lotSize * 100;
          }
          profit += floatingPnL;

          // Calculate initial levels
          const initialSL = dynamicLevels.initialSL;
          const initialTP = dynamicLevels.initialTP;

          // Determine status flags
          const isBEActive = dynamicLevels.beTriggered;
          const isTPExpanded = dynamicLevels.tp !== null && Math.abs(dynamicLevels.tp - initialTP) > 0.01;
          const isSLTrailing = dynamicLevels.sl !== null && Math.abs(dynamicLevels.sl - initialSL) > 0.01;

          let statusText = "Normal";
          if (isBEActive && isTPExpanded) {
            statusText = "BE + TP Expanded";
          } else if (isBEActive) {
            statusText = "Break-Even";
          } else if (isTPExpanded) {
            statusText = "TP Expanded";
          } else if (isSLTrailing) {
            statusText = "Trailing";
          }

          // Compute trigger prices
          const beTriggerPrice = strategyParams.enable_breakeven
            ? (typeLower === "buy" ? entryPrice + strategyParams.breakeven_trigger : entryPrice - strategyParams.breakeven_trigger)
            : null;

          const isTPMaxed = strategyParams.max_ekspansi > 0 && dynamicLevels.expansionCount >= strategyParams.max_ekspansi;
          const tpTriggerPrice = isTPMaxed
            ? null
            : (dynamicLevels.tp !== null
                ? (typeLower === "buy" ? dynamicLevels.tp - strategyParams.tp_trigger : dynamicLevels.tp + strategyParams.tp_trigger)
                : null
              );

          activePosList.push({
            ticket: t.ticket,
            type: t.type,
            entry_time: t.entry_time,
            lot_size: lotSize,
            entry_price: entryPrice,
            current_price: candle.close,
            sl: dynamicLevels.sl,
            tp: dynamicLevels.tp,
            original_sl: initialSL,
            original_tp: initialTP,
            status: statusText,
            pnl: floatingPnL,
            be_trigger_price: beTriggerPrice,
            is_be_active: isBEActive,
            tp_trigger_price: tpTriggerPrice,
            is_tp_maxed: isTPMaxed,
          });
        }
      }
    }

    // Process LLM positions in the active positions table & metrics
    for (const llmPos of llmPositions) {
      const entryTs = llmPos.entry_time ?? 0;
      if (entryTs <= candle.time) {
        if (llmPos.is_rejected) {
          activePosList.push({
            ticket: llmPos.ticket,
            type: llmPos.type,
            entry_time: llmPos.entry_time,
            lot_size: llmPos.lot_size ?? 0,
            entry_price: llmPos.entry_price ?? 0,
            current_price: null,
            sl: null,
            tp: null,
            original_sl: null,
            original_tp: null,
            status: "Rejected",
            reject_reason: llmPos.reject_reason || "Ditolak / HOLD",
            pnl: 0,
            is_rejected: true,
            is_llm: true,
          });
          continue;
        }

        total++;
        const typeUpper = (llmPos.type ?? "BUY").toUpperCase();
        const isBuy = typeUpper === "BUY";
        const lotSize = llmPos.lot_size ?? 0.01;
        const entryPrice = llmPos.entry_price ?? 0;
        const slPrice = llmPos.sl ?? 0;
        const tpPrice = llmPos.tp ?? 0;

        // Check historical candles between entry and current candle to see if SL/TP was hit
        let isClosed = false;
        let exitPrice = candle.close;
        let exitTime: number | null = null;
        let statusText = "Running";

        const entryCandleIdx = replayData.candles.findIndex(c => c.time >= entryTs);
        const startIdx = entryCandleIdx >= 0 ? entryCandleIdx : 0;
        const endIdx = activeIdx;

        for (let i = startIdx; i <= endIdx; i++) {
          const c = replayData.candles[i];
          if (!c) continue;

          // Force 24h close check: 86400 seconds = 24 hours
          if (strategyParams.force_24h_close && (c.time - entryTs) >= 86400) {
            isClosed = true;
            exitPrice = c.close;
            exitTime = c.time;
            statusText = "Closed (24h)";
            break;
          }

          if (isBuy) {
            if (slPrice > 0 && c.low <= slPrice) {
              isClosed = true;
              exitPrice = slPrice;
              exitTime = c.time;
              statusText = "Closed (SL)";
              break;
            } else if (tpPrice > 0 && c.high >= tpPrice) {
              isClosed = true;
              exitPrice = tpPrice;
              exitTime = c.time;
              statusText = "Closed (TP)";
              break;
            }
          } else {
            if (slPrice > 0 && c.high >= slPrice) {
              isClosed = true;
              exitPrice = slPrice;
              exitTime = c.time;
              statusText = "Closed (SL)";
              break;
            } else if (tpPrice > 0 && c.low <= tpPrice) {
              isClosed = true;
              exitPrice = tpPrice;
              exitTime = c.time;
              statusText = "Closed (TP)";
              break;
            }
          }
        }

        let pnl = 0;
        if (isClosed) {
          if (isBuy) {
            pnl = (exitPrice - entryPrice) * lotSize * 100;
          } else {
            pnl = (entryPrice - exitPrice) * lotSize * 100;
          }
          if (pnl > 0) wins++;
          else if (pnl < 0) losses++;
        } else {
          if (isBuy) {
            pnl = (candle.close - entryPrice) * lotSize * 100;
          } else {
            pnl = (entryPrice - candle.close) * lotSize * 100;
          }
        }
        profit += pnl;

        activePosList.push({
          ticket: llmPos.ticket,
          type: typeUpper,
          entry_time: entryTs,
          lot_size: lotSize,
          entry_price: entryPrice,
          current_price: isClosed ? exitPrice : candle.close,
          sl: slPrice,
          tp: tpPrice,
          original_sl: llmPos.original_sl ?? slPrice,
          original_tp: llmPos.original_tp ?? tpPrice,
          status: statusText,
          pnl: pnl,
          be_trigger_price: null,
          is_be_active: false,
          tp_trigger_price: null,
          is_tp_maxed: false,
          is_closed: isClosed,
          is_llm: true,
          exit_time: exitTime,
        });
      }
    }

    setRunningProfit(profit);
    setTradeStats({ total, wins, losses });
    setActivePositions(activePosList.sort((a, b) => (b.entry_time ?? Number.MIN_SAFE_INTEGER) - (a.entry_time ?? Number.MIN_SAFE_INTEGER)));

    // Also update chart markers
    if (tradesPrimitiveRef.current) {
      const mapped = filteredTrades
        .filter(t => (t.entry_time ?? 0) <= candle.time)
        .map(t => {
          const entryTs = t.entry_time ?? 0;
          const exitTs = t.exit_time;
          const simTime = exitTs !== null ? Math.min(candle.time, exitTs) : candle.time;
          const dynamicLevels = simulateTrailingSLTP(t, replayData.candles, simTime, replayData.structures, strategyParams);

          const isClosedOriginal = exitTs !== null && exitTs <= candle.time;
          const isClosed = dynamicLevels.isClosedSimulated || isClosedOriginal;
          const finalExitPrice = (dynamicLevels.isClosedSimulated
            ? (dynamicLevels.exitPriceSimulated ?? t.entry_price)
            : (isClosedOriginal ? t.exit_price : t.entry_price)) ?? 0;
          const finalExitTs = dynamicLevels.isClosedSimulated
            ? (dynamicLevels.exitTimeSimulated ?? null)
            : (isClosedOriginal ? exitTs : null);

          // Calculate profit
          let finalProfit = t.net_profit ?? 0;
          const actualLot = getActualLotSize(t);
          if (strategyParams.lot_override > 0 && actualLot > 0) {
            finalProfit = (finalProfit * strategyParams.lot_override) / actualLot;
          }
          if (dynamicLevels.isClosedSimulated) {
            const lotSize = strategyParams.lot_override > 0 ? strategyParams.lot_override : actualLot;
            const entryPrice = t.entry_price ?? 0;
            const typeLower = t.type.toLowerCase();
            if (typeLower === "buy") {
              finalProfit = (finalExitPrice - entryPrice) * lotSize * 100;
            } else {
              finalProfit = (entryPrice - finalExitPrice) * lotSize * 100;
            }
          }

          return {
            type: t.type,
            entry_price: t.entry_price ?? 0,
            sl: dynamicLevels.sl,
            tp: dynamicLevels.tp,
            profit: finalProfit,
            entry_time_ts: entryTs,
            exit_time_ts: isClosed ? finalExitTs : null,
            // ATR band: value + candle range (start = entry - period bars, end = entry)
            atr: (strategyParams.use_atr_sltp || useLLMSetup) ? calculateATR(replayData.candles, entryTs, strategyParams.atr_period) : null,
            atr_start_ts: (strategyParams.use_atr_sltp || useLLMSetup) ? entryTs - strategyParams.atr_period * 900 : null,
            atr_end_ts: (strategyParams.use_atr_sltp || useLLMSetup) ? entryTs : null,
          };
        });

      if (activePlanner) {
        const exitTs = activePlanner.exitTime ?? (activePlanner.entryTime + (activePlanner.durationBars || 15) * 900);
        mapped.push({
          type: activePlanner.type === "long" ? "BUY" : "SELL",
          entry_price: activePlanner.entryPrice,
          sl: activePlanner.slPrice,
          tp: activePlanner.tpPrice,
          profit: 0,
          entry_time_ts: activePlanner.entryTime,
          exit_time_ts: exitTs,
          atr: null,
          atr_start_ts: null,
          atr_end_ts: null,
        });
      }

      const lastTime = candle?.time ?? null;
      if (lastTime !== null) {
        tradesPrimitiveRef.current.setLastCandleTime(lastTime);
      }
      tradesPrimitiveRef.current.setTimeframe(activeTimeframe);
      // Merge LLM-executed positions so they persist across replay re-renders.
      const isAtrEnabled = strategyParams.use_atr_sltp || useLLMSetup;
      const merged = [
        ...mapped,
        ...llmPositions
          .filter(p => !p.is_rejected && (p.entry_time ?? 0) <= candle.time)
          .map(p => {
            const entryTs = p.entry_time ?? 0;
            const posInList = activePosList.find(pos => pos.ticket === p.ticket);
            return {
              type: p.type,
              entry_price: p.entry_price,
              sl: p.sl,
              tp: p.tp,
              profit: posInList?.pnl ?? 0,
              entry_time_ts: entryTs,
              exit_time_ts: posInList?.is_closed ? posInList.exit_time : null,
              atr: isAtrEnabled ? calculateATR(replayData.candles, entryTs, strategyParams.atr_period) : null,
              atr_start_ts: isAtrEnabled ? entryTs - strategyParams.atr_period * 900 : null,
              atr_end_ts: isAtrEnabled ? entryTs : null,
            };
          }),
      ];
      tradesPrimitiveRef.current.setTrades(merged);
    }

    if (supplyDemandPrimitiveRef.current && candle) {
      supplyDemandPrimitiveRef.current.setVisible(strategyParams.show_supply_demand);
      if (strategyParams.show_supply_demand) {
        const sdZones = calculateSupplyDemandZones(replayData.candles, replayData.structures, candle.time);
        supplyDemandPrimitiveRef.current.setLastCandleTime(candle.time);
        supplyDemandPrimitiveRef.current.setZones(sdZones);
      } else {
        supplyDemandPrimitiveRef.current.setZones([]);
      }
    }

    if (liquidityPoolsPrimitiveRef.current && candle) {
      liquidityPoolsPrimitiveRef.current.setVisible(strategyParams.show_liquidity_pools);
      if (strategyParams.show_liquidity_pools) {
        const pools = calculateLiquidityPools(replayData.candles, replayData.structures, candle.time);
        liquidityPoolsPrimitiveRef.current.setLastCandleTime(candle.time);
        liquidityPoolsPrimitiveRef.current.setPools(pools);
      } else {
        liquidityPoolsPrimitiveRef.current.setPools([]);
      }
    }
  }, [strategyParams, entryFilterParams, replayData, currentIndex, activeTimeframe, activePlanner, llmPositions, allReplayData, useLLMSetup]);

  const setChartDataToIndex = useCallback((targetIdx: number, data: ReplayData) => {
    if (!data) return;
    const limit = Math.min(targetIdx, data.candles.length);
    
    // 1. Prepare candles array
    const chartCandles = data.candles.slice(0, limit).map(c => ({
      time: c.time as any,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    candleSeriesRef.current?.setData(chartCandles);

    // 2. Prepare EMA200 array
    const chartEMA = data.candles.slice(0, limit)
      .filter(c => c.ema200 !== null)
      .map(c => ({
        time: c.time as any,
        value: c.ema200,
      }));
    emaSeriesRef.current?.setData(chartEMA as any);

    const chartMA20 = data.candles.slice(0, limit)
      .map((candle, index) => {
        const value = getSimpleMovingAverage(data.candles, index, 20);
        return value === null ? null : { time: candle.time as any, value };
      })
      .filter((point): point is { time: any; value: number } => point !== null);
    ma20SeriesRef.current?.setData(chartMA20 as any);

    const chartMA50 = data.candles.slice(0, limit)
      .map((candle, index) => {
        const value = getSimpleMovingAverage(data.candles, index, 50);
        return value === null ? null : { time: candle.time as any, value };
      })
      .filter((point): point is { time: any; value: number } => point !== null);
    ma50SeriesRef.current?.setData(chartMA50 as any);

    // 3. Update structure markers
    if (limit > 0) {
      const lastCandle = data.candles[limit - 1];
      const markers: any[] = [];
      for (const s of data.structures) {
        if (s.time <= lastCandle.time) {
          const color = STRUCTURE_COLORS[s.type?.toUpperCase()] ?? "#94a3b8";
          const typeUpper = s.type?.toUpperCase() ?? "";
          const dirLower = s.direction?.toLowerCase() ?? "";

          let position: "aboveBar" | "belowBar";
          if (typeUpper === "HH" || typeUpper === "LH") {
            position = "aboveBar";
          } else if (typeUpper === "HL" || typeUpper === "LL") {
            position = "belowBar";
          } else {
            position = dirLower.includes("bear") ? "aboveBar" : "belowBar";
          }

          markers.push({
            time: s.time as any,
            position,
            color,
            shape: "arrowDown",
            text: typeUpper,
          });
        }
      }
      markersPluginRef.current?.setMarkers(markers);

      if (supplyDemandPrimitiveRef.current && limit > 0) {
        const lastCandle = data.candles[limit - 1];
        supplyDemandPrimitiveRef.current.setVisible(strategyParams.show_supply_demand);
        if (strategyParams.show_supply_demand && lastCandle) {
          const sdZones = calculateSupplyDemandZones(data.candles, data.structures, lastCandle.time);
          supplyDemandPrimitiveRef.current.setLastCandleTime(lastCandle.time);
          supplyDemandPrimitiveRef.current.setZones(sdZones);
        } else {
          supplyDemandPrimitiveRef.current.setZones([]);
        }
      }

      if (liquidityPoolsPrimitiveRef.current && limit > 0) {
        const lastCandle = data.candles[limit - 1];
        liquidityPoolsPrimitiveRef.current.setVisible(strategyParams.show_liquidity_pools);
        if (strategyParams.show_liquidity_pools && lastCandle) {
          const pools = calculateLiquidityPools(data.candles, data.structures, lastCandle.time);
          liquidityPoolsPrimitiveRef.current.setLastCandleTime(lastCandle.time);
          liquidityPoolsPrimitiveRef.current.setPools(pools);
        } else {
          liquidityPoolsPrimitiveRef.current.setPools([]);
        }
      }
    } else {
      markersPluginRef.current?.setMarkers([]);
      structurePrimitiveRef.current?.setLines([]);
      tradesPrimitiveRef.current?.setTrades([]);
      supplyDemandPrimitiveRef.current?.setZones([]);
      liquidityPoolsPrimitiveRef.current?.setPools([]);
    }

    if (chartRef.current && limit > 0) {
      followReplayPlayhead(chartRef.current);
    }
  }, [strategyParams.show_supply_demand, strategyParams.show_liquidity_pools]);

  // ── Load Data ────────────────────────────────────────────────────────────

  const handleLoad = useCallback(async () => {
    if (isPlaying) stopPlayback();
    setIsLoading(true);
    setLoadError(null);
    setCurrentIndex(0);
    setRunningProfit(0);
    setTradeStats({ total: 0, wins: 0, losses: 0 });
    setActivePositions([]);
    // Reset LLM auto-trigger dedup on fresh load.
    processedLLMEventsRef.current.clear();
    setLlmRecommendation(null);
    setLlmPositions([]);

    // Clear chart
    candleSeriesRef.current?.setData([]);
    emaSeriesRef.current?.setData([]);
    ma20SeriesRef.current?.setData([]);
    ma50SeriesRef.current?.setData([]);
    structurePrimitiveRef.current?.setLines([]);
    tradesPrimitiveRef.current?.setTrades([]);
    supplyDemandPrimitiveRef.current?.setZones([]);
    liquidityPoolsPrimitiveRef.current?.setPools([]);

    // Initialize progress bar simulation
    setLoadProgress({
      visible: true,
      percent: 0,
      step: "Connecting to database...",
    });

    let currentPercent = 0;
    let step = "Connecting to database...";
    const interval = setInterval(() => {
      if (currentPercent < 25) {
        currentPercent += 4;
        step = "Connecting to database...";
      } else if (currentPercent < 80) {
        currentPercent += 2.5;
        step = "Fetching all timeframes (M15, H1, H4) candles & structures...";
      } else if (currentPercent < 95) {
        currentPercent += 0.5;
        step = "Processing indicator caches & EMA200...";
      }
      setLoadProgress({
        visible: true,
        percent: Math.min(95, Math.round(currentPercent)),
        step,
      });
    }, 45);

    try {
      const timeframes = ["M15", "H1", "H4"];
      const results = await Promise.all(
        timeframes.map(tf => fetchReplayData(yearFrom, monthFrom, yearTo, monthTo, tf))
      );
      clearInterval(interval);

      // Transition to 100% complete
      setLoadProgress({
        visible: true,
        percent: 100,
        step: "Complete!",
      });

      // Brief delay to let the user see the complete state
      await new Promise(resolve => setTimeout(resolve, 300));

      const loadedDataMap: Record<string, ReplayData> = {};
      timeframes.forEach((tf, idx) => {
        loadedDataMap[tf] = results[idx];
      });
      allReplayDataRef.current = loadedDataMap;
      setAllReplayData(loadedDataMap);

      // Default load activeTimeframe data into active display
      const currentData = loadedDataMap[activeTimeframe];
      if (currentData) {
        setReplayData(currentData);
        candleTimeArrayRef.current = currentData.candles.map(c => c.time);
        const map = new Map<number, ReplayCandle>();
        currentData.candles.forEach(c => map.set(c.time, c));
        candleTimeMapRef.current = map;
      }
    } catch (err: unknown) {
      clearInterval(interval);
      setLoadError(err instanceof Error ? err.message : "Gagal memuat data");
    } finally {
      setIsLoading(false);
      setLoadProgress(prev => ({ ...prev, visible: false }));
    }
  }, [yearFrom, monthFrom, yearTo, monthTo, isPlaying, activeTimeframe]);

  const handleTimeframeChange = useCallback((tf: string) => {
    if (isPlaying) stopPlayback();

    const currentData = replayData;
    let targetTime = 0;
    if (currentData && currentData.candles.length > 0) {
      const activeCandle = currentData.candles[Math.max(0, currentIndex - 1)];
      if (activeCandle) {
        targetTime = activeCandle.time;
      }
    }

    setActiveTimeframe(tf);

    const newData = allReplayData[tf];
    if (newData) {
      setReplayData(newData);
      candleTimeArrayRef.current = newData.candles.map(c => c.time);
      const map = new Map<number, ReplayCandle>();
      newData.candles.forEach(c => map.set(c.time, c));
      candleTimeMapRef.current = map;

      let newIndex = 0;
      if (targetTime > 0) {
        const idx = newData.candles.findIndex(c => c.time > targetTime);
        newIndex = idx === -1 ? newData.candles.length : idx;
      }

      setChartDataToIndex(newIndex, newData);
      setCurrentIndex(newIndex);
    }
  }, [isPlaying, replayData, currentIndex, allReplayData, setChartDataToIndex, stopPlayback]);

  const handleMonthRowClick = useCallback(async (year: number, monthNum: number, monthLabel: string) => {
    setIsLoadingTrades(true);
    setModalTitle(monthLabel);
    setIsModalOpen(true);
    setSelectedMonthTrades([]);

    try {
      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiUrl}/performance/backtest/monthly-trades?year=${year}&month=${monthNum}`);
      if (response.ok) {
        const result = await response.json();
        setSelectedMonthTrades(result.data || []);
      }
    } catch (error) {
      console.error("Error loading monthly trades:", error);
    } finally {
      setIsLoadingTrades(false);
    }
  }, []);

  // ── Advance one candle ────────────────────────────────────────────────────

  const advanceCandle = useCallback((idx: number, data: ReplayData) => {
    if (idx >= data.candles.length) return idx;

    const candle = data.candles[idx];

    // Add candle
    candleSeriesRef.current?.update({
      time: candle.time as any,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    });

    // Add EMA200
    if (candle.ema200 !== null) {
      emaSeriesRef.current?.update({ time: candle.time as any, value: candle.ema200 });
    }
    const ma20 = getSimpleMovingAverage(data.candles, idx, 20);
    if (ma20 !== null) {
      ma20SeriesRef.current?.update({ time: candle.time as any, value: ma20 });
    }
    const ma50 = getSimpleMovingAverage(data.candles, idx, 50);
    if (ma50 !== null) {
      ma50SeriesRef.current?.update({ time: candle.time as any, value: ma50 });
    }

    // Update structure markers — all events up to this candle
    const markers: any[] = [];
    for (const s of data.structures) {
      if (s.time <= candle.time) {
        const color = STRUCTURE_COLORS[s.type?.toUpperCase()] ?? "#94a3b8";
        const typeUpper = s.type?.toUpperCase() ?? "";
        const dirLower = s.direction?.toLowerCase() ?? "";

        // HH/LH → at the high (aboveBar), HL/LL → at the low (belowBar)
        // CHoCH/BOS → bearish = aboveBar, bullish = belowBar
        let position: "aboveBar" | "belowBar";
        if (typeUpper === "HH" || typeUpper === "LH") {
          position = "aboveBar";
        } else if (typeUpper === "HL" || typeUpper === "LL") {
          position = "belowBar";
        } else {
          // CHoCH, BOS — use direction field
          position = dirLower.includes("bear") ? "aboveBar" : "belowBar";
        }

        markers.push({
          time: s.time as any,
          position,
          color,
          shape: "circle",
          text: "", // Remove text label completely to avoid layout clutter
          size: 0.6,
        });
      }
    }

    markersPluginRef.current?.setMarkers(markers);

    // Update structure lines
    const lowerBound = (target: number): number => {
      const arr = candleTimeArrayRef.current;
      let lo = 0, hi = arr.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (arr[mid] < target) lo = mid + 1;
        else hi = mid;
      }
      return lo;
    };

    // Pre-build a list of BOS/CHOCH events in the dataset to find breaks
    const bosChochEvents = data.structures.filter(evt => {
      const t = evt.type?.toUpperCase();
      return t === "BOS" || t === "CHOCH";
    });

    const isLevelBrokenAtPlayhead = (h: StructureEvent, currentCandleTime: number): boolean => {
      const hType = h.type?.toUpperCase();
      if (hType !== "HH" && hType !== "LL" && hType !== "LH" && hType !== "HL") {
        return false;
      }

      const hBucket = Math.round(h.price / 0.05);

      // Find if there is a BOS/CHOCH event that breaks this HH/LL level
      const breakEvent = bosChochEvents.find(b => {
        const bBucket = Math.round(b.price / 0.05);
        const priceMatch = Math.abs(bBucket - hBucket) <= 1;
        const timeMatch = b.previous_time ? Math.abs(b.previous_time - h.time) <= 7200 : true;
        return priceMatch && timeMatch && b.time > h.time && b.timeframe === h.timeframe;
      });

      // It is broken if the playhead has reached the break time
      return breakEvent ? currentCandleTime >= breakEvent.time : false;
    };

    // Helper: find when a price level was first formed in HH/LL data.
    const findLevelFormationTime = (
      levelPrice: number,
      direction: string, // 'BULLISH' or 'BEARISH'
      eventTime: number,
      timeframe: string
    ): number | undefined => {
      const isBullish = direction?.toUpperCase() === 'BULLISH';
      const targetTypes = isBullish ? ["HH", "LH"] : ["LL", "HL"];

      let matchTime: number | undefined;
      for (const item of data.structures) {
        const itemType = item.type?.toUpperCase();
        if (targetTypes.includes(itemType) && item.time < eventTime && item.timeframe === timeframe) {
          // Check price with 0.08 tolerance
          if (Math.abs(item.price - levelPrice) <= 0.08) {
            if (matchTime === undefined || item.time < matchTime) {
              matchTime = item.time;
            }
          }
        }
      }
      return matchTime;
    };

    const linesToDraw: StructureLineItem[] = [];
    const currentCandleTime = candle.time;

    for (const s of data.structures) {
      const typeUpper = s.type?.toUpperCase() ?? "";
      const dirUpper = s.direction?.toUpperCase() ?? "";
      const isBullish = dirUpper === "BULLISH";

      if (typeUpper === "BOS" || typeUpper === "CHOCH") {
        // Only draw BOS/CHOCH line after the breakout has actually occurred at this playhead
        if (currentCandleTime < s.time) {
          continue;
        }

        const levelFormationTime = findLevelFormationTime(s.price, s.direction, s.time, s.timeframe);
        const startTime = levelFormationTime ?? s.previous_time ?? (s.time - 900);
        let endTime = s.time;

        // Cap or stop line if crossed/broken by any candle close before endTime
        const dirUp = isBullish;
        const startIdx = lowerBound(startTime + 1);
        const endIdx = lowerBound(endTime);
        for (let i = startIdx; i < endIdx; i++) {
          const c = data.candles[i];
          const crossed = dirUp ? c.close > s.price : c.close < s.price;
          if (crossed) {
            endTime = c.time;
            break;
          }
        }

        if (startTime < endTime) {
          linesToDraw.push({
            price: s.price,
            startTime,
            endTime,
            color: isBullish ? '#10b981' : '#ef4444',
            lineWidth: 2,
            lineStyle: typeUpper === "BOS" ? LineStyle.Solid : LineStyle.Dashed,
            label: `${typeUpper} ${s.price.toFixed(2)}`,
            isResistance: isBullish,
          });
        }
      } else if (typeUpper === "HH" || typeUpper === "LL" || typeUpper === "LH" || typeUpper === "HL") {
        // Skip HH/LL line drawing if it has already been broken by a BOS/CHOCH event at this playhead
        if (isLevelBrokenAtPlayhead(s, currentCandleTime)) {
          continue;
        }

        const startTime = s.time;
        if (startTime > currentCandleTime) continue; // Point not yet formed

        // Cap at 20 candles after formation
        const startIdx = lowerBound(startTime + 1);
        const maxIdx = Math.min(startIdx + 20, data.candles.length);

        let endTime = currentCandleTime;
        let broke = false;
        for (let i = startIdx; i < maxIdx; i++) {
          const c = data.candles[i];
          if (c.time > currentCandleTime) break;
          const crossed = (typeUpper === "HH" || typeUpper === "LH") ? c.close > s.price : c.close < s.price;
          if (crossed) {
            endTime = c.time;
            broke = true;
            break;
          }
        }

        if (!broke && maxIdx > startIdx) {
          const maxCandleTime = data.candles[maxIdx - 1].time;
          endTime = Math.min(maxCandleTime, currentCandleTime);
        }

        if (startTime < endTime) {
          const isHigh = typeUpper === "HH" || typeUpper === "LH";
          const color = isHigh ? '#60a5fa' : '#fb923c';
          linesToDraw.push({
            price: s.price,
            startTime,
            endTime,
            color,
            lineWidth: 1.5,
            lineStyle: LineStyle.Dotted,
            label: `${typeUpper} [M15] ${s.price.toFixed(2)}`,
            isResistance: isHigh,
          });
        }
      }
    }

    // Filter linesToDraw to only keep the oldest HH/LL line when multiple exist in the same price range
    const filteredLinesToDraw: StructureLineItem[] = [];
    const sortedLines = [...linesToDraw].sort((a, b) => a.startTime - b.startTime);
    for (const line of sortedLines) {
      const isHhOrLl = line.label.startsWith("HH") || line.label.startsWith("LL") ||
        line.label.startsWith("LH") || line.label.startsWith("HL");
      if (isHhOrLl) {
        const lineTypePrefix = line.label.slice(0, 2);
        const hasOlderSameLevel = filteredLinesToDraw.some(existing => {
          const existingTypePrefix = existing.label.slice(0, 2);
          const sameType = existingTypePrefix === lineTypePrefix;
          const samePrice = Math.abs(existing.price - line.price) <= 0.08;
          return sameType && samePrice;
        });
        if (hasOlderSameLevel) {
          continue;
        }
      }
      filteredLinesToDraw.push(line);
    }

    structurePrimitiveRef.current?.setLines(filteredLinesToDraw);

    // Update Supply & Demand zones primitive
    if (supplyDemandPrimitiveRef.current) {
      supplyDemandPrimitiveRef.current.setVisible(strategyParams.show_supply_demand);
      if (strategyParams.show_supply_demand) {
        const sdZones = calculateSupplyDemandZones(data.candles, data.structures, candle.time);
        supplyDemandPrimitiveRef.current.setLastCandleTime(candle.time);
        supplyDemandPrimitiveRef.current.setZones(sdZones);
      } else {
        supplyDemandPrimitiveRef.current.setZones([]);
      }
    }

    // Update Liquidity Pools primitive (BSL / SSL)
    if (liquidityPoolsPrimitiveRef.current) {
      liquidityPoolsPrimitiveRef.current.setVisible(strategyParams.show_liquidity_pools);
      if (strategyParams.show_liquidity_pools) {
        const pools = calculateLiquidityPools(data.candles, data.structures, candle.time);
        liquidityPoolsPrimitiveRef.current.setLastCandleTime(candle.time);
        liquidityPoolsPrimitiveRef.current.setPools(pools);
      } else {
        liquidityPoolsPrimitiveRef.current.setPools([]);
      }
    }

    // Update trades overlay
    const m15Data = allReplayData.M15 ?? (data.meta.timeframe === "M15" ? data : null);
    const h1Data = allReplayData.H1 ?? (data.meta.timeframe === "H1" ? data : null);
    const h4Data = allReplayData.H4 ?? (data.meta.timeframe === "H4" ? data : null);
    const m15Candles = m15Data?.candles ?? [];
    const h1Candles = h1Data?.candles ?? [];
    const h4Candles = h4Data?.candles ?? [];

    const { executedTrades, rejectedTrades } = getProcessedReplayTrades(
      data,
      data.structures,
      entryFilterParams,
      m15Candles,
      h1Candles,
      h4Candles,
      useLLMSetup || decisionEngine === "llm",
    );
    const filteredTrades = executedTrades;

    // Track running trade stats
    let profit = 0;
    let total = 0;
    let wins = 0;
    let losses = 0;
    const activePosList: any[] = [];

    const llmEntryTimes = new Set(llmPositions.map(p => p.entry_time ?? 0));
    for (const trade of rejectedTrades) {
      if ((trade.entry_time ?? 0) > candle.time) continue;
      if (llmEntryTimes.has(trade.entry_time ?? 0)) continue;
      activePosList.push({
        ticket: trade.ticket,
        type: trade.type,
        entry_time: trade.entry_time,
        lot_size: trade.lot_size ?? 0,
        entry_price: trade.entry_price ?? 0,
        current_price: null,
        sl: null,
        tp: null,
        original_sl: null,
        original_tp: null,
        status: "Rejected",
        reject_reason: trade.reject_reason,
        pnl: 0,
        is_rejected: true,
      });
    }

    for (const t of filteredTrades) {
      const entryTs = t.entry_time ?? 0;
      if (entryTs <= candle.time) {
        total++;
        const exitTs = t.exit_time;

        const actualLot = getActualLotSize(t);
        const lotSize = strategyParams.lot_override > 0 ? strategyParams.lot_override : actualLot;

        const simTime = exitTs !== null ? Math.min(candle.time, exitTs) : candle.time;
        const dynamicLevels = simulateTrailingSLTP(t, data.candles, simTime, data.structures, strategyParams);
        const isClosedOriginal = exitTs !== null && exitTs <= candle.time;

        if (dynamicLevels.isClosedSimulated || isClosedOriginal) {
          // Closed trade: use net profit (scaled or simulated)
          let tradeProfit = 0;
          const exitPrice = dynamicLevels.isClosedSimulated
            ? (dynamicLevels.exitPriceSimulated ?? (t.entry_price ?? 0))
            : (t.exit_price ?? (t.entry_price ?? 0));
          if (dynamicLevels.isClosedSimulated) {
            const entryPrice = t.entry_price ?? 0;
            const typeLower = t.type.toLowerCase();
            if (typeLower === "buy") {
              tradeProfit = (exitPrice - entryPrice) * lotSize * 100;
            } else {
              tradeProfit = (entryPrice - exitPrice) * lotSize * 100;
            }
          } else {
            tradeProfit = t.net_profit ?? 0;
            if (strategyParams.lot_override > 0 && actualLot > 0) {
              tradeProfit = (tradeProfit * strategyParams.lot_override) / actualLot;
            }
          }
          profit += tradeProfit;
          if (tradeProfit > 0) wins++;
          else if (tradeProfit < 0) losses++;
          activePosList.push({
            ticket: t.ticket,
            type: t.type,
            entry_time: t.entry_time,
            lot_size: lotSize,
            entry_price: t.entry_price ?? 0,
            current_price: exitPrice,
            sl: dynamicLevels.sl,
            tp: dynamicLevels.tp,
            original_sl: dynamicLevels.initialSL,
            original_tp: dynamicLevels.initialTP,
            status: "Closed",
            pnl: tradeProfit,
            be_trigger_price: null,
            is_be_active: false,
            tp_trigger_price: null,
            is_tp_maxed: false,
            is_closed: true,
          });
        } else {
          // Open trade: calculate running floating PnL
          const entryPrice = t.entry_price ?? 0;
          const typeLower = t.type.toLowerCase();

          let floatingPnL = 0;
          if (typeLower === "buy") {
            floatingPnL = (candle.close - entryPrice) * lotSize * 100;
          } else if (typeLower === "sell") {
            floatingPnL = (entryPrice - candle.close) * lotSize * 100;
          }
          profit += floatingPnL;

          // Calculate initial levels
          const initialSL = dynamicLevels.initialSL;
          const initialTP = dynamicLevels.initialTP;

          // Determine status flags
          const isBEActive = dynamicLevels.beTriggered;
          const isTPExpanded = dynamicLevels.tp !== null && Math.abs(dynamicLevels.tp - initialTP) > 0.01;
          const isSLTrailing = dynamicLevels.sl !== null && Math.abs(dynamicLevels.sl - initialSL) > 0.01;

          let statusText = "Normal";
          if (isBEActive && isTPExpanded) {
            statusText = "BE + TP Expanded";
          } else if (isBEActive) {
            statusText = "Break-Even";
          } else if (isTPExpanded) {
            statusText = "TP Expanded";
          } else if (isSLTrailing) {
            statusText = "Trailing";
          }

          // Compute trigger prices
          const beTriggerPrice = strategyParams.enable_breakeven
            ? (typeLower === "buy" ? entryPrice + strategyParams.breakeven_trigger : entryPrice - strategyParams.breakeven_trigger)
            : null;

          const isTPMaxed = strategyParams.max_ekspansi > 0 && dynamicLevels.expansionCount >= strategyParams.max_ekspansi;
          const tpTriggerPrice = isTPMaxed
            ? null
            : (dynamicLevels.tp !== null
                ? (typeLower === "buy" ? dynamicLevels.tp - strategyParams.tp_trigger : dynamicLevels.tp + strategyParams.tp_trigger)
                : null
              );

          activePosList.push({
            ticket: t.ticket,
            type: t.type,
            entry_time: t.entry_time,
            lot_size: lotSize,
            entry_price: entryPrice,
            current_price: candle.close,
            sl: dynamicLevels.sl,
            tp: dynamicLevels.tp,
            original_sl: initialSL,
            original_tp: initialTP,
            status: statusText,
            pnl: floatingPnL,
            be_trigger_price: beTriggerPrice,
            is_be_active: isBEActive,
            tp_trigger_price: tpTriggerPrice,
            is_tp_maxed: isTPMaxed,
          });
        }
      }
    }

    // Process LLM positions in advanceCandle
    for (const llmPos of llmPositions) {
      const entryTs = llmPos.entry_time ?? 0;
      if (entryTs <= candle.time) {
        if (llmPos.is_rejected) {
          activePosList.push({
            ticket: llmPos.ticket,
            type: llmPos.type,
            entry_time: llmPos.entry_time,
            lot_size: llmPos.lot_size ?? 0,
            entry_price: llmPos.entry_price ?? 0,
            current_price: null,
            sl: null,
            tp: null,
            original_sl: null,
            original_tp: null,
            status: "Rejected",
            reject_reason: llmPos.reject_reason || "Ditolak / HOLD",
            pnl: 0,
            is_rejected: true,
            is_llm: true,
          });
          continue;
        }

        total++;
        const typeUpper = (llmPos.type ?? "BUY").toUpperCase();
        const isBuy = typeUpper === "BUY";
        const lotSize = llmPos.lot_size ?? 0.01;
        const entryPrice = llmPos.entry_price ?? 0;
        const slPrice = llmPos.sl ?? 0;
        const tpPrice = llmPos.tp ?? 0;

        let isClosed = false;
        let exitPrice = candle.close;
        let exitTime: number | null = null;
        let statusText = "Running";

        const entryCandleIdx = data.candles.findIndex(c => c.time >= entryTs);
        const startIdx = entryCandleIdx >= 0 ? entryCandleIdx : 0;
        const endIdx = idx;

        for (let i = startIdx; i <= endIdx; i++) {
          const c = data.candles[i];
          if (!c) continue;

          // Force 24h close check: 86400 seconds = 24 hours
          if (strategyParams.force_24h_close && (c.time - entryTs) >= 86400) {
            isClosed = true;
            exitPrice = c.close;
            exitTime = c.time;
            statusText = "Closed (24h)";
            break;
          }

          if (isBuy) {
            if (slPrice > 0 && c.low <= slPrice) {
              isClosed = true;
              exitPrice = slPrice;
              exitTime = c.time;
              statusText = "Closed (SL)";
              break;
            } else if (tpPrice > 0 && c.high >= tpPrice) {
              isClosed = true;
              exitPrice = tpPrice;
              exitTime = c.time;
              statusText = "Closed (TP)";
              break;
            }
          } else {
            if (slPrice > 0 && c.high >= slPrice) {
              isClosed = true;
              exitPrice = slPrice;
              exitTime = c.time;
              statusText = "Closed (SL)";
              break;
            } else if (tpPrice > 0 && c.low <= tpPrice) {
              isClosed = true;
              exitPrice = tpPrice;
              exitTime = c.time;
              statusText = "Closed (TP)";
              break;
            }
          }
        }

        let pnl = 0;
        if (isClosed) {
          if (isBuy) {
            pnl = (exitPrice - entryPrice) * lotSize * 100;
          } else {
            pnl = (entryPrice - exitPrice) * lotSize * 100;
          }
          if (pnl > 0) wins++;
          else if (pnl < 0) losses++;
        } else {
          if (isBuy) {
            pnl = (candle.close - entryPrice) * lotSize * 100;
          } else {
            pnl = (entryPrice - candle.close) * lotSize * 100;
          }
        }
        profit += pnl;

        activePosList.push({
          ticket: llmPos.ticket,
          type: typeUpper,
          entry_time: entryTs,
          lot_size: lotSize,
          entry_price: entryPrice,
          current_price: isClosed ? exitPrice : candle.close,
          sl: slPrice,
          tp: tpPrice,
          original_sl: llmPos.original_sl ?? slPrice,
          original_tp: llmPos.original_tp ?? tpPrice,
          status: statusText,
          pnl: pnl,
          be_trigger_price: null,
          is_be_active: false,
          tp_trigger_price: null,
          is_tp_maxed: false,
          is_closed: isClosed,
          is_llm: true,
          exit_time: exitTime,
        });
      }
    }

    setRunningProfit(profit);
    setTradeStats({ total, wins, losses });
    setActivePositions(activePosList.sort((a, b) => (b.entry_time ?? Number.MIN_SAFE_INTEGER) - (a.entry_time ?? Number.MIN_SAFE_INTEGER)));

    // Update chart trades overlay
    if (tradesPrimitiveRef.current) {
      const isAtrEnabled = strategyParams.use_atr_sltp || useLLMSetup;
      const entries: TradeOverlayEntry[] = filteredTrades
        .filter(t => (t.entry_time ?? 0) <= candle.time)
        .map(t => {
          const entryTs = t.entry_time ?? 0;
          const exitTs = t.exit_time;
          const simTime = exitTs !== null ? Math.min(candle.time, exitTs) : candle.time;
          const dynamicLevels = simulateTrailingSLTP(t, data.candles, simTime, data.structures, strategyParams);

          const isClosedOriginal = exitTs !== null && exitTs <= candle.time;
          const isClosed = dynamicLevels.isClosedSimulated || isClosedOriginal;
          const finalExitPrice = (dynamicLevels.isClosedSimulated
            ? (dynamicLevels.exitPriceSimulated ?? t.entry_price)
            : (isClosedOriginal ? t.exit_price : t.entry_price)) ?? 0;
          const finalExitTs = dynamicLevels.isClosedSimulated
            ? (dynamicLevels.exitTimeSimulated ?? null)
            : (isClosedOriginal ? exitTs : null);

          // Calculate profit
          let finalProfit = t.net_profit ?? 0;
          const actualLot = getActualLotSize(t);
          if (strategyParams.lot_override > 0 && actualLot > 0) {
            finalProfit = (finalProfit * strategyParams.lot_override) / actualLot;
          }
          if (dynamicLevels.isClosedSimulated) {
            const lotSize = strategyParams.lot_override > 0 ? strategyParams.lot_override : actualLot;
            const entryPrice = t.entry_price ?? 0;
            const typeLower = t.type.toLowerCase();
            if (typeLower === "buy") {
              finalProfit = (finalExitPrice - entryPrice) * lotSize * 100;
            } else {
              finalProfit = (entryPrice - finalExitPrice) * lotSize * 100;
            }
          }

          return {
            type: t.type,
            entry_price: t.entry_price ?? 0,
            sl: dynamicLevels.sl,
            tp: dynamicLevels.tp,
            profit: finalProfit,
            entry_time_ts: entryTs,
            exit_time_ts: isClosed ? finalExitTs : null,
            atr: isAtrEnabled ? calculateATR(data.candles, entryTs, strategyParams.atr_period) : null,
            atr_start_ts: isAtrEnabled ? entryTs - strategyParams.atr_period * 900 : null,
            atr_end_ts: isAtrEnabled ? entryTs : null,
          };
        });

      if (activePlanner) {
        const exitTs = activePlanner.exitTime ?? (activePlanner.entryTime + (activePlanner.durationBars || 15) * 900);
        entries.push({
          type: activePlanner.type === "long" ? "BUY" : "SELL",
          entry_price: activePlanner.entryPrice,
          sl: activePlanner.slPrice,
          tp: activePlanner.tpPrice,
          profit: 0,
          entry_time_ts: activePlanner.entryTime,
          exit_time_ts: exitTs,
          atr: null,
          atr_start_ts: null,
          atr_end_ts: null,
        });
      }

      const mergedEntries = [
        ...entries,
        ...llmPositions
          .filter(p => !p.is_rejected && (p.entry_time ?? 0) <= candle.time)
          .map(p => {
            const entryTs = p.entry_time ?? 0;
            const posInList = activePosList.find(pos => pos.ticket === p.ticket);
            return {
              type: p.type,
              entry_price: p.entry_price,
              sl: p.sl,
              tp: p.tp,
              profit: posInList?.pnl ?? 0,
              entry_time_ts: entryTs,
              exit_time_ts: posInList?.is_closed ? posInList.exit_time : null,
              atr: isAtrEnabled ? calculateATR(data.candles, entryTs, strategyParams.atr_period) : null,
              atr_start_ts: isAtrEnabled ? entryTs - strategyParams.atr_period * 900 : null,
              atr_end_ts: isAtrEnabled ? entryTs : null,
            };
          }),
      ];
      tradesPrimitiveRef.current.setTrades(mergedEntries);
      tradesPrimitiveRef.current.setLastCandleTime(candle.time);
      tradesPrimitiveRef.current.setTimeframe(activeTimeframe);
    }

    if (chartRef.current) {
      followReplayPlayhead(chartRef.current);
    }

    return idx + 1;
  }, [strategyParams, getFilteredTrades, llmPositions, useLLMSetup, activePlanner, activeTimeframe]);

  // ── Playback controls (continued) ──

  const startPlayback = useCallback(() => {
    if (!replayData || currentIndex >= replayData.candles.length) return;
    setIsPlaying(true);

    let idx = currentIndex;
    timerRef.current = setInterval(() => {
      if (idx >= replayData.candles.length) {
        clearInterval(timerRef.current!);
        timerRef.current = null;
        setIsPlaying(false);
        return;
      }
      idx = advanceCandle(idx, replayData);
      setCurrentIndex(idx);
    }, SPEED_MAP[speed]);
  }, [replayData, currentIndex, speed, advanceCandle]);

  const handleNext = useCallback(() => {
    if (!replayData || currentIndex >= replayData.candles.length) return;
    const next = advanceCandle(currentIndex, replayData);
    setCurrentIndex(next);
  }, [replayData, currentIndex, advanceCandle]);

  const handlePrev = useCallback(() => {
    if (!replayData || currentIndex <= 0) return;
    const prev = currentIndex - 1;
    setChartDataToIndex(prev, replayData);
    setCurrentIndex(prev);
  }, [replayData, currentIndex, setChartDataToIndex]);

  // Re-start timer when speed changes while playing
  useEffect(() => {
    if (isPlaying) {
      stopPlayback();
      // Brief delay so state settles
      setTimeout(() => startPlayback(), 50);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speed]);

  // Cleanup on unmount
  useEffect(() => () => stopPlayback(), [stopPlayback]);

  // ── Derived ──────────────────────────────────────────────────────────────

  const totalCandles = replayData?.candles.length ?? 0;
  const progress = totalCandles > 0 ? Math.round((currentIndex / totalCandles) * 100) : 0;
  const currentCandle = replayData?.candles[Math.max(0, currentIndex - 1)];
  const completedTrades = tradeStats.wins + tradeStats.losses;
  const winRate = completedTrades > 0 ? Math.round((tradeStats.wins / completedTrades) * 100) : 0;
  const initialBalance = strategyParams.initial_balance ?? INITIAL_BALANCE;
  const currentEquity = initialBalance + runningProfit;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div
      className="flex flex-col size-full text-[var(--text-primary)] transition-all duration-300 ease-in-out"
      style={{ background: "var(--bg-primary, #0f172a)", paddingLeft: "var(--sidebar-offset, 250px)", overflow: "hidden" }}
    >
      {/* ── Header ── */}
      <div
        className="relative z-30 flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 sm:py-4 border-b backdrop-blur-md bg-[rgba(15,23,42,0.45)]"
        style={{ borderColor: "rgba(var(--neon-blue-rgb), 0.15)", boxShadow: "0 4px 30px rgba(0,0,0,0.2)" }}
      >
        <div className="flex items-center gap-3 sm:gap-4 shrink-0">
          <div className="flex items-center justify-center w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-white/[0.03] border border-white/[0.08] backdrop-blur-md text-xl sm:text-2xl hover:scale-105 transition-transform duration-200 ease-out shadow-[0_0_15px_rgba(var(--neon-cyan-rgb),0.15)] select-none">
            🎬
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-[var(--text-primary)] leading-none mb-1">
              Replay Trades
            </h1>
            <p className="text-[var(--text-tertiary)] text-[11px] sm:text-xs">
              Replay historical trades and evaluate strategy performance
            </p>
          </div>
        </div>

        {/* Filter controls + Playback Controls */}
        <div className="flex items-center gap-2 flex-wrap justify-start sm:justify-end min-w-0">
          {/* If replayData is loaded, render playback controls FIRST! */}
          {replayData && (
            <>
              {/* Playback Control Deck */}
              <div className="inline-flex items-center gap-1.5 p-1 bg-[rgba(15,23,42,0.55)] border border-slate-800/80 rounded-xl shadow-[inset_0_1.5px_3px_rgba(0,0,0,0.8)]">
                {/* Rewind */}
                <button
                  onClick={handlePrev}
                  disabled={isPlaying || currentIndex <= 0}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg font-semibold text-xs transition-all duration-150 active:scale-95 disabled:opacity-30 cursor-pointer text-purple-400 hover:text-purple-300 hover:bg-purple-500/10 disabled:hover:bg-transparent"
                >
                  <Rewind size={12} />
                  <span>Rewind</span>
                </button>

                {/* Play / Pause */}
                <button
                  onClick={isPlaying ? stopPlayback : startPlayback}
                  disabled={currentIndex >= totalCandles}
                  className={cn(
                    "flex items-center gap-1 px-3 py-1 rounded-lg font-bold text-xs transition-all duration-150 active:scale-95 disabled:opacity-30 cursor-pointer shadow-sm border",
                    isPlaying
                      ? "bg-red-500/10 hover:bg-red-500/20 text-red-400 border-red-500/20 shadow-[0_0_10px_rgba(239,68,68,0.15)]"
                      : "bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border-cyan-500/20 shadow-[0_0_10px_rgba(34,211,238,0.15)]"
                  )}
                >
                  {isPlaying ? <Pause size={12} /> : <Play size={12} />}
                  <span>{isPlaying ? "Pause" : "Play"}</span>
                </button>

                {/* Next */}
                <button
                  onClick={handleNext}
                  disabled={isPlaying || currentIndex >= totalCandles}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg font-semibold text-xs transition-all duration-150 active:scale-95 disabled:opacity-30 cursor-pointer text-purple-400 hover:text-purple-300 hover:bg-purple-500/10 disabled:hover:bg-transparent"
                >
                  <SkipForward size={12} />
                  <span>Next</span>
                </button>

                {/* Stop */}
                <button
                  onClick={handleStop}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg font-semibold text-xs transition-all duration-150 active:scale-95 cursor-pointer text-red-400 hover:text-red-300 hover:bg-red-500/10"
                >
                  <Square size={12} />
                  <span>Stop</span>
                </button>
              </div>

              {/* Speed */}
              <div className="flex items-center gap-1.5 ml-1">
                <span className="text-xs text-[var(--text-secondary,#94a3b8)]">Speed:</span>
                <div className="inline-flex items-center gap-1.5 p-1 bg-[rgba(15,23,42,0.55)] border border-slate-800/80 rounded-xl shadow-[inset_0_1.5px_3px_rgba(0,0,0,0.8)]">
                  {(["1x", "2x", "3x", "5x", "10x"] as const).map((s) => (
                    <button
                      key={s}
                      onClick={() => setSpeed(s)}
                      className={cn(
                        "px-2.5 py-1 rounded-lg text-xs font-semibold transition-all duration-150 active:scale-95 cursor-pointer",
                        speed === s
                          ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-[0_0_10px_rgba(34,211,238,0.15)]"
                          : "text-slate-400 hover:text-white hover:bg-white/5"
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              {/* Progress Bar */}
              <div className="flex items-center gap-2 w-32 ml-1">
                <div className="flex-1 h-1.5 rounded-full bg-[rgba(100,116,139,0.15)] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-purple-500 transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <span className="text-xs font-mono tabular-nums text-[var(--text-secondary,#94a3b8)] min-w-[28px] text-right">
                  {progress}%
                </span>
              </div>

              {/* Vertical separator */}
              <div className="w-[1px] h-6 bg-slate-800/60 self-center" />
            </>
          )}

          <div className="flex items-center gap-2 flex-wrap">
            {/* Timeframe selector (tiru 100% dari page trades) */}
            <div className="flex items-center gap-1.5 sm:gap-2 mr-1 sm:mr-2">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-secondary,#94a3b8)]">Timeframe</span>
              <div className="inline-flex items-center gap-1.5 p-1 bg-[rgba(15,23,42,0.55)] border border-slate-800/80 rounded-xl shadow-[inset_0_1.5px_3px_rgba(0,0,0,0.8)]">
                {["M15", "H1", "H4"].map((tf) => (
                  <button
                    key={tf}
                    disabled={isLoading}
                    onClick={() => handleTimeframeChange(tf)}
                    className={cn(
                      "px-2.5 py-1 rounded-lg text-xs font-semibold transition-all duration-150 active:scale-95 cursor-pointer disabled:opacity-40",
                      tf === activeTimeframe
                        ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-[0_0_10px_rgba(34,211,238,0.15)]"
                        : "text-slate-400 hover:text-white hover:bg-white/5"
                    )}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>

            <Calendar size={16} className="text-[var(--neon-blue,#38bdf8)] animate-pulse hidden sm:inline-block" />

            {/* From */}
            <CustomSelect
              value={yearFrom}
              onChange={setYearFrom}
              options={availableYearsFrom}
              getLabel={(val) => String(val)}
              accent="blue"
            />
            <CustomSelect
              value={monthFrom}
              onChange={setMonthFrom}
              options={availableMonthsFrom}
              getLabel={(val) => MONTHS[val - 1]}
              accent="purple"
              className="w-28 sm:w-32"
            />

            <span className="text-[var(--text-secondary,#94a3b8)] text-sm font-semibold">→</span>

            {/* To */}
            <CustomSelect
              value={yearTo}
              onChange={setYearTo}
              options={availableYearsTo}
              getLabel={(val) => String(val)}
              accent="blue"
            />
            <CustomSelect
              value={monthTo}
              onChange={setMonthTo}
              options={availableMonthsTo}
              getLabel={(val) => MONTHS[val - 1]}
              accent="purple"
              className="w-28 sm:w-32"
            />

            <button
              onClick={handleLoad}
              disabled={isLoading}
              className="inline-flex items-center justify-center px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer border transition-all duration-200 outline-none hover:bg-[rgba(255,255,255,0.08)] hover:border-[rgba(255,255,255,0.25)] hover:text-white"
              style={
                replayData
                  ? {
                    backgroundColor: "rgba(6, 182, 212, 0.18)",
                    borderColor: "var(--neon-cyan, #06b6d4)",
                    color: "#67e8f9",
                    boxShadow: "0 0 12px rgba(6, 182, 212, 0.25)",
                  }
                  : {
                    backgroundColor: "rgba(255, 255, 255, 0.04)",
                    borderColor: "rgba(255, 255, 255, 0.15)",
                    color: "rgba(255, 255, 255, 0.8)",
                  }
              }
            >
              Load
            </button>
          </div>
        </div>
      </div>

      {/* ── Scrollable Body ── */}
      <div className="flex-1 overflow-y-auto elegant-scrollbar px-6 py-4 flex flex-col gap-6">
        {/* ── Stats Bar ── */}
        <div
          aria-live="polite"
          className="relative flex min-h-[72px] flex-wrap overflow-hidden rounded-lg border border-slate-700/70 bg-[rgba(8,15,29,0.82)] shadow-[0_14px_32px_rgba(0,0,0,0.18)]"
        >
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/50 via-slate-500/30 to-transparent" />
            <div className="flex min-w-[210px] flex-1 items-center gap-3 border-b border-slate-700/50 px-4 py-3 lg:border-b-0 lg:border-r">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-cyan-400/20 bg-cyan-400/10 text-cyan-300">
                <CalendarDays size={15} />
              </div>
              <div className="min-w-0">
                <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Replay Range</div>
                <div className="mt-0.5 truncate font-mono text-[11px] text-slate-200">
                  {replayData ? <>{replayData.meta.date_from} <span className="text-slate-600">to</span> {replayData.meta.date_to}</> : <span className="text-slate-500">Awaiting dataset</span>}
                </div>
              </div>
            </div>
            <div className="flex min-w-[170px] flex-1 items-center gap-3 border-b border-slate-700/50 px-4 py-3 lg:border-b-0 lg:border-r">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-blue-400/20 bg-blue-400/10 text-blue-300">
                <ChartNoAxesCombined size={15} />
              </div>
              <div className="min-w-0">
                <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Playback</div>
                <div className="mt-0.5 flex items-baseline gap-1.5 font-mono tabular-nums">
                  <span className="text-base font-bold text-slate-100">{currentIndex.toLocaleString()}</span>
                  <span className="text-[11px] text-slate-500">/ {totalCandles.toLocaleString()}</span>
                  <span className="text-[10px] text-cyan-300">{progress}%</span>
                </div>
              </div>
            </div>
            <div className="flex min-w-[135px] flex-1 items-center px-4 py-3 border-b border-slate-700/50 lg:border-b-0 lg:border-r">
              <div className="min-w-0 font-mono tabular-nums">
                <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Net PnL</div>
                <div className={`mt-0.5 text-base font-bold ${currentEquity >= initialBalance ? "text-emerald-300" : "text-rose-300"}`}>${currentEquity.toFixed(2)}</div>
              </div>
            </div>
            <div className="flex min-w-[175px] flex-1 items-center gap-3 border-b border-slate-700/50 px-4 py-3 lg:border-b-0 lg:border-r">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-amber-400/20 bg-amber-400/10 text-amber-300">
                <Trophy size={15} />
              </div>
              <div className="min-w-0">
                <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Trade Results</div>
                <div className="mt-0.5 flex items-baseline gap-2 font-mono">
                  <span className="text-base font-bold text-slate-100">{tradeStats.total}</span>
                  <span className="text-[10px] text-slate-500">trades</span>
                  <span className="text-[10px] text-emerald-300">{winRate}% win</span>
                </div>
              </div>
            </div>
            <div className="flex min-w-[150px] flex-1 items-center gap-3 px-4 py-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-slate-600/50 bg-slate-800/60 text-slate-300">
                <TrendingDown size={15} />
              </div>
              <div className="min-w-0">
                <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Outcome</div>
                <div className="mt-0.5 flex items-baseline gap-2 font-mono text-[11px]">
                  <span className="text-emerald-300"><span className="text-slate-500">W</span> {tradeStats.wins}</span>
                  <span className="text-rose-300"><span className="text-slate-500">L</span> {tradeStats.losses}</span>
                </div>
              </div>
            </div>
            <div className="flex w-full items-center justify-between gap-4 border-t border-slate-700/50 bg-slate-950/25 px-4 py-3 font-mono">
              <div className="min-w-0">
                <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Modal Awal</div>
                <div className="mt-0.5 text-base font-bold text-slate-200">${initialBalance.toFixed(2)}</div>
              </div>
              <div className="flex min-w-0 items-center gap-3 text-right">
                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border ${runningProfit >= 0 ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300" : "border-rose-400/20 bg-rose-400/10 text-rose-300"}`}>
                  <CircleDollarSign size={15} />
                </div>
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Account Value</div>
                  <div className={`mt-0.5 text-base font-bold ${currentEquity >= initialBalance ? "text-emerald-300" : "text-rose-300"}`}>${currentEquity.toFixed(2)}</div>
                </div>
              </div>
            </div>
            {currentCandle && (
              <div className="flex w-full items-center justify-end border-t border-slate-700/50 bg-slate-950/25 px-4 py-1.5 font-mono text-[10px] text-slate-500">
                {new Date(currentCandle.time * 1000).toISOString().slice(0, 16).replace("T", " ")} UTC
              </div>
            )}
        </div>

        {/* ── Error ── */}
        {loadError && (
          <div className="px-4 py-3 rounded bg-red-900/30 border border-red-500/30 text-red-400 text-sm">
            {loadError}
          </div>
        )}

        {/* ── Empty state ── */}
        {!replayData && !loadError && (
          <div
            className="flex items-center justify-center flex-col gap-3 text-[var(--text-secondary,#94a3b8)] flex-shrink-0"
            style={{ height: "790px" }}
          >
            <span className="text-5xl">🎬</span>
            <p className="text-sm">Pilih rentang tanggal dan klik <strong>Load</strong> untuk memulai replay.</p>
          </div>
        )}

        {/* ── Chart ── */}
        <div className="relative px-4 pt-3 pb-0 flex-shrink-0" style={{ height: "790px", display: replayData ? "block" : "none" }}>
          {/* Floating Tooltip/Legend */}
          {hoveredInfo && (
            <div className="absolute top-6 left-8 z-10 bg-slate-900/95 border border-slate-800/80 rounded px-3 py-1.5 text-[10px] font-mono flex items-center gap-3 text-slate-300 backdrop-blur-md pointer-events-none shadow-xl">
              {hoveredInfo.time && (
                <span className="text-slate-400 mr-1">{hoveredInfo.time}</span>
              )}
              {hoveredInfo.open !== null && (
                <span className="flex items-center gap-0.5">
                  <span className="text-slate-500">O</span>
                  <span className={hoveredInfo.close! >= hoveredInfo.open! ? "text-green-400" : "text-red-400"}>
                    {hoveredInfo.open.toFixed(2)}
              </span>
                </span>
              )}
              {hoveredInfo.high !== null && (
                <span className="flex items-center gap-0.5">
                  <span className="text-slate-500">H</span>
                  <span className="text-slate-200">{hoveredInfo.high.toFixed(2)}</span>
                </span>
              )}
              {hoveredInfo.low !== null && (
                <span className="flex items-center gap-0.5">
                  <span className="text-slate-500">L</span>
                  <span className="text-slate-200">{hoveredInfo.low.toFixed(2)}</span>
                </span>
              )}
              {hoveredInfo.close !== null && (
                <span className="flex items-center gap-0.5">
                  <span className="text-slate-500">C</span>
                  <span className={hoveredInfo.close! >= hoveredInfo.open! ? "text-green-400" : "text-red-400"}>
                    {hoveredInfo.close.toFixed(2)}
                  </span>
                </span>
              )}
              {hoveredInfo.hoveredPrice !== null && (
                <span className="border-l border-slate-800 pl-3 flex items-center gap-1">
                  <span className="text-cyan-400">PRICE</span>
                  <span className="text-cyan-300 font-bold">{hoveredInfo.hoveredPrice.toFixed(2)}</span>
                </span>
              )}
            </div>
          )}

          {/* ── TradingView-style Ultra Premium Draggable Long/Short Toolbar ── */}
          <div
            style={{ left: toolbarPos.x, top: toolbarPos.y }}
            className="absolute z-20 flex items-center gap-1.5 rounded-xl border border-slate-700/80 bg-slate-950/85 px-2 py-1.5 backdrop-blur-2xl shadow-[0_12px_40px_rgba(0,0,0,0.7)] select-none transition-shadow hover:shadow-[0_16px_50px_rgba(0,0,0,0.85)] border-slate-700/60 hover:border-cyan-500/40 animate-in fade-in"
          >
            {/* Drag Grip Handle */}
            <div
              onMouseDown={handleToolbarMouseDown}
              title="Klik & tahan untuk memindahkan toolbar"
              className="flex items-center justify-center p-1 text-slate-500 hover:text-cyan-400 cursor-grab active:cursor-grabbing rounded hover:bg-slate-800/60 transition-colors"
            >
              <GripVertical size={14} />
            </div>

            {/* Long Tool Button */}
            <button
              type="button"
              id="btn-long-tool"
              onClick={() => {
                setPlannerTool((prev) => (prev === "long" ? "none" : "long"));
              }}
              title="Long Position Tool (Klik pada chart untuk meletakkan posisi Buy)"
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold transition-all cursor-pointer",
                plannerTool === "long"
                  ? "bg-emerald-500 text-slate-950 shadow-[0_0_16px_rgba(16,185,129,0.5)] border border-emerald-400"
                  : "text-emerald-400 hover:bg-emerald-500/15 border border-emerald-500/25 bg-emerald-500/5 hover:border-emerald-500/40"
              )}
            >
              <TrendingUp size={14} className={plannerTool === "long" ? "text-slate-950 stroke-[2.5]" : "text-emerald-400"} />
              <span>Long</span>
            </button>

            {/* Short Tool Button */}
            <button
              type="button"
              id="btn-short-tool"
              onClick={() => {
                setPlannerTool((prev) => (prev === "short" ? "none" : "short"));
              }}
              title="Short Position Tool (Klik pada chart untuk meletakkan posisi Sell)"
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold transition-all cursor-pointer",
                plannerTool === "short"
                  ? "bg-rose-500 text-slate-950 shadow-[0_0_16px_rgba(244,63,94,0.5)] border border-rose-400"
                  : "text-rose-400 hover:bg-rose-500/15 border border-rose-500/25 bg-rose-500/5 hover:border-rose-500/40"
              )}
            >
              <TrendingDown size={14} className={plannerTool === "short" ? "text-slate-950 stroke-[2.5]" : "text-rose-400"} />
              <span>Short</span>
            </button>

            {/* Divider */}
            <div className="h-4 w-px bg-slate-700/60" />

            {/* Target RR Selector */}
            <div className="flex items-center gap-1 text-[11px] font-mono text-slate-300">
              <span className="text-[10px] text-slate-500 uppercase font-semibold">RR</span>
              {[1.0, 1.5, 2.0, 3.0].map((ratio) => (
                <button
                  key={ratio}
                  type="button"
                  onClick={() => {
                    setSelectedRrRatio(ratio);
                    if (activePlanner) {
                      const slDist = Math.abs(activePlanner.entryPrice - activePlanner.slPrice);
                      const newTpPrice =
                        activePlanner.type === "long"
                          ? activePlanner.entryPrice + slDist * ratio
                          : activePlanner.entryPrice - slDist * ratio;
                      setActivePlanner((prev) =>
                        prev ? { ...prev, riskRewardRatio: ratio, tpPrice: newTpPrice } : null
                      );
                    }
                  }}
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[10px] font-bold transition-all cursor-pointer",
                    selectedRrRatio === ratio
                      ? "bg-cyan-400 text-slate-950 shadow-[0_0_10px_rgba(6,182,212,0.4)]"
                      : "text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-transparent hover:border-slate-700"
                  )}
                >
                  1:{ratio}
                </button>
              ))}
            </div>

            {/* Clear Button */}
            {(activePlanner || plannerTool !== "none") && (
              <>
                <div className="h-4 w-px bg-slate-700/60" />
                <button
                  type="button"
                  id="btn-clear-planner"
                  onClick={() => {
                    setActivePlanner(null);
                    setPlannerTool("none");
                  }}
                  title="Hapus Position Tool"
                  className="flex items-center justify-center rounded-lg p-1.5 text-slate-400 hover:bg-rose-500/20 hover:text-rose-300 transition-all cursor-pointer hover:border hover:border-rose-500/30"
                >
                  <X size={14} />
                </button>
              </>
            )}
          </div>

          {/* ── Position Planner Adaptive & Customizable Control HUD Card ── */}
          {activePlanner && (
            <div
              style={{ left: hudCardPos.x, top: hudCardPos.y }}
              className="absolute z-20 w-[380px] rounded-2xl border border-slate-700/80 bg-gradient-to-b from-slate-900/95 via-slate-950/90 to-slate-900/95 p-4 backdrop-blur-2xl shadow-[0_20px_60px_rgba(0,0,0,0.8),inset_0_1px_1px_rgba(255,255,255,0.1)] font-mono text-xs text-slate-200 select-none hover:border-cyan-500/40 transition-all"
            >
              {/* Header: Grip Handle, Type Toggle, Snap Structure, Minimize, Close */}
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-2.5">
                <div className="flex items-center gap-2">
                  <div
                    onMouseDown={handleHudMouseDown}
                    title="Klik & tahan untuk memindahkan kartu"
                    className="flex items-center justify-center p-1 text-slate-500 hover:text-cyan-400 cursor-grab active:cursor-grabbing rounded hover:bg-slate-800/60 transition-colors"
                  >
                    <GripVertical size={14} />
                  </div>

                  <button
                    type="button"
                    onClick={togglePlannerType}
                    title="Klik untuk ubah arah Long ↔ Short"
                    className={cn(
                      "flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-bold uppercase transition-all cursor-pointer",
                      activePlanner.type === "long"
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30 shadow-[0_0_12px_rgba(16,185,129,0.15)]"
                        : "bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30 shadow-[0_0_12px_rgba(244,63,94,0.15)]"
                    )}
                  >
                    {activePlanner.type === "long" ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                    <span>{activePlanner.type === "long" ? "Long" : "Short"}</span>
                    <span className="text-[9px] opacity-60">⇄</span>
                  </button>

                  <button
                    type="button"
                    onClick={snapPlannerStructure}
                    title="Snap SL otomatis ke Swing High (Short) / Swing Low (Long)"
                    className="flex items-center gap-1 rounded-lg border border-fuchsia-500/30 bg-fuchsia-500/10 px-2 py-1 text-[10px] font-bold text-fuchsia-300 hover:bg-fuchsia-500/20 hover:border-fuchsia-500/50 transition-all cursor-pointer shadow-[0_0_10px_rgba(217,70,239,0.15)]"
                  >
                    <Target size={12} />
                    <span>Snap HH/LL</span>
                  </button>
                </div>

                <div className="flex items-center gap-1.5">
                  <span className="rounded bg-cyan-500/10 px-2 py-0.5 text-[10px] font-bold text-cyan-300 border border-cyan-500/25">
                    RR 1:{activePlanner.riskRewardRatio}
                  </span>
                  <button
                    type="button"
                    onClick={() => setIsHudMinimized((prev) => !prev)}
                    className="text-slate-400 hover:text-cyan-300 cursor-pointer p-1 rounded hover:bg-slate-800 transition-colors"
                    title={isHudMinimized ? "Perbesar Panel" : "Perkecil Panel"}
                  >
                    {isHudMinimized ? <Maximize2 size={13} /> : <Minimize2 size={13} />}
                  </button>
                  <button
                    type="button"
                    onClick={() => setActivePlanner(null)}
                    className="text-slate-400 hover:text-rose-400 cursor-pointer p-1 rounded hover:bg-rose-500/20 transition-colors"
                    title="Tutup Planner"
                  >
                    <X size={13} />
                  </button>
                </div>
              </div>

              {isHudMinimized ? (
                <div className="mt-2 flex items-center justify-between text-[11px] font-bold">
                  <span className="text-emerald-400">TP: {activePlanner.tpPrice.toFixed(2)}</span>
                  <span className="text-rose-400">SL: {activePlanner.slPrice.toFixed(2)}</span>
                  <span className="text-cyan-300">
                    +$
                    {(
                      Math.abs(activePlanner.tpPrice - activePlanner.entryPrice) *
                      (activePlanner.lotSize || 0.05) *
                      100
                    ).toFixed(2)}
                  </span>
                </div>
              ) : (
                <>

              {/* Entry Price Row */}
              <div className="mt-3 flex items-center justify-between gap-3 bg-slate-950/60 rounded-lg p-2 border border-slate-800/80">
                <span className="text-[10px] font-semibold text-slate-400 uppercase">Entry Price</span>
                <div className="flex items-center gap-1.5">
                  <input
                    type="text"
                    inputMode="decimal"
                    data-planner-input="entry"
                    aria-label="Entry Price"
                    value={plannerEntryInput}
                    onChange={(e) => {
                      setPlannerEntryInput(e.target.value);
                      const val = parseFloat(e.target.value.replace(",", "."));
                      if (!isNaN(val) && val > 0) updatePlannerEntry(val);
                    }}
                    onBlur={() => {
                      if (!plannerEntryInput || isNaN(parseFloat(plannerEntryInput.replace(",", ".")))) {
                        setPlannerEntryInput(activePlanner.entryPrice.toFixed(2));
                      } else {
                        const val = parseFloat(plannerEntryInput.replace(",", "."));
                        setPlannerEntryInput(val.toFixed(2));
                        updatePlannerEntry(val);
                      }
                    }}
                    className="h-6 w-24 rounded border border-slate-700 bg-slate-900 px-1.5 text-right font-mono text-xs font-bold text-slate-100 outline-none focus:border-cyan-500"
                  />
                  {currentCandle && (
                    <button
                      type="button"
                      onClick={() => updatePlannerEntry(currentCandle.close)}
                      title="Set Entry ke harga candle replay saat ini"
                      className="rounded border border-slate-700 bg-slate-800 px-1.5 py-0.5 text-[9px] font-bold text-cyan-400 hover:bg-slate-700 cursor-pointer"
                    >
                      📍 Candle
                    </button>
                  )}
                </div>
              </div>

              {/* Target (TP) Section */}
              <div className="mt-2.5 rounded-lg bg-emerald-950/20 border border-emerald-500/25 p-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-emerald-400">Target (Take Profit)</span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => adjustPlannerTPDistance(-10)}
                      title="Kurangi TP $10"
                      className="rounded bg-emerald-900/40 border border-emerald-500/30 px-1.5 py-0.5 text-[9px] font-bold text-emerald-300 hover:bg-emerald-800/50 cursor-pointer"
                    >
                      -$10
                    </button>
                    <button
                      type="button"
                      onClick={() => adjustPlannerTPDistance(10)}
                      title="Tambah TP $10"
                      className="rounded bg-emerald-900/40 border border-emerald-500/30 px-1.5 py-0.5 text-[9px] font-bold text-emerald-300 hover:bg-emerald-800/50 cursor-pointer"
                    >
                      +$10
                    </button>
                  </div>
                </div>

                <div className="mt-1.5 flex items-center justify-between gap-2">
                  <div>
                    <input
                      type="text"
                      inputMode="decimal"
                      data-planner-input="tp"
                      aria-label="TP Price"
                      value={plannerTpInput}
                      onChange={(e) => {
                        setPlannerTpInput(e.target.value);
                        const val = parseFloat(e.target.value.replace(",", "."));
                        if (!isNaN(val) && val > 0) updatePlannerTPPrice(val);
                      }}
                      onBlur={() => {
                        if (!plannerTpInput || isNaN(parseFloat(plannerTpInput.replace(",", ".")))) {
                          setPlannerTpInput(activePlanner.tpPrice.toFixed(2));
                        } else {
                          const val = parseFloat(plannerTpInput.replace(",", "."));
                          setPlannerTpInput(val.toFixed(2));
                          updatePlannerTPPrice(val);
                        }
                      }}
                      className="h-6 w-24 rounded border border-emerald-500/40 bg-slate-900 px-1.5 text-left font-mono text-xs font-bold text-emerald-300 outline-none focus:border-emerald-400"
                    />
                  </div>
                  <div className="text-right text-[10px] text-emerald-400/90 font-medium">
                    +{(Math.abs(activePlanner.tpPrice - activePlanner.entryPrice) * 10).toFixed(1)} Pips (
                    +{(Math.abs(activePlanner.tpPrice - activePlanner.entryPrice) * 100).toFixed(0)} pts)
                  </div>
                </div>

                {/* RR Quick Pills */}
                <div className="mt-2 flex items-center gap-1">
                  <span className="text-[9px] text-slate-500 font-semibold mr-1">R:R</span>
                  {[1.0, 1.5, 2.0, 2.5, 3.0, 4.0].map((ratio) => (
                    <button
                      key={ratio}
                      type="button"
                      onClick={() => {
                        const slDist = Math.abs(activePlanner.entryPrice - activePlanner.slPrice);
                        const newTP =
                          activePlanner.type === "long"
                            ? activePlanner.entryPrice + slDist * ratio
                            : activePlanner.entryPrice - slDist * ratio;
                        setActivePlanner((prev) =>
                          prev ? { ...prev, riskRewardRatio: ratio, tpPrice: newTP } : null
                        );
                      }}
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[9px] font-bold transition-all cursor-pointer",
                        Math.abs(activePlanner.riskRewardRatio - ratio) < 0.05
                          ? "bg-emerald-400 text-slate-950 shadow-sm"
                          : "bg-slate-900/80 text-slate-400 hover:bg-emerald-500/20 hover:text-emerald-300"
                      )}
                    >
                      1:{ratio}
                    </button>
                  ))}
                </div>

                <div className="mt-1.5 text-[10px] font-bold text-emerald-300">
                  Est. Profit: +$
                  {(
                    Math.abs(activePlanner.tpPrice - activePlanner.entryPrice) *
                    (activePlanner.lotSize || 0.05) *
                    100
                  ).toFixed(2)}{" "}
                  <span className="text-emerald-500/70 font-normal">
                    (+
                    {(
                      ((Math.abs(activePlanner.tpPrice - activePlanner.entryPrice) *
                        (activePlanner.lotSize || 0.05) *
                        100) /
                        (strategyParams.initial_balance || 1000)) *
                      100
                    ).toFixed(1)}
                    % modal)
                  </span>
                </div>
              </div>

              {/* Stop Loss (SL) Section */}
              <div className="mt-2.5 rounded-lg bg-rose-950/20 border border-rose-500/25 p-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-rose-400">Stop Loss (SL)</span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => adjustPlannerSLDistance(-5)}
                      title="Rapatkan SL $5"
                      className="rounded bg-rose-900/40 border border-rose-500/30 px-1.5 py-0.5 text-[9px] font-bold text-rose-300 hover:bg-rose-800/50 cursor-pointer"
                    >
                      -$5
                    </button>
                    <button
                      type="button"
                      onClick={() => adjustPlannerSLDistance(5)}
                      title="Lebarkan SL $5"
                      className="rounded bg-rose-900/40 border border-rose-500/30 px-1.5 py-0.5 text-[9px] font-bold text-rose-300 hover:bg-rose-800/50 cursor-pointer"
                    >
                      +$5
                    </button>
                    <button
                      type="button"
                      onClick={() => adjustPlannerSLDistance(10)}
                      title="Lebarkan SL $10"
                      className="rounded bg-rose-900/40 border border-rose-500/30 px-1.5 py-0.5 text-[9px] font-bold text-rose-300 hover:bg-rose-800/50 cursor-pointer"
                    >
                      +$10
                    </button>
                  </div>
                </div>

                <div className="mt-1.5 flex items-center justify-between gap-2">
                  <div>
                    <input
                      type="text"
                      inputMode="decimal"
                      data-planner-input="sl"
                      aria-label="SL Price"
                      value={plannerSlInput}
                      onChange={(e) => {
                        setPlannerSlInput(e.target.value);
                        const val = parseFloat(e.target.value.replace(",", "."));
                        if (!isNaN(val) && val > 0) updatePlannerSLPrice(val);
                      }}
                      onBlur={() => {
                        if (!plannerSlInput || isNaN(parseFloat(plannerSlInput.replace(",", ".")))) {
                          setPlannerSlInput(activePlanner.slPrice.toFixed(2));
                        } else {
                          const val = parseFloat(plannerSlInput.replace(",", "."));
                          setPlannerSlInput(val.toFixed(2));
                          updatePlannerSLPrice(val);
                        }
                      }}
                      className="h-6 w-24 rounded border border-rose-500/40 bg-slate-900 px-1.5 text-left font-mono text-xs font-bold text-rose-300 outline-none focus:border-rose-400"
                    />
                  </div>
                  <div className="text-right text-[10px] text-rose-400/90 font-medium">
                    -{(Math.abs(activePlanner.entryPrice - activePlanner.slPrice) * 10).toFixed(1)} Pips (
                    -{(Math.abs(activePlanner.entryPrice - activePlanner.slPrice) * 100).toFixed(0)} pts)
                  </div>
                </div>

                <div className="mt-1.5 text-[10px] font-bold text-rose-300">
                  Risk Loss: -$
                  {(
                    Math.abs(activePlanner.entryPrice - activePlanner.slPrice) *
                    (activePlanner.lotSize || 0.05) *
                    100
                  ).toFixed(2)}{" "}
                  <span className="text-rose-500/70 font-normal">
                    (-
                    {(
                      ((Math.abs(activePlanner.entryPrice - activePlanner.slPrice) *
                        (activePlanner.lotSize || 0.05) *
                        100) /
                        (strategyParams.initial_balance || 1000)) *
                      100
                    ).toFixed(1)}
                    % modal)
                  </span>
                </div>
              </div>

              {/* Lot & Risk Management Footer */}
              <div className="mt-3 border-t border-slate-800/80 pt-2.5">
                <div className="flex items-center justify-between text-[10px]">
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400 font-semibold">Mode:</span>
                    <button
                      type="button"
                      onClick={() => setActivePlanner((prev) => (prev ? { ...prev, isAutoRisk: false } : null))}
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[9px] font-bold transition-all cursor-pointer",
                        !activePlanner.isAutoRisk
                          ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                          : "text-slate-500 hover:text-slate-300"
                      )}
                    >
                      Fixed Lot
                    </button>
                    <button
                      type="button"
                      onClick={() => updatePlannerRiskAmount(activePlanner.riskAmountUsd || 100)}
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[9px] font-bold transition-all cursor-pointer",
                        activePlanner.isAutoRisk
                          ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                          : "text-slate-500 hover:text-slate-300"
                      )}
                    >
                      Auto Risk ($)
                    </button>
                  </div>

                  {!activePlanner.isAutoRisk ? (
                    <div className="flex items-center gap-1">
                      <span className="text-slate-400">Lot:</span>
                      <input
                        type="text"
                        inputMode="decimal"
                        data-planner-input="lot"
                        aria-label="Planner Lot Size"
                        value={plannerLotInput}
                        onChange={(e) => {
                          setPlannerLotInput(e.target.value);
                          const val = parseFloat(e.target.value.replace(",", "."));
                          if (!isNaN(val) && val > 0) updatePlannerLot(val);
                        }}
                        onBlur={() => {
                          if (!plannerLotInput || isNaN(parseFloat(plannerLotInput.replace(",", ".")))) {
                            setPlannerLotInput(activePlanner.lotSize.toFixed(2));
                          } else {
                            const val = parseFloat(plannerLotInput.replace(",", "."));
                            setPlannerLotInput(val.toFixed(2));
                            updatePlannerLot(val);
                          }
                        }}
                        className="h-5 w-14 rounded border border-slate-700 bg-slate-950 px-1 text-center font-mono text-[10px] font-bold text-cyan-300 outline-none focus:border-cyan-500"
                      />
                    </div>
                  ) : (
                    <div className="flex items-center gap-1">
                      <span className="text-slate-400">Risk $:</span>
                      <input
                        type="text"
                        inputMode="numeric"
                        data-planner-input="risk"
                        aria-label="Planner Risk USD"
                        value={plannerRiskInput}
                        onChange={(e) => {
                          setPlannerRiskInput(e.target.value);
                          const val = Number(e.target.value.replace(/\D/g, ""));
                          if (Number.isFinite(val) && val > 0) updatePlannerRiskAmount(val);
                        }}
                        onBlur={() => {
                          if (!plannerRiskInput || isNaN(Number(plannerRiskInput.replace(/\D/g, "")))) {
                            setPlannerRiskInput(String(activePlanner.riskAmountUsd || 100));
                          } else {
                            const val = Math.max(1, Number(plannerRiskInput.replace(/\D/g, "")));
                            setPlannerRiskInput(String(val));
                            updatePlannerRiskAmount(val);
                          }
                        }}
                        className="h-5 w-14 rounded border border-cyan-500/50 bg-slate-950 px-1 text-center font-mono text-[10px] font-bold text-cyan-300 outline-none focus:border-cyan-400"
                      />
                      <span className="text-[9px] text-cyan-400 font-bold">({activePlanner.lotSize.toFixed(2)}L)</span>
                    </div>
                  )}
                </div>
              </div>
                </>
              )}
            </div>
          )}

          {/* Top Center Non-Obstructive Live HUD Indicator */}
          {(dragMode !== "none" || hoveredDragTarget !== "none") && activePlanner && (
            <div
              className="pointer-events-none absolute top-4 left-1/2 z-30 -translate-x-1/2 rounded-full bg-slate-900/95 px-4 py-1.5 font-mono text-xs font-bold shadow-[0_8px_30px_rgba(0,0,0,0.6)] border border-slate-700/90 backdrop-blur-md transition-all select-none animate-in fade-in zoom-in-95"
            >
              {dragMode === "tp" || hoveredDragTarget === "tp" ? (
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-emerald-400">
                    <span>🎯 Target TP:</span>
                    <span className="text-white font-bold">{activePlanner.tpPrice.toFixed(2)}</span>
                    <span className="text-emerald-400/80 font-normal text-[11px]">
                      (+{(Math.abs(activePlanner.tpPrice - activePlanner.entryPrice) * 10).toFixed(1)} pips)
                    </span>
                  </div>
                  <div className="h-3.5 w-px bg-slate-700" />
                  <div className="flex items-center gap-2 text-[11px]">
                    <span className="text-emerald-300">
                      Est. Profit: +$
                      {(
                        Math.abs(activePlanner.tpPrice - activePlanner.entryPrice) *
                        (activePlanner.lotSize || 0.05) *
                        100
                      ).toFixed(2)}
                    </span>
                    <span className="text-cyan-300">RR 1:{activePlanner.riskRewardRatio}</span>
                    <span className="text-slate-400">({activePlanner.lotSize.toFixed(2)} Lot)</span>
                  </div>
                </div>
              ) : dragMode === "sl" || hoveredDragTarget === "sl" ? (
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-rose-400">
                    <span>🛡️ Stop Loss:</span>
                    <span className="text-white font-bold">{activePlanner.slPrice.toFixed(2)}</span>
                    <span className="text-rose-400/80 font-normal text-[11px]">
                      (-{(Math.abs(activePlanner.entryPrice - activePlanner.slPrice) * 10).toFixed(1)} pips)
                    </span>
                  </div>
                  <div className="h-3.5 w-px bg-slate-700" />
                  <div className="flex items-center gap-2 text-[11px]">
                    <span className="text-rose-300">
                      Max Risk: -$
                      {(
                        Math.abs(activePlanner.entryPrice - activePlanner.slPrice) *
                        (activePlanner.lotSize || 0.05) *
                        100
                      ).toFixed(2)}
                    </span>
                    <span className="text-cyan-300">RR 1:{activePlanner.riskRewardRatio}</span>
                    <span className="text-slate-400">({activePlanner.lotSize.toFixed(2)} Lot)</span>
                  </div>
                </div>
              ) : dragMode === "width" || hoveredDragTarget === "width" ? (
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-violet-400">
                    <span>⏱️ Lebar Waktu:</span>
                    <span className="text-white font-bold">{activePlanner.durationBars || 15} Candle M15</span>
                  </div>
                  <div className="h-3.5 w-px bg-slate-700" />
                  <div className="text-[11px] text-slate-300 font-normal">
                    Durasi: {Math.floor(((activePlanner.durationBars || 15) * 15) / 60) > 0 ? `${Math.floor(((activePlanner.durationBars || 15) * 15) / 60)} Jam ` : ""}
                    {((activePlanner.durationBars || 15) * 15) % 60} Menit (Tarik ↔ untuk perlebar)
                  </div>
                </div>
              ) : dragMode === "move" || hoveredDragTarget === "move" ? (
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-cyan-400">
                    <span>✢ Pindah Posisi Bebas:</span>
                    <span className="text-white font-bold">${activePlanner.entryPrice.toFixed(2)}</span>
                  </div>
                  <div className="h-3.5 w-px bg-slate-700" />
                  <div className="text-[11px] text-slate-300 font-normal">
                    Tarik bebas ke Atas/Bawah (Harga) & Kiri/Kanan (Waktu Candle)
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 text-cyan-400">
                  <span className="text-xs">📍 Entry Level:</span>
                  <span className="text-white font-bold">{activePlanner.entryPrice.toFixed(2)}</span>
                </div>
              )}
            </div>
          )}

          <div
            ref={chartContainerRef}
            onMouseDown={handleChartMouseDown}
            onMouseMove={handleChartMouseMove}
            onMouseUp={handleChartMouseUp}
            onMouseLeave={handleChartMouseLeave}
            className={cn(
              "w-full h-full rounded-lg overflow-hidden transition-all",
              dragMode === "move" || hoveredDragTarget === "move"
                ? "cursor-move select-none"
                : dragMode === "width" || hoveredDragTarget === "width"
                ? "cursor-ew-resize select-none"
                : dragMode !== "none" || hoveredDragTarget !== "none"
                ? "cursor-ns-resize select-none"
                : plannerTool !== "none"
                ? "cursor-crosshair"
                : "cursor-default"
            )}
            style={{ background: "rgba(15,23,42,0.5)" }}
          />
        </div>



        {/* ── Active Positions Panel ── */}
        {replayData && (
          <div className="glass-card flex-shrink-0">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <span className="animate-pulse w-2.5 h-2.5 rounded-full bg-cyan-400 inline-block"></span>
              ⚡ Daftar Posisi
              {activePositions.length > 0 && (
                <span className="ml-auto text-xs font-normal text-slate-400">
                  <span className="text-cyan-400 font-semibold">{activePositions.filter(p => !p.is_closed && !p.is_rejected).length}</span> aktif
                  {" · "}
                  <span className="text-slate-400 font-semibold">{activePositions.filter(p => p.is_closed).length}</span> closed
                  {" · "}
                  <span className="text-rose-400 font-semibold">{activePositions.filter(p => p.is_rejected).length}</span> rejected
                </span>
              )}
            </h2>

            {/* ── LLM Trade Setup Recommendation Panel ── */}
            {(useLLMSetup || decisionEngine === "llm" || llmLoading || decisionLoading || llmRecommendation) && (
              <div className="mb-4 rounded-xl border border-purple-500/40 bg-gradient-to-br from-purple-950/40 via-slate-950/80 to-purple-900/15 p-4 shadow-lg backdrop-blur-md">
                <div className="flex items-center justify-between gap-3 border-b border-purple-500/20 pb-3">
                  <div className="flex items-center gap-2 text-sm font-bold text-purple-300">
                    <span className="text-base">🤖</span>
                    <span>LLM Trade Setup ({decisionEngine === "llm" ? "7-Step Reasoning" : "CHoCH & BOS"})</span>
                    {llmRecommendation?.cycle_stage && (
                      <span className={cn(
                        "font-bold px-2 py-0.5 rounded text-[10px]",
                        String(llmRecommendation.cycle_stage).includes("OVEREXTENDED")
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                          : String(llmRecommendation.cycle_stage).includes("MID_CYCLE")
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                          : String(llmRecommendation.cycle_stage).includes("REVERSAL") || String(llmRecommendation.cycle_stage).includes("CHOCH")
                          ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
                          : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                      )}>
                        {llmRecommendation.cycle_stage}
                      </span>
                    )}
                  </div>
                  {(llmLoading || decisionLoading) && (
                    <div className="flex items-center gap-2">
                      <span className="flex items-center gap-1.5 text-xs font-semibold text-purple-300 animate-pulse">
                        <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
                        <span>LLM Berpikir & Menganalisis...</span>
                      </span>
                      <button
                        type="button"
                        onClick={cancelLLMSetup}
                        className="rounded-md border border-rose-500/40 bg-rose-500/15 px-2.5 py-1 text-[11px] font-semibold text-rose-300 hover:bg-rose-500/25 transition-colors cursor-pointer"
                        title="Batalkan permintaan rekomendasi LLM"
                      >
                        Batal
                      </button>
                    </div>
                  )}
                </div>

                {!llmRecommendation && !llmLoading && !decisionLoading && (
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                    <span className="text-xs text-slate-400">
                      Otomatis menganalisis saat CHoCH/BOS terdeteksi, atau minta LLM menentukan Signal, SL, TP, & Lot sekarang.
                    </span>
                    <button
                      type="button"
                      onClick={() => (decisionEngine === "llm" ? requestDecisionSetup() : requestLLMSetup())}
                      className="rounded-md border border-purple-500/40 bg-purple-500/20 px-3.5 py-1.5 text-xs font-semibold text-purple-200 hover:bg-purple-500/30 transition-all cursor-pointer shadow-sm"
                    >
                      🧠 Analisis Sekarang (LLM)
                    </button>
                  </div>
                )}

                {llmRecommendation && (() => {
                  const sigUpper = (llmRecommendation.signal || "HOLD").toUpperCase();
                  const isTradeable = (sigUpper === "BUY" || sigUpper === "SELL") && (llmRecommendation.sl_price ?? llmRecommendation.sl ?? 0) > 0;
                  const isBlocked = sigUpper.includes("BLOCK");

                  return (
                    <div className="mt-3 space-y-3">
                      <div className="grid grid-cols-2 gap-2.5 text-xs sm:grid-cols-4">
                        <div className="rounded-lg bg-slate-950/90 border border-slate-800/80 p-2.5 shadow-sm">
                          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Signal</div>
                          <div className={`font-bold text-sm ${sigUpper === "BUY" ? "text-emerald-400" : sigUpper === "SELL" ? "text-rose-400" : isBlocked ? "text-amber-400" : "text-slate-400"}`}>
                            {sigUpper} ({Math.round((llmRecommendation.confidence ?? 0) * 100)}%)
                          </div>
                        </div>
                        <div className="rounded-lg bg-slate-950/90 border border-slate-800/80 p-2.5 shadow-sm">
                          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Risk %</div>
                          <div className="font-mono font-bold text-amber-400 text-sm">
                            {isTradeable && llmRecommendation.risk_pct ? `${Number(llmRecommendation.risk_pct).toFixed(1)}%` : "-"}
                          </div>
                        </div>
                        <div className="rounded-lg bg-slate-950/90 border border-slate-800/80 p-2.5 shadow-sm">
                          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">SL / TP</div>
                          <div className="font-mono text-xs font-semibold flex items-center gap-1">
                            {isTradeable ? (
                              <>
                                <span className="text-rose-400 font-bold">${llmRecommendation.sl_price?.toFixed(2)}</span>
                                <span className="text-slate-600">/</span>
                                <span className="text-emerald-400 font-bold">${llmRecommendation.tp_price?.toFixed(2)}</span>
                              </>
                            ) : (
                              <span className="text-slate-500 font-mono">- / -</span>
                            )}
                          </div>
                        </div>
                        <div className="rounded-lg bg-slate-950/90 border border-slate-800/80 p-2.5 shadow-sm">
                          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Lot Size</div>
                          <div className="font-mono font-bold text-cyan-300 text-sm">
                            {isTradeable ? `${Math.max(0.01, Number(llmRecommendation.lot_size || 0.01)).toFixed(2)} Lot` : "-"}
                          </div>
                        </div>
                      </div>

                      {(() => {
                        const reasoningRaw =
                          llmRecommendation.reasoning ||
                          (llmRecommendation as any).reason ||
                          (llmRecommendation as any).analysis ||
                          (llmRecommendation as any).explanation;
                        const reasoningStr =
                          typeof reasoningRaw === "string"
                            ? reasoningRaw
                            : Array.isArray(reasoningRaw)
                            ? reasoningRaw.join("\n")
                            : typeof reasoningRaw === "object" && reasoningRaw !== null
                            ? Object.entries(reasoningRaw)
                                .map(([k, v]) => `• ${k}: ${v}`)
                                .join("\n")
                            : null;

                        if (!reasoningStr) return null;

                        return (
                          <div className="rounded-lg border border-purple-500/30 bg-slate-950/95 p-3 text-xs leading-relaxed text-slate-200 shadow-sm">
                            <div className="font-bold text-purple-300 flex items-center gap-1.5 mb-1.5 pb-1 border-b border-slate-800/80 text-xs">
                              <span>💡</span> Analisis & Pertimbangan AI:
                            </div>
                            <div className="whitespace-pre-line text-slate-300 font-sans leading-relaxed text-[11px] space-y-1">
                              {reasoningStr}
                            </div>
                          </div>
                        );
                      })()}

                      {/* Action Buttons */}
                      <div className="flex items-center gap-2.5 pt-1">
                        {!isTradeable ? (
                          <button
                            type="button"
                            onClick={() => rejectLLMSetup(llmRecommendation.reasoning || `Ditolak oleh LLM (${sigUpper})`)}
                            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 transition-colors cursor-pointer active:scale-95"
                          >
                            <span>✓</span>
                            <span>Pahami Keputusan ({sigUpper} - Stand Aside)</span>
                          </button>
                        ) : (
                          <>
                            <button
                              type="button"
                              onClick={executeLLMSetup}
                              className="flex items-center gap-1.5 rounded-lg border border-emerald-500/60 bg-emerald-500/20 px-4 py-2 text-xs font-bold text-emerald-300 hover:bg-emerald-500/30 transition-all cursor-pointer shadow-sm active:scale-95"
                            >
                              <span>✓</span>
                              <span>Eksekusi Trade ({sigUpper})</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => rejectLLMSetup("Ditolak oleh User")}
                              className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-500/15 px-4 py-2 text-xs font-semibold text-rose-300 hover:bg-rose-500/25 transition-all cursor-pointer active:scale-95"
                            >
                              <span>✗</span>
                              <span>Tolak Setup</span>
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}

            {activePositions.length === 0 ? (
              <div className="py-8 text-center text-slate-400 text-sm bg-slate-900/20 rounded-lg border border-slate-800/40">
                Tidak ada posisi aktif saat ini
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-800/50">
                <table className="min-w-full divide-y divide-slate-800/60 bg-slate-900/10">
                  <thead className="bg-slate-900/40 text-slate-400 text-[11px] font-semibold tracking-wider uppercase">
                    <tr>
                      <th className="py-3 px-4 text-left">Ticket</th>
                      <th className="py-3 px-4 text-left">Type</th>
                      <th className="py-3 px-4 text-left">Signal Type</th>
                      <th className="py-3 px-4 text-left">Reject Reason</th>
                      <th className="py-3 px-4 text-right">Lot</th>
                      <th className="py-3 px-4 text-right">Entry Price</th>
                      <th className="py-3 px-4 text-left">Entry Time</th>
                      <th className="py-3 px-4 text-right">Current Price</th>
                      <th className="py-3 px-4 text-right">SL (Orig → Curr)</th>
                      <th className="py-3 px-4 text-right">TP (Orig → Curr)</th>
                      <th className="py-3 px-4 text-left">Triggers (BE | TP-Ex)</th>
                      <th className="py-3 px-4 text-center">Status</th>
                      <th className="py-3 px-4 text-right">Floating PnL</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-200 text-xs font-medium">
                    {activePositions
                      .map((pos) => {
                      const isWin = pos.pnl >= 0;
                      const isBuy = pos.type === "BUY";
                      const isClosed = pos.is_closed === true;
                      const isRejected = pos.is_rejected === true;
                      const signalType = pos.entry_time == null
                        ? ""
                        : getEntryStructureInfo(pos.entry_time, replayData.structures).latestType;

                      const hasSLChanged = !isClosed && pos.sl && pos.original_sl && Math.abs(pos.sl - pos.original_sl) > 0.01;
                      const hasTPChanged = !isClosed && pos.tp && pos.original_tp && Math.abs(pos.tp - pos.original_tp) > 0.01;

                      // Status Badge Classes
                      let badgeClass = "bg-slate-800/40 text-slate-400 border border-slate-700/30";
                      if (isRejected) {
                        badgeClass = "bg-rose-500/15 text-rose-400 border border-rose-500/30";
                      } else if (isClosed) {
                        badgeClass = isWin
                          ? "bg-emerald-900/30 text-emerald-500 border border-emerald-700/40"
                          : "bg-rose-900/30 text-rose-500 border border-rose-700/40";
                      } else if (pos.status === "BE + TP Expanded") {
                        badgeClass = "bg-fuchsia-500/15 text-fuchsia-400 border border-fuchsia-500/30 shadow-[0_0_8px_rgba(217,70,239,0.15)]";
                      } else if (pos.status === "Break-Even") {
                        badgeClass = "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shadow-[0_0_8px_rgba(16,185,129,0.15)]";
                      } else if (pos.status === "TP Expanded") {
                        badgeClass = "bg-amber-500/15 text-amber-400 border border-amber-500/30 shadow-[0_0_8px_rgba(245,158,11,0.15)]";
                      } else if (pos.status === "Trailing") {
                        badgeClass = "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 shadow-[0_0_8px_rgba(6,182,212,0.15)]";
                      }

                      return (
                        <tr
                          key={`${pos.ticket}-${pos.entry_time ?? "unknown"}-${pos.is_rejected ? "rejected" : "trade"}`}
                          className={cn(
                            "transition-colors",
                            isClosed
                              ? isWin
                                ? "bg-emerald-950/15"
                                : "bg-rose-950/15"
                              : isRejected
                                ? "bg-rose-950/15"
                                : isBuy
                                  ? "bg-emerald-950/10 hover:bg-emerald-950/20"
                                  : "bg-rose-950/10 hover:bg-rose-950/20"
                          )}
                        >
                          <td className="py-3.5 px-4 font-mono text-slate-400">#{pos.ticket}</td>
                          <td className="py-3.5 px-4">
                            <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${
                              isBuy
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            }`}>
                              {pos.type}
                            </span>
                          </td>
                          <td className="py-3.5 px-4">
                            {signalType ? (
                              <span className={`inline-block rounded border px-2 py-0.5 text-[10px] font-bold tracking-wider ${
                                signalType === "CHOCH"
                                  ? "border-violet-400/30 bg-violet-400/10 text-violet-300"
                                  : "border-amber-400/30 bg-amber-400/10 text-amber-300"
                              }`}>
                                {signalType}
                              </span>
                            ) : (
                              <span className="text-slate-600">-</span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-[10px] text-rose-300">{pos.reject_reason || "-"}</td>
                          <td className="py-3.5 px-4 text-right font-mono">{pos.lot_size.toFixed(2)}</td>
                          <td className="py-3.5 px-4 text-right font-mono">${pos.entry_price.toFixed(2)}</td>
                          <td className="py-3.5 px-4 font-mono text-[10px] text-slate-400 whitespace-nowrap">
                            {pos.entry_time == null
                              ? "-"
                              : `${new Date(pos.entry_time * 1000).toISOString().slice(0, 16).replace("T", " ")} UTC`}
                          </td>
                          <td className={`py-3.5 px-4 text-right font-mono ${isClosed ? "text-slate-500" : ""}`}>
                            {isRejected ? <span className="text-slate-600">-</span> : <>{isClosed ? <span className="text-[10px] text-slate-500">Exit: </span> : null}${pos.current_price.toFixed(2)}</>}
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono">
                            {hasSLChanged ? (
                              <span className="flex items-center justify-end gap-1.5">
                                <span className="text-slate-500 line-through">${pos.original_sl.toFixed(2)}</span>
                                <span className="text-slate-400">→</span>
                                <span className="text-rose-400 font-bold">${pos.sl.toFixed(2)}</span>
                              </span>
                            ) : (
                              <span className="text-slate-400">${pos.original_sl ? pos.original_sl.toFixed(2) : "-"}</span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono">
                            {hasTPChanged ? (
                              <span className="flex items-center justify-end gap-1.5">
                                <span className="text-slate-500 line-through">${pos.original_tp.toFixed(2)}</span>
                                <span className="text-slate-400">→</span>
                                <span className="text-emerald-400 font-bold">${pos.tp.toFixed(2)}</span>
                              </span>
                            ) : (
                              <span className="text-slate-400">${pos.original_tp ? pos.original_tp.toFixed(2) : "-"}</span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-left font-mono text-[10px] space-y-0.5">
                            {isClosed ? (
                              <span className="text-slate-600">—</span>
                            ) : (
                              <>
                                <div className="flex items-center gap-1.5">
                                  <span className="text-slate-500">BE:</span>
                                  {pos.be_trigger_price == null ? (
                                    <span className="text-slate-600">-</span>
                                  ) : pos.is_be_active ? (
                                    <span className="px-1.5 py-0.2 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded font-bold">Active</span>
                                  ) : (
                                    <span className="text-slate-300">${pos.be_trigger_price.toFixed(2)}</span>
                                  )}
                                </div>
                                <div className="flex items-center gap-1.5">
                                  <span className="text-slate-500">TP-Ex:</span>
                                  {pos.is_tp_maxed ? (
                                    <span className="px-1.5 py-0.2 bg-rose-500/10 text-rose-400 border border-rose-500/20 rounded font-bold text-[9px]">Maxed</span>
                                  ) : pos.tp_trigger_price == null ? (
                                    <span className="text-slate-600">-</span>
                                  ) : (
                                    <span className="text-cyan-400">${pos.tp_trigger_price.toFixed(2)}</span>
                                  )}
                                </div>
                              </>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-center">
                            <span className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold transition-all duration-300 ${badgeClass}`}>
                              {pos.status}
                            </span>
                          </td>
                          <td className={`py-3.5 px-4 text-right font-mono font-bold text-sm ${
                            isRejected ? "text-white" : isWin ? "text-emerald-400" : "text-rose-500"
                          }`}>
                            {isWin ? "+" : ""}${pos.pnl.toFixed(2)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── Strategy Settings & Parameters ── */}
        {replayData && (
          <section className="flex-shrink-0 rounded-xl border border-slate-800/80 bg-slate-900/45 p-5 shadow-[0_8px_32px_rgba(0,0,0,.28)]">
            <button
              type="button"
              onClick={() => setIsStrategyPanelOpen((open) => !open)}
              aria-expanded={isStrategyPanelOpen}
              className="flex w-full cursor-pointer items-center justify-between gap-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70"
            >
              <span className="flex items-center gap-2.5 text-sm font-bold text-slate-100">
                <span className="flex h-7 w-7 items-center justify-center rounded-md border border-cyan-500/25 bg-cyan-500/10 text-cyan-400">
                  <Settings className="h-4 w-4" />
                </span>
                Strategy Settings &amp; Parameters
              </span>
              <span className="rounded border border-slate-800 bg-slate-950/40 px-2 py-1 text-[10px] font-semibold text-slate-400">
                {isStrategyPanelOpen ? "Tutup Panel ▲" : "Buka Panel ▼"}
              </span>
            </button>

            {isStrategyPanelOpen && (
              <div className="mt-5 border-t border-slate-800/60 pt-5">
                <div className="space-y-3">
                  <div className="flex items-center gap-1.5 border-b border-slate-800/50 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    <Target className="h-3.5 w-3.5 text-fuchsia-400" />
                    Trend &amp; Cycle Schema Map
                  </div>
                  <StructureSchemaMap params={entryFilterParams} />
                  <div className="grid border-t border-slate-800/50 lg:grid-cols-2">
                    <div className="divide-y divide-slate-800/50 py-2 lg:pr-5">
                      <div className="px-1 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Entry Settings
                      </div>
                      <EntryToggle
                        label="CHoCH Entries"
                        description="Change of Character patterns"
                        checked={entryFilterParams.entry_choch}
                        onChange={() => setEntryFilterParams((prev) => ({ ...prev, entry_choch: !prev.entry_choch }))}
                        disabled={isAutoDecisionActive}
                        disabledReason={isAutoDecisionActive ? "Nonaktif — LLM auto-thinking aktif" : undefined}
                      />
                      <EntryToggle
                        label="BOS Cycle 1 Entries"
                        description="First BOS after CHoCH"
                        checked={entryFilterParams.entry_bos}
                        onChange={() => setEntryFilterParams((prev) => ({ ...prev, entry_bos: !prev.entry_bos }))}
                        disabled={isAutoDecisionActive}
                        disabledReason={isAutoDecisionActive ? "Nonaktif — LLM auto-thinking aktif" : undefined}
                      />
                      <EntryToggle
                        label="BOS Cycle 2+ Entries"
                        description="Second and subsequent BOS cycles"
                        checked={entryFilterParams.entry_bos_cycle_2_plus}
                        onChange={() => setEntryFilterParams((prev) => ({ ...prev, entry_bos_cycle_2_plus: !prev.entry_bos_cycle_2_plus }))}
                        disabled={isAutoDecisionActive}
                        disabledReason={isAutoDecisionActive ? "Nonaktif — LLM auto-thinking aktif" : undefined}
                      />
                      <label className="flex items-center justify-between gap-4 px-1 py-3">
                        <span>
                          <span className="block text-xs font-semibold text-slate-200">Max Cycle BOS</span>
                          <span className="mt-0.5 block text-[10px] text-slate-500">0 means unlimited cycles</span>
                        </span>
                        <input
                          type="text"
                          inputMode="numeric"
                          pattern="[0-9]*"
                          aria-label="Max Cycle BOS"
                          value={maxBosCycleInput}
                          onChange={(event) => {
                            const digits = event.target.value.replace(/\D/g, "");
                            const normalized = digits === "" ? "" : String(Number(digits));
                            setMaxBosCycleInput(normalized);
                            if (normalized === "") return;
                            const value = Number(normalized);
                            setEntryFilterParams((prev) => ({ ...prev, max_bos_cycle: value }));
                          }}
                          onBlur={() => {
                            if (maxBosCycleInput !== "") return;
                            setMaxBosCycleInput("0");
                            setEntryFilterParams((prev) => ({ ...prev, max_bos_cycle: 0 }));
                          }}
                          className="h-8 w-20 appearance-none rounded-md border border-slate-700 bg-slate-950/80 px-2 text-center font-mono text-xs text-cyan-300 outline-none focus:border-cyan-500/60 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                        />
                      </label>
                      <div className="px-1 pt-4 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Position &amp; Exit
                      </div>
                      <label className="flex items-center justify-between gap-4 px-1 py-3">
                        <span>
                          <span className="block text-xs font-semibold text-slate-200">Initial Balance ($)</span>
                          <span className="mt-0.5 block text-[10px] text-slate-500">Modal awal akun replay</span>
                        </span>
                        <input
                          type="text"
                          inputMode="decimal"
                          aria-label="Initial Balance"
                          value={initialBalanceInput}
                          onChange={(event) => {
                            const nextValue = event.target.value.replace(",", ".");
                            if (!/^\d*(\.\d{0,2})?$/.test(nextValue)) return;
                            setInitialBalanceInput(nextValue);
                            if (nextValue === "" || nextValue === ".") return;
                            const balance = Number(nextValue);
                            if (!Number.isFinite(balance) || balance < 0) return;
                            setStrategyParams((prev) => ({ ...prev, initial_balance: balance }));
                          }}
                          onBlur={() => {
                            const balance = Math.max(0, Number(initialBalanceInput) || 1000);
                            setInitialBalanceInput(String(balance));
                            setStrategyParams((prev) => ({ ...prev, initial_balance: balance }));
                          }}
                          className="h-8 w-24 appearance-none rounded-md border border-slate-700 bg-slate-950/80 px-2 text-center font-mono text-xs text-cyan-300 outline-none focus:border-cyan-500/60 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                        />
                      </label>
                      <label className="flex items-center justify-between gap-4 px-1 py-3">
                        <span>
                          <span className="block text-xs font-semibold text-slate-200">Lot Size</span>
                          <span className="mt-0.5 block text-[10px] text-slate-500">0 = Auto Risk Manager</span>
                        </span>
                        <input
                          type="text"
                          inputMode="decimal"
                          aria-label="Lot Size"
                          value={lotSizeInput}
                          onChange={(event) => {
                            const nextValue = event.target.value.replace(",", ".");
                            if (!/^\d*(\.\d{0,2})?$/.test(nextValue)) return;
                            setLotSizeInput(nextValue);
                            if (nextValue === "" || nextValue === ".") return;
                            const lotSize = Math.min(50, Number(nextValue));
                            if (!Number.isFinite(lotSize)) return;
                            setStrategyParams((prev) => ({ ...prev, lot_override: lotSize }));
                          }}
                          onBlur={() => {
                            const lotSize = Math.min(50, Math.max(0, Number(lotSizeInput) || 0));
                            setLotSizeInput(String(lotSize));
                            setStrategyParams((prev) => ({ ...prev, lot_override: lotSize }));
                          }}
                          className="h-8 w-20 appearance-none rounded-md border border-slate-700 bg-slate-950/80 px-2 text-center font-mono text-xs text-cyan-300 outline-none focus:border-cyan-500/60 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                        />
                      </label>
                      <EntryToggle
                        label="Force 24h Close"
                        description="Automatically close open trades after 24 hours"
                        checked={strategyParams.force_24h_close}
                        onChange={() => setStrategyParams((prev) => ({ ...prev, force_24h_close: !prev.force_24h_close }))}
                      />
                      <div className="px-1 pt-4 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        ATR Adaptive SL/TP
                      </div>
                      <div className="flex items-center justify-between gap-4 px-1 py-3">
                        <div className="min-w-0">
                          <div className="flex items-center text-xs font-semibold text-slate-200">
                            Gunakan ATR untuk SL/TP
                            <StrategyTooltip
                              fungsi="Jarak SL/TP dihitung dari ATR (Average True Range) sehingga menyesuaikan volatilitas pasar. Saat harga tinggi (mis. 5000), SL/TP otomatis lebih lebar; saat harga rendah (mis. 1000), SL/TP lebih ketat. Ini mencegah SL/TP terlalu sempit di harga tinggi."
                              contoh="Entry $5000, ATR $40 → SL = 40 × 1.5 = $60 (600 pips), TP = 40 × 2.0 = $80 (800 pips). Entry $1000, ATR $8 → SL = 8 × 1.5 = $12 (120 pips), TP = 8 × 2.0 = $16 (160 pips)."
                            />
                          </div>
                          <div className="mt-0.5 text-[10px] text-slate-500">
                            Jarak SL/TP menyesuaikan volatilitas (ATR), proporsional di harga 1000 maupun 5000
                          </div>
                        </div>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={strategyParams.use_atr_sltp}
                          aria-label="Gunakan ATR untuk SL/TP"
                          onClick={() => setStrategyParams((prev) => ({ ...prev, use_atr_sltp: !prev.use_atr_sltp }))}
                          className={cn(
                            "relative h-5 w-9 shrink-0 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70",
                            strategyParams.use_atr_sltp ? "border-cyan-400/50 bg-cyan-500/25" : "border-slate-700 bg-slate-900"
                          )}
                        >
                          <span
                            className={cn(
                              "absolute left-0.5 top-0.5 h-3.5 w-3.5 rounded-full transition-transform",
                              strategyParams.use_atr_sltp ? "translate-x-4 bg-cyan-300" : "translate-x-0 bg-slate-500"
                            )}
                          />
                        </button>
                      </div>
                      {strategyParams.use_atr_sltp && (
                        <>
                          <label className="flex items-center justify-between gap-4 px-1 py-3">
                            <span>
                              <span className="block text-xs font-semibold text-slate-200">ATR Period</span>
                              <span className="mt-0.5 block text-[10px] text-slate-500">Jumlah candle untuk hitung ATR</span>
                            </span>
                            <input
                              type="text"
                              inputMode="numeric"
                              pattern="[0-9]*"
                              aria-label="ATR Period"
                              value={atrPeriodInput}
                              onChange={(event) => {
                                const digits = event.target.value.replace(/\D/g, "");
                                setAtrPeriodInput(digits);
                                if (digits === "") return;
                                const value = Math.max(2, Number(digits));
                                setStrategyParams((prev) => ({ ...prev, atr_period: value }));
                              }}
                              onBlur={() => {
                                const value = Math.max(2, Number(atrPeriodInput) || 14);
                                setAtrPeriodInput(String(value));
                                setStrategyParams((prev) => ({ ...prev, atr_period: value }));
                              }}
                              className="h-8 w-20 appearance-none rounded-md border border-slate-700 bg-slate-950/80 px-2 text-center font-mono text-xs text-cyan-300 outline-none focus:border-cyan-500/60 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                            />
                          </label>
                          <label className="flex items-center justify-between gap-4 px-1 py-3">
                            <span>
                              <span className="block text-xs font-semibold text-slate-200">SL Multiplier</span>
                              <span className="mt-0.5 block text-[10px] text-slate-500">SL = ATR × pengali (default 1.5)</span>
                            </span>
                            <input
                              type="text"
                              inputMode="decimal"
                              aria-label="ATR SL Multiplier"
                              value={atrSlMultInput}
                              onChange={(event) => {
                                const nextValue = event.target.value.replace(",", ".");
                                if (!/^\d*(\.\d{0,2})?$/.test(nextValue)) return;
                                setAtrSlMultInput(nextValue);
                                if (nextValue === "" || nextValue === ".") return;
                                const value = Math.max(0.1, Number(nextValue));
                                setStrategyParams((prev) => ({ ...prev, atr_sl_multiplier: value }));
                              }}
                              onBlur={() => {
                                const value = Math.max(0.1, Number(atrSlMultInput) || 1.5);
                                setAtrSlMultInput(String(value));
                                setStrategyParams((prev) => ({ ...prev, atr_sl_multiplier: value }));
                              }}
                              className="h-8 w-20 appearance-none rounded-md border border-slate-700 bg-slate-950/80 px-2 text-center font-mono text-xs text-cyan-300 outline-none focus:border-cyan-500/60 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                            />
                          </label>
                          <label className="flex items-center justify-between gap-4 px-1 py-3">
                            <span>
                              <span className="block text-xs font-semibold text-slate-200">TP Multiplier</span>
                              <span className="mt-0.5 block text-[10px] text-slate-500">TP = ATR × pengali (default 2.0)</span>
                            </span>
                            <input
                              type="text"
                              inputMode="decimal"
                              aria-label="ATR TP Multiplier"
                              value={atrTpMultInput}
                              onChange={(event) => {
                                const nextValue = event.target.value.replace(",", ".");
                                if (!/^\d*(\.\d{0,2})?$/.test(nextValue)) return;
                                setAtrTpMultInput(nextValue);
                                if (nextValue === "" || nextValue === ".") return;
                                const value = Math.max(0.1, Number(nextValue));
                                setStrategyParams((prev) => ({ ...prev, atr_tp_multiplier: value }));
                              }}
                              onBlur={() => {
                                const value = Math.max(0.1, Number(atrTpMultInput) || 2.0);
                                setAtrTpMultInput(String(value));
                                setStrategyParams((prev) => ({ ...prev, atr_tp_multiplier: value }));
                              }}
                              className="h-8 w-20 appearance-none rounded-md border border-slate-700 bg-slate-950/80 px-2 text-center font-mono text-xs text-cyan-300 outline-none focus:border-cyan-500/60 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                            />
                          </label>
                        </>
                      )}

                      {/* ── Decision Engine (Rule vs LLM) ── */}
                      {/* ── Mesin Keputusan & AI Analysis ── */}
                      <div className="px-1 pt-4 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Mesin Keputusan & AI Analysis
                      </div>

                      {/* 1. SmartRule Engine */}
                      <div className="flex items-center justify-between gap-4 px-1 py-3">
                        <div className="min-w-0">
                          <div className="flex items-center text-xs font-semibold text-cyan-300">
                            ⚙️ SmartRule Engine
                            <StrategyTooltip
                              fungsi="Menggunakan aturan baku Smart Money Concepts (SMC) dan filter teknikal deterministik secara instan tanpa memanggil AI."
                              contoh="Entry otomatis dievaluasi berdasarkan break struktur CHoCH/BOS dan filter EMA200."
                            />
                          </div>
                          <div className="mt-0.5 text-[10px] text-slate-500">
                            Eksekusi deterministik cepat berbasis aturan indikator & filter
                          </div>
                        </div>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={decisionEngine === "rule"}
                          aria-label="Aktifkan SmartRule Engine"
                          onClick={() => {
                            setDecisionEngine((prev) => (prev === "rule" ? "off" as any : "rule"));
                          }}
                          className={cn(
                            "relative h-5 w-9 shrink-0 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70",
                            decisionEngine === "rule" ? "border-cyan-400/50 bg-cyan-500/25" : "border-slate-700 bg-slate-900"
                          )}
                        >
                          <span
                            className={cn(
                              "absolute left-0.5 top-0.5 h-3.5 w-3.5 rounded-full transition-transform",
                              decisionEngine === "rule" ? "translate-x-4 bg-cyan-300" : "translate-x-0 bg-slate-500"
                            )}
                          />
                        </button>
                      </div>

                      {/* 2. LLM 7-Step Reasoning */}
                      <div className="flex items-center justify-between gap-4 px-1 py-3">
                        <div className="min-w-0">
                          <div className="flex items-center text-xs font-semibold text-purple-300">
                            🧠 LLM 7-Step Reasoning
                            <StrategyTooltip
                              fungsi="AI melakukan analisis kontekstual mendalam melalui 7 tahapan: Regime, Structure, Catalyst, Risk Asymmetry, Path Dependency, Decision, & Invalidation."
                              contoh="Menganalisis multi-timeframe M15/H1/H4 dan memberikan justifikasi komprehensif sebelum merumuskan trade setup."
                            />
                          </div>
                          <div className="mt-0.5 text-[10px] text-slate-500">
                            Analisis institusional mendalam 7 langkah berbasis AI multi-tier
                          </div>
                        </div>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={decisionEngine === "llm"}
                          aria-label="Aktifkan LLM 7-Step Reasoning"
                          onClick={() => {
                            setDecisionEngine((prev) => (prev === "llm" ? "off" as any : "llm"));
                          }}
                          className={cn(
                            "relative h-5 w-9 shrink-0 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400/70",
                            decisionEngine === "llm" ? "border-purple-400/50 bg-purple-500/25" : "border-slate-700 bg-slate-900"
                          )}
                        >
                          <span
                            className={cn(
                              "absolute left-0.5 top-0.5 h-3.5 w-3.5 rounded-full transition-transform",
                              decisionEngine === "llm" ? "translate-x-4 bg-purple-300" : "translate-x-0 bg-slate-500"
                            )}
                          />
                        </button>
                      </div>

                      {/* 3. Gunakan LLM untuk SL/TP/Lot */}
                      <div className="flex items-center justify-between gap-4 px-1 py-3">
                        <div className="min-w-0">
                          <div className="flex items-center text-xs font-semibold text-purple-300">
                            🤖 Gunakan LLM untuk SL/TP/Lot
                            <StrategyTooltip
                              fungsi="Saat terdeteksi struktur CHoCH atau BOS, AI langsung menganalisis dan memunculkan kartu rekomendasi setup posisi (Signal, SL, TP, & Lot) di Daftar Posisi dengan tombol Eksekusi dan Tolak."
                              contoh="Struktur CHoCH muncul → LLM thinking → Muncul kartu rekomendasi BUY, SL $4419.70, TP $4509.60, Lot 0.01 → Anda klik '✓ Eksekusi' untuk membuka posisi atau '✗ Tolak'."
                            />
                          </div>
                          <div className="mt-0.5 text-[10px] text-slate-500">
                            Auto-thinking saat CHoCH/BOS dengan kartu rekomendasi SL, TP, & Lot
                          </div>
                        </div>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={useLLMSetup}
                          aria-label="Gunakan LLM untuk SL/TP/Lot"
                          onClick={() => {
                            setUseLLMSetup((prev) => {
                              const next = !prev;
                              setAutoDecisionEnabled(next);
                              return next;
                            });
                          }}
                          className={cn(
                            "relative h-5 w-9 shrink-0 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400/70",
                            useLLMSetup ? "border-purple-400/50 bg-purple-500/25" : "border-slate-700 bg-slate-900"
                          )}
                        >
                          <span
                            className={cn(
                              "absolute left-0.5 top-0.5 h-3.5 w-3.5 rounded-full transition-transform",
                              useLLMSetup ? "translate-x-4 bg-purple-300" : "translate-x-0 bg-slate-500"
                            )}
                          />
                        </button>
                      </div>

                      <div className="px-1 pt-4 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Smart Money Concepts (SMC)
                      </div>
                      <div className="flex items-center justify-between gap-4 px-1 py-3">
                        <div className="min-w-0">
                          <div className="flex items-center text-xs font-semibold text-purple-300">
                            🏷️ Visual Supply & Demand
                            <StrategyTooltip
                              fungsi="Menampilkan zona Order Block / Resistance (Ungu) dan Support (Emas) berdasarkan struktur pasar secara visual di grafik tanpa bertubrukan dengan warna SL (Merah) dan TP (Hijau)."
                              contoh="Puncak swing high membentuk kotak Ungu Supply Zone. Lembah swing low membentuk kotak Emas Demand Zone."
                            />
                          </div>
                          <div className="mt-0.5 text-[10px] text-slate-500">
                            Kotak Supply / Resistance (Ungu) & Demand / Support (Emas)
                          </div>
                        </div>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={strategyParams.show_supply_demand}
                          aria-label="Tampilkan Visual Supply & Demand"
                          onClick={() => {
                            setStrategyParams((prev) => {
                              const next = !prev.show_supply_demand;
                              if (supplyDemandPrimitiveRef.current) {
                                supplyDemandPrimitiveRef.current.setVisible(next);
                              }
                              return { ...prev, show_supply_demand: next };
                            });
                          }}
                          className={cn(
                            "relative h-5 w-9 shrink-0 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400/70",
                            strategyParams.show_supply_demand ? "border-purple-400/50 bg-purple-500/25" : "border-slate-700 bg-slate-900"
                          )}
                        >
                          <span
                            className={cn(
                              "absolute left-0.5 top-0.5 h-3.5 w-3.5 rounded-full transition-transform",
                              strategyParams.show_supply_demand ? "translate-x-4 bg-purple-300" : "translate-x-0 bg-slate-500"
                            )}
                          />
                        </button>
                      </div>

                      <div className="flex items-center justify-between gap-4 px-1 py-3">
                        <div className="min-w-0">
                          <div className="flex items-center text-xs font-semibold text-sky-300">
                            🎯 Visual Liquidity Pools (BSL / SSL)
                            <StrategyTooltip
                              fungsi="Menampilkan garis level likuiditas Buy-Side (Cyan / Equal Highs) dan Sell-Side (Orange / Equal Lows) tempat target perburuan likuiditas dan Stop Loss pasar terkumpul."
                              contoh="Garis Cyan 🎯 BSL di atas puncak swing high. Garis Orange 🎯 SSL di bawah lembah swing low. Garis otomatis berubah menjadi (Swept) jika telah tertembus harga."
                            />
                          </div>
                          <div className="mt-0.5 text-[10px] text-slate-500">
                            Garis target likuiditas BSL (Cyan) & SSL (Orange)
                          </div>
                        </div>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={strategyParams.show_liquidity_pools}
                          aria-label="Tampilkan Visual Liquidity Pools"
                          onClick={() => {
                            setStrategyParams((prev) => {
                              const next = !prev.show_liquidity_pools;
                              if (liquidityPoolsPrimitiveRef.current) {
                                liquidityPoolsPrimitiveRef.current.setVisible(next);
                              }
                              return { ...prev, show_liquidity_pools: next };
                            });
                          }}
                          className={cn(
                            "relative h-5 w-9 shrink-0 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70",
                            strategyParams.show_liquidity_pools ? "border-sky-400/50 bg-sky-500/25" : "border-slate-700 bg-slate-900"
                          )}
                        >
                          <span
                            className={cn(
                              "absolute left-0.5 top-0.5 h-3.5 w-3.5 rounded-full transition-transform",
                              strategyParams.show_liquidity_pools ? "translate-x-4 bg-sky-300" : "translate-x-0 bg-slate-500"
                            )}
                          />
                        </button>
                      </div>
                    </div>

                    <div className="divide-y divide-slate-800/50 border-t border-slate-800/50 py-2 lg:border-l lg:border-t-0 lg:pl-5">
                      <div className="px-1 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        EA Entry Filters
                      </div>
                      <EntryToggle
                        label="H1 EMA200 Filter"
                        description="H1 close must be above/below EMA200 by trade direction"
                        checked={entryFilterParams.h1_ema200_filter}
                        onChange={() => setEntryFilterParams((prev) => ({ ...prev, h1_ema200_filter: !prev.h1_ema200_filter }))}
                      />
                      <EntryToggle
                        label="H4 EMA Filter"
                        description="H4 EMA trend with EA gap threshold"
                        checked={entryFilterParams.h4_ema_filter}
                        onChange={() => setEntryFilterParams((prev) => ({ ...prev, h4_ema_filter: !prev.h4_ema_filter }))}
                      />
                      <EntryToggle
                        label="EMA Slope Filter"
                        description="M15 EMA200 must move in the trade direction"
                        checked={entryFilterParams.ema_slope_filter}
                        onChange={() => setEntryFilterParams((prev) => ({ ...prev, ema_slope_filter: !prev.ema_slope_filter }))}
                      />
                      <EntryToggle
                        label="Body Ratio Filter"
                        description="M15 candle body must be at least 40% of its range"
                        checked={entryFilterParams.body_ratio_filter}
                        onChange={() => setEntryFilterParams((prev) => ({ ...prev, body_ratio_filter: !prev.body_ratio_filter }))}
                      />
                      <EntryToggle
                        label="Session Filter"
                        description="Block entries recorded at 01:00 UTC"
                        checked={entryFilterParams.session_filter}
                        onChange={() => setEntryFilterParams((prev) => ({ ...prev, session_filter: !prev.session_filter }))}
                      />
                      <EntryToggle
                        label="🛡️ EMA Stretch Filter"
                        description="Peringatkan/HOLD jika jarak harga >3.5x ATR dari M15 EMA200"
                        checked={entryFilterParams.ema_stretch_filter}
                        onChange={() => setEntryFilterParams((prev) => ({ ...prev, ema_stretch_filter: !prev.ema_stretch_filter }))}
                      />
                      <EntryToggle
                        label="🛡️ BOS Cycle Stage Filter"
                        description="Peringatkan/HOLD jika sudah mencapai BOS ke-4+ berturut-turut tanpa pullback"
                        checked={entryFilterParams.bos_cycle_filter}
                        onChange={() => setEntryFilterParams((prev) => ({ ...prev, bos_cycle_filter: !prev.bos_cycle_filter }))}
                      />
                      <div className="px-1 pt-4 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Chart Indicators
                      </div>
                      <EntryToggle
                        label="MA 20"
                        description="20-period simple moving average"
                        checked={isMa20Visible}
                        onChange={() => setIsMa20Visible((visible) => !visible)}
                      />
                      <EntryToggle
                        label="MA 50"
                        description="50-period simple moving average"
                        checked={isMa50Visible}
                        onChange={() => setIsMa50Visible((visible) => !visible)}
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </section>
        )}

        {/* ── Monthly Summary Section (100% Identical to trades.tsx) ── */}
        <div className="glass-card mt-2 flex-shrink-0">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <h2 className="text-xl font-semibold">📋 Monthly Performance Summary</h2>

            {/* Filter Controls */}
            <div className="flex flex-wrap items-center gap-3">
              {/* Year Select Dropdown */}
              <div className="relative">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400 font-medium">Tahun:</span>
                  <button
                    onClick={() => setIsYearDropdownOpen((prev) => !prev)}
                    className="flex items-center justify-between gap-2 bg-cyan-500/10 border border-cyan-500/25 text-cyan-300 rounded-lg px-3 py-1.5 text-xs font-semibold focus:outline-none hover:bg-cyan-500/15 transition-all cursor-pointer shadow-[0_0_12px_rgba(6,182,212,0.1)] min-w-[75px]"
                  >
                    <span>{monthlySummaryYearFilter}</span>
                    <span className="text-[10px] text-cyan-400">▼</span>
                  </button>
                </div>

                {isYearDropdownOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setIsYearDropdownOpen(false)}
                    />
                    <div className="absolute right-0 mt-1.5 w-24 bg-slate-900/90 border border-slate-800 rounded-lg shadow-2xl backdrop-blur-xl z-50 overflow-hidden py-1">
                      {availableYears.map((year) => (
                        <button
                          key={year}
                          onClick={() => {
                            setMonthlySummaryYearFilter(year);
                            setIsYearDropdownOpen(false);
                          }}
                          className={`w-full text-left px-3 py-2 text-xs transition-colors hover:bg-cyan-500/10 hover:text-cyan-300 font-medium cursor-pointer ${monthlySummaryYearFilter === year ? "text-cyan-400 bg-cyan-500/5" : "text-slate-300"
                            }`}
                        >
                          {year}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>

              {/* Performance Status Tabs */}
              <div className="flex bg-slate-950/40 p-0.5 rounded-lg border border-slate-800/80 backdrop-blur-md shadow-[0_4px_12px_rgba(0,0,0,0.2)]">
                {(["all", "profit", "loss"] as const).map((perfFilter) => (
                  <button
                    key={perfFilter}
                    onClick={() => setMonthlySummaryPerformanceFilter(perfFilter)}
                    className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${monthlySummaryPerformanceFilter === perfFilter
                      ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)]"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/40"
                      }`}
                  >
                    {perfFilter === "all" ? "Semua" : perfFilter === "profit" ? "Profit Only" : "Loss Only"}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="overflow-hidden">
            <table className="w-full border-collapse text-sm">
              <thead className="bg-slate-900/30 border-b border-slate-800/60">
                <tr>
                  <th className="px-4 py-3.5 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">Month</th>
                  <th className="px-4 py-3.5 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">Trades</th>
                  <th className="px-4 py-3.5 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">Win Rate</th>
                  <th className="px-4 py-3.5 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">Profit</th>
                  <th className="px-4 py-3.5 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">Loss</th>
                  <th className="px-4 py-3.5 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">Net P&L</th>
                  <th className="px-4 py-3.5 text-left text-xs text-[var(--text-tertiary)] uppercase tracking-wider font-semibold whitespace-nowrap">Return %</th>
                </tr>
              </thead>
              <tbody>
                {(() => {
                  const filteredMonthlyPNL = monthlyPNL.filter((month) => {
                    if (monthlySummaryYearFilter !== "all" && String(month.year) !== monthlySummaryYearFilter) {
                      return false;
                    }
                    const netProfit = month.net_profit ?? 0;
                    if (monthlySummaryPerformanceFilter === "profit" && netProfit <= 0) {
                      return false;
                    }
                    if (monthlySummaryPerformanceFilter === "loss" && netProfit >= 0) {
                      return false;
                    }
                    return true;
                  });

                  if (filteredMonthlyPNL.length === 0) {
                    return (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center text-slate-400 italic">
                          Tidak ada ringkasan bulanan yang cocok dengan kriteria filter.
                        </td>
                      </tr>
                    );
                  }

                  return filteredMonthlyPNL.map((month, idx) => (
                    <tr
                      key={idx}
                      onClick={() => handleMonthRowClick(month.year, month.month_num, month.month_label || `${month.month} ${month.year}`)}
                      className="border-b border-[rgba(100,116,139,0.1)] hover:bg-cyan-500/10 cursor-pointer transition-colors"
                      title="Klik untuk melihat detail transaksi"
                    >
                      <td className="px-4 py-3.5 whitespace-nowrap font-medium text-slate-200">
                        {month.month_label || `${month.month ?? "N/A"}-${month.year ?? ""}`}
                      </td>
                      <td className="px-4 py-3.5 whitespace-nowrap font-mono">{month.executed_trades ?? month.trades ?? 0}</td>
                      <td className={`px-4 py-3.5 whitespace-nowrap font-semibold ${
                        (month.win_rate ?? 0) > 50
                          ? "text-green-400"
                          : (month.win_rate ?? 0) === 50
                          ? "text-white"
                          : "text-red-400"
                      }`}>
                        {(month.win_rate ?? 0).toFixed(1)}%
                      </td>
                      <td className="px-4 py-3.5 whitespace-nowrap font-mono font-semibold text-green-400">{(month.profit ?? 0).toFixed(2)}</td>
                      <td className="px-4 py-3.5 whitespace-nowrap font-mono font-semibold text-red-400">{(month.loss ?? 0).toFixed(2)}</td>
                      <td className={`px-4 py-3.5 whitespace-nowrap font-mono font-semibold ${(month.net_profit ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {(month.net_profit ?? 0) >= 0 ? "+" : ""}{(month.net_profit ?? 0).toFixed(2)}
                      </td>
                      <td className={`px-4 py-3.5 whitespace-nowrap font-mono font-semibold ${((month.net_profit ?? 0) / 1000 * 100) >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {((month.net_profit ?? 0) / 1000 * 100).toFixed(2)}%
                      </td>
                    </tr>
                  ));
                })()}
              </tbody>
            </table>
          </div>
        </div>
      </div>


      {/* Progress popup for Loading Replay Data */}
      {loadProgress.visible && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[200]">
          <div className="bg-gray-900 border border-purple-500/30 rounded-xl p-6 shadow-2xl w-96">
            <div className="text-center mb-4">
              <div className="text-purple-300 font-semibold text-sm mb-2">
                📅 Loading Replay Data
              </div>
              <div className="text-3xl font-bold text-white mb-1">
                {loadProgress.percent}%
              </div>
              <div className="text-xs text-gray-400">{loadProgress.step}</div>
            </div>
            <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-500 to-blue-500 rounded-full transition-all duration-150"
                style={{ width: `${loadProgress.percent}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Transaction Detail Pop-up Modal (100% Identical to trades.tsx) ── */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xl animate-in fade-in duration-200">
          <div className="w-full max-w-[95vw] xl:max-w-[1400px] bg-slate-900/90 border border-slate-800 rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200 relative">
            {/* Premium Gradient Top Accent Line */}
            <div className="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-500" />

            {/* Header */}
            <div className="p-6 pt-7 border-b border-slate-800 flex items-center justify-between bg-slate-900/40">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-300 border border-cyan-500/15">
                  <CalendarDays className="size-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-100 tracking-tight">
                    Detail Transaksi - {modalTitle}
                  </h3>
                  <p className="text-xs text-slate-400">
                    Daftar transaksi yang ditutup pada bulan ini
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all cursor-pointer hover:scale-105 active:scale-95 duration-150"
                title="Tutup"
              >
                <X className="size-5" />
              </button>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              {isLoadingTrades ? (
                <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400">
                  <Loader2 className="size-8 text-cyan-500 animate-spin" />
                  <span className="text-sm">Memuat data transaksi...</span>
                </div>
              ) : selectedMonthTrades.length === 0 ? (
                <div className="py-20 text-center text-slate-400 text-sm italic">
                  Tidak ada transaksi yang tercatat pada bulan ini.
                </div>
              ) : (
                <>
                  {/* Summary Dashboard Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="bg-slate-950/30 border border-slate-800/60 rounded-xl p-4 flex flex-col">
                      <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">Total Trades</span>
                      <span className="text-2xl font-bold text-slate-200 font-mono">{selectedMonthTrades.length}</span>
                    </div>
                    <div className="bg-slate-950/30 border border-slate-800/60 rounded-xl p-4 flex flex-col">
                      <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">Win Rate</span>
                      <span className="text-2xl font-bold text-cyan-400 font-mono">
                        {(() => {
                          const wins = selectedMonthTrades.filter(t => (t.net_profit ?? 0) > 0).length;
                          return ((wins / selectedMonthTrades.length) * 100).toFixed(1);
                        })()}%
                      </span>
                    </div>
                    <div className="bg-slate-950/30 border border-slate-800/60 rounded-xl p-4 flex flex-col">
                      <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">Net P&L</span>
                      <span className={`text-2xl font-bold font-mono ${selectedMonthTrades.reduce((sum, t) => sum + (t.net_profit ?? 0), 0) >= 0 ? "text-emerald-400" : "text-rose-500"
                        }`}>
                        {selectedMonthTrades.reduce((sum, t) => sum + (t.net_profit ?? 0), 0) >= 0 ? "+" : ""}
                        ${selectedMonthTrades.reduce((sum, t) => sum + (t.net_profit ?? 0), 0).toFixed(2)}
                      </span>
                    </div>
                  </div>

                  {/* Trades Detail Table */}
                  <div className="border border-slate-800/80 rounded-xl overflow-hidden bg-slate-950/20">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="bg-slate-900/60 border-b border-slate-800 text-slate-400 text-xs uppercase font-semibold whitespace-nowrap">
                          <tr>
                            <th className="py-3 px-4">Ticket</th>
                            <th className="py-3 px-4">Type</th>
                            <th className="py-3 px-4 text-right">Lot</th>
                            <th className="py-3 px-4 text-right">Entry Price</th>
                            <th className="py-3 px-4 text-right">SL</th>
                            <th className="py-3 px-4 text-right">TP</th>
                            <th className="py-3 px-4 text-right">Exit Price</th>
                            <th className="py-3 px-4 text-right">Net Profit</th>
                            <th className="py-3 px-4">Entry Time</th>
                            <th className="py-3 px-4">Exit Time</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 text-slate-200">
                          {[...selectedMonthTrades]
                            .sort((a, b) => (a.entry_time || "").localeCompare(b.entry_time || ""))
                            .map((trade) => {
                              const isWin = (trade.net_profit ?? 0) >= 0;
                              return (
                                <tr key={trade.ticket} className="hover:bg-slate-800/30 transition-colors whitespace-nowrap">
                                  <td className="py-3 px-4 font-mono text-xs text-slate-400">#{trade.ticket}</td>
                                  <td className="py-3 px-4">
                                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${trade.type === "BUY"
                                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                      : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                                      }`}>
                                      {trade.type}
                                    </span>
                                  </td>
                                  <td className="py-3 px-4 text-right font-mono">{(getActualLotSize(trade)).toFixed(2)}</td>
                                  <td className="py-3 px-4 text-right font-mono">${(trade.entry_price ?? 0).toFixed(2)}</td>
                                  <td className="py-3 px-4 text-right font-mono text-xs text-rose-400/90">
                                    {trade.sl != null ? `$${trade.sl.toFixed(2)}` : "-"}
                                  </td>
                                  <td className="py-3 px-4 text-right font-mono text-xs text-emerald-400/90">
                                    {trade.tp != null ? `$${trade.tp.toFixed(2)}` : "-"}
                                  </td>
                                  <td className="py-3 px-4 text-right font-mono">${(trade.exit_price ?? 0).toFixed(2)}</td>
                                  <td className={`py-3 px-4 text-right font-mono font-semibold ${isWin ? "text-emerald-400" : "text-rose-500"
                                    }`}>
                                    {isWin ? "+" : ""}${(trade.net_profit ?? 0).toFixed(2)}
                                  </td>
                                  <td className="py-3 px-4 text-xs text-slate-400">{trade.entry_time}</td>
                                  <td className="py-3 px-4 text-xs text-slate-400">{trade.exit_time}</td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-800 bg-slate-900/30 flex justify-end">
              <button
                onClick={() => setIsModalOpen(false)}
                className="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold transition-all cursor-pointer"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
