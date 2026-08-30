import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import * as THREE from "three";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
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
import { Play, Pause, SkipForward, Square, Loader2, Calendar, CalendarDays, X, Rewind, Clapperboard, ArrowUp, ArrowDown, ArrowUpDown, Ghost, Brain, Newspaper, Shield, Building2, Clock3, AlertTriangle, Bot, Settings, Target, Zap, ClipboardList, Database, FileText, ChevronDown, ArrowRight } from "lucide-react";
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
import { useSessionZones } from "@/api/mt5_agents";
import { selectSetupExtremeEvents } from "./structure-extremes";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { LLMMSAReport } from "./components/LLMMSAReport";

// â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

// â”€â”€ Constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const SPEED_MAP: Record<string, number> = {
  "1x": 400,
  "2x": 200,
  "3x": 100,
  "5x": 50,
  "10x": 20,
};

const INITIAL_BALANCE = 1000.00;

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

// â”€â”€ API helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

// â”€â”€ Strategy Info Tooltip â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

interface StrategyTooltipProps {
  fungsi: string;
  contoh: string;
}

function StrategyTooltip({ fungsi, contoh }: StrategyTooltipProps) {
  return (
    <div className="group relative inline-block ml-1.5 align-middle cursor-help">
      <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-[#BFDBFE] text-[10px] text-slate-400 font-bold border border-blue-300/75 hover:bg-slate-700 hover:text-cyan-400 transition-colors">
        ?
      </span>
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 hidden group-hover:block bg-white/95 border border-blue-200 rounded-xl text-[11px] text-slate-600 shadow-2xl backdrop-blur-md z-30 transition-all pointer-events-none">
        <div className="font-bold text-cyan-400 mb-1">Fungsi:</div>
        <div className="mb-2 leading-relaxed text-slate-800">{fungsi}</div>
        <div className="font-bold text-purple-400 mb-0.5">Contoh:</div>
        <div className="leading-relaxed text-slate-400">{contoh}</div>
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-950/95" />
      </div>
    </div>
  );
}

// â”€â”€ Custom Dropdown Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const SELECT_ACCENTS = {
  blue: { border: "rgba(59, 130, 246, 0.45)", bg: "rgba(239, 246, 255, 0.95)", text: "#1e40af", shadow: "rgba(59, 130, 246, 0.15)" },
  purple: { border: "rgba(139, 92, 246, 0.45)", bg: "rgba(250, 245, 255, 0.95)", text: "#6b21a8", shadow: "rgba(139, 92, 246, 0.15)" },
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
          "inline-flex items-center gap-1.5 px-2.5 py-1.5 border rounded-lg text-xs font-bold transition-all duration-200 active:scale-95 cursor-pointer whitespace-nowrap outline-none shadow-sm",
          className ? "w-full justify-between" : ""
        )}
        style={{
          backgroundColor: c.bg,
          borderColor: c.border,
          color: c.text,
          boxShadow: `0 1px 4px ${c.shadow}`,
        }}
      >
        <span>{getLabel(value)}</span>
        <ChevronDown size={12} className={cn("transition-transform duration-200", isOpen && "rotate-180")} style={{ color: c.text }} />
      </button>

      {isOpen && (
        <div
          className="absolute top-[calc(100%+6px)] right-0 min-w-[140px] bg-white border border-slate-200/90 rounded-[10px] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.15)] z-[110] transition-all origin-top-right animate-in fade-in zoom-in-95 slide-in-from-top-2 duration-150 ease-out transform perspective-1000"
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
                className={cn(
                  "px-2.5 py-2 rounded-md border border-transparent text-xs transition-all duration-150 active:scale-[0.98] cursor-pointer",
                  active ? "font-semibold" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                )}
                style={
                  active
                    ? {
                      backgroundColor: c.bg,
                      borderColor: c.border,
                      color: c.text,
                      boxShadow: `0 1px 4px ${c.shadow}`,
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

// â”€â”€ Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

// ponytail: flat object params with defaults â€” no class, no registry
interface StrategyParams {
  trailing_distance: number;   // USD, default 30.00 (3000 poin)
  tp_trigger: number;          // USD, default 10.00 (1000 poin)
  tp_ekspansi: number;         // USD, default 20.00 (2000 poin)
  max_ekspansi: number;        // 0 = unlimited
  enable_breakeven: boolean;
  breakeven_trigger: number;   // USD profit from entry, default 15.00 (1500 poin)
  breakeven_buffer: number;    // USD above entry, default 1.00 (100 poin)
  lot_override: number;        // 0.00 = Auto
  initial_sl_dist: number;     // USD, default 3.00 (300 poin)
  initial_tp_dist: number;     // USD, default 30.00 (3000 poin)
  sl_min_distance: number;     // USD, default 5.00 (500 poin)
  sl_safety_buffer: number;    // USD, default 10.00 (1000 poin)
  force_24h_close: boolean;
}

const DEFAULT_STRATEGY_PARAMS: StrategyParams = {
  trailing_distance: 30.00,
  tp_trigger: 10.00,
  tp_ekspansi: 20.00,
  max_ekspansi: 0,
  enable_breakeven: false,
  breakeven_trigger: 15.00,
  breakeven_buffer: 1.00,
  lot_override: 0.00,
  initial_sl_dist: 3.00,
  initial_tp_dist: 30.00,
  sl_min_distance: 5.00,
  sl_safety_buffer: 10.00,
  force_24h_close: false,
};

const simulateTrailingSLTP = (
  t: any,
  candles: any[],
  currentCandleTime: number,
  params: StrategyParams = DEFAULT_STRATEGY_PARAMS
): {
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

  // Custom initial SL and TP overrides
  const baseSL = params.initial_sl_dist > 0
    ? (typeLower === "buy" ? entryPrice - params.initial_sl_dist : entryPrice + params.initial_sl_dist)
    : (t.sl ?? (typeLower === "buy" ? entryPrice - params.trailing_distance : entryPrice + params.trailing_distance));

  // Opsi A: Jika SL awal terlalu dekat ke entry (kurang dari sl_min_distance), maka SL dipasang di SL_lama - sl_safety_buffer (untuk BUY)
  let initialSL = baseSL;
  if (Math.abs(entryPrice - baseSL) < params.sl_min_distance) {
    initialSL = typeLower === "buy"
      ? baseSL - params.sl_safety_buffer
      : baseSL + params.sl_safety_buffer;
  }

  const initialTP = params.initial_tp_dist > 0
    ? (typeLower === "buy" ? entryPrice + params.initial_tp_dist : entryPrice - params.initial_tp_dist)
    : (t.tp ?? (typeLower === "buy" ? entryPrice + 30.00 : entryPrice - 30.00));

  let currentSL = initialSL;
  let currentTP = initialTP;

  // Compute effective Break-Even buffer
  let effectiveBuffer = params.breakeven_buffer;

  const entryTs = t.entry_time ?? 0;
  if (!candles || candles.length === 0 || entryTs > currentCandleTime) {
    return {
      sl: initialSL,
      tp: initialTP,
      beTriggered: false,
      isClosedSimulated: false,
      exitPriceSimulated: null,
      exitTimeSimulated: null,
      expansionCount: 0,
    };
  }

  let startIdx = 0, lo = 0, hi = candles.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (candles[mid].time >= entryTs) {
      startIdx = mid;
      hi = mid - 1;
    } else {
      lo = mid + 1;
    }
  }

  let endIdx = candles.length - 1;
  lo = startIdx;
  hi = candles.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (candles[mid].time <= currentCandleTime) {
      endIdx = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }

  let expansionCount = 0;
  let beTriggered = false;
  let isClosedSimulated = false;
  let exitPriceSimulated: number | null = null;
  let exitTimeSimulated: number | null = null;

  for (let i = startIdx; i <= endIdx; i++) {
    const c = candles[i];
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
    sl: currentSL,
    tp: currentTP,
    beTriggered,
    isClosedSimulated,
    exitPriceSimulated,
    exitTimeSimulated,
    expansionCount,
  };
};

// â”€â”€ Agent Panel (cursor-following orchestrator frames) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

interface SimAgentState {
  status: "fired" | "skipped" | "error";
  signal: string | null;
  confidence: number;
  approved?: boolean | null;
  filtered?: boolean | null;
  adjustment?: number | null;
  reasoning?: string | null;
  meta?: Record<string, any> | null;
}

interface SimFrame {
  event_time: number;
  event_type: string;
  event_direction: string;
  agents: {
    market_structure: SimAgentState;
    ml_prediction: SimAgentState;
    sentiment: SimAgentState;
    risk_management: SimAgentState;
  };
  final_signal: string;
  approved: boolean | null;
  consensus_level: string;
  consensus_confidence: number;
  // Trade execution context â€” populated by backend _build_frame when the
  // orchestrator approves a BUY/SELL signal. Consumed by TradesOverlayPrimitive
  // (via setAgentTrades) to draw SL/TP zones and entry line on the chart.
  sl_tp?: {
    entry_price?: number;
    sl_price?: number;
    tp_price?: number;
    sl_distance_pips?: number;
    tp_distance_pips?: number;
    rr_ratio?: number;
  } | null;
  position_sizing?: {
    lot_size?: number;
    risk_pct?: number;
    risk_usd?: number;
    multiplier?: number;
  } | null;
  event_price?: number;
  // Sentiment debug context â€” only populated by the single-event endpoint
  // (trading.py:simulate-event). Consumed by the modal's News & Calendar block.
  debug_news?: Array<{ headline?: string; timestamp?: string }>;
  debug_events?: Array<{ event?: string; impact?: string; time?: string }>;
  // Counter-swing flag: frontend should NOT update Agent Consensus panel
  // when true â€” keeps warm-up values from the setup swing event visible.
  is_counter_swing?: boolean;
  llm_msa?: {
    status?: string;
    mode?: string;
    display_report?: Parameters<typeof LLMMSAReport>[0]["report"];
  } | null;
}

const AGENT_PANEL_DEFS = [
  { key: "market_structure" as const, name: "Market Structure Agent", icon: Building2, color: "var(--neon-blue)", bg: "rgba(59,130,246,0.2)" },
  { key: "ml_prediction" as const, name: "ML Filter Agent", icon: Brain, color: "var(--neon-purple)", bg: "rgba(139,92,246,0.2)" },
  { key: "sentiment" as const, name: "Sentiment Agent", icon: Newspaper, color: "var(--neon-emerald)", bg: "rgba(16,185,129,0.2)" },
  { key: "risk_management" as const, name: "Risk Manager", icon: Shield, color: "var(--neon-amber)", bg: "rgba(251,191,36,0.2)" },
];

// Helper to dynamically resolve CHoCH and BOS cycle count from a chronological event list
const getEventCycleInfo = (event: any, allEvents: any[]) => {
  const typeUpper = event.type?.toUpperCase() || "";
  if (typeUpper.includes("CHOCH")) {
    return { isChoch: true, isBos: false, cycle: 0 };
  }
  if (typeUpper.includes("BOS")) {
    // Find index of the last CHoCH event before this event
    let lastChochIndex = -1;
    for (let i = allEvents.length - 1; i >= 0; i--) {
      const e = allEvents[i];
      if (e.time < event.time && e.type?.toUpperCase().includes("CHOCH")) {
        lastChochIndex = i;
        break;
      }
    }

    if (lastChochIndex === -1) {
      // If no CHoCH found, count all BOS up to this event
      const bosBefore = allEvents.filter(e => e.time <= event.time && e.type?.toUpperCase().includes("BOS"));
      return { isChoch: false, isBos: true, cycle: bosBefore.length };
    }

    const lastChochTime = allEvents[lastChochIndex].time;
    const bosSince = allEvents.filter(e => 
      e.time > lastChochTime && 
      e.time <= event.time && 
      e.type?.toUpperCase().includes("BOS")
    );
    return { isChoch: false, isBos: true, cycle: bosSince.length };
  }
  return { isChoch: false, isBos: false, cycle: 0 };
};

// Helper to derive the signal type (CHOCH / BOS) from a structure event type
const getSignalType = (eventType: string | null | undefined): string => {
  const t = (eventType || "").toUpperCase();
  if (t.includes("CHOCH")) return "CHOCH";
  if (t.includes("BOS")) return "BOS";
  return t || "-";
};

// Helper to derive a human-readable reject reason from a simulation frame.
// Returns { label, detail } â€” label is the short column text, detail is a
// plain-language explanation shown in a hover popup.
const getRejectReason = (frame: any): { label: string; detail: string } => {
  if (!frame) return { label: "unknown", detail: "Tidak ada data frame." };
  const agents = frame.agents || {};
  const ms = agents.market_structure || {};
  const ml = agents.ml_prediction || {};
  const sent = agents.sentiment || {};
  const rm = agents.risk_management || {};

  const consensusPct = Math.round((frame.consensus_confidence ?? 0) * 100);
  const thresholdPct = 60;

  // Explicit filter flags (sentiment is the main one that hard-filters)
  if (sent.filtered) {
    return {
      label: "Sentiment filter",
      detail: "Sinyal ditolak karena ada berita atau peristiwa penting yang akan rilis. Sistem menghindari masuk pasar saat berita besar karena harga bisa bergerak liar dan tak terduga.",
    };
  }
  if (ml.filtered) {
    return {
      label: "ML filter",
      detail: "Sinyal ditolak karena model ML menilai peluang untung-rugi kurang menarik. Rasio R:R di bawah batas minimal, artinya risiko lebih besar daripada potensi profit, jadi sistem memilih tidak masuk.",
    };
  }
  if (ms.filtered) {
    return {
      label: "Market structure filter",
      detail: "Sinyal ditolak karena struktur pasar tidak mendukung. Pola harga yang terbentuk tidak memenuhi syarat untuk entry yang aman.",
    };
  }

  // Risk management veto (only runs after consensus approves)
  if (rm.approved === false) {
    return {
      label: "Risk management",
      detail: "Sinyal ditolak karena risikonya terlalu besar. Posisi ini akan mempertaruhkan lebih dari batas maksimal yang diizinkan, jadi sistem menjaga modal agar tidak terlalu berisiko.",
    };
  }

  // Market structure is the primary signal source â€” if it's HOLD, no setup
  if (ms.signal === "HOLD") {
    return {
      label: "Market structure HOLD",
      detail: "Sinyal ditolak karena struktur pasar belum membentuk pola yang jelas. Tidak ada setup yang valid untuk masuk, jadi sistem menahan diri.",
    };
  }

  // ML filter rejected the structure signal
  if (ml.signal === "HOLD") {
    return {
      label: "ML filter",
      detail: "Sinyal ditolak karena model ML tidak mendukung. Peluang profit yang diprediksi terlalu kecil atau tidak meyakinkan, jadi sistem memilih tidak masuk.",
    };
  }

  // Sentiment turned the signal to HOLD
  if (sent.signal === "HOLD") {
    return {
      label: "Sentiment filter",
      detail: "Sinyal ditolak karena sentimen pasar tidak mendukung. Berita atau kondisi ekonomi saat ini tidak sejalan dengan arah sinyal, jadi sistem menahan diri.",
    };
  }

  // Consensus level tells us how strong the agreement was
  if (frame.consensus_level === "no_consensus") {
    return {
      label: "No consensus",
      detail: `Sinyal ditolak karena para agen tidak sepakat. Kekuatan konsensus hanya ${consensusPct}%, padahal minimal dibutuhkan ${thresholdPct}%. Semua agen memilih HOLD (tidak ada sinyal jelas), jadi sistem menahan diri.`,
    };
  }
  if (frame.consensus_level === "weak" || frame.consensus_level === "moderate") {
    return {
      label: "Consensus too weak",
      detail: `Sinyal ditolak karena konsensus para agen terlalu lemah. Kekuatan konsensus hanya ${consensusPct}%, padahal minimal dibutuhkan ${thresholdPct}%. Sistem butuh kesepakatan yang lebih kuat sebelum masuk.`,
    };
  }

  if (frame.final_signal === "HOLD") {
    return {
      label: "No tradeable signal",
      detail: "Sinyal ditolak karena tidak ada sinyal yang layak diperdagangkan. Hasil akhir dari semua agen adalah HOLD (tidak ada arah yang jelas).",
    };
  }
  return {
    label: "Consensus too weak",
    detail: `Sinyal ditolak karena konsensus para agen terlalu lemah. Kekuatan konsensus hanya ${consensusPct}%, padahal minimal dibutuhkan ${thresholdPct}%.`,
  };
};

// â”€â”€ Types for simulation helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export default function SimulationOfDead() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const emaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<any> | null>(null);
  const structurePrimitiveRef = useRef<StructureLinesPrimitive | null>(null);
  const tradesPrimitiveRef = useRef<TradesOverlayPrimitive | null>(null);
  const sessionZonesPrimitiveRef = useRef<SessionZonesPrimitive | null>(null);
  const candleTimeArrayRef = useRef<number[]>([]);
  const candleTimeMapRef = useRef<Map<number, ReplayCandle>>(new Map());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // â”€â”€ Filter state
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
  const [orchestratorEnabled, setOrchestratorEnabled] = useState<boolean>(true);
  const [simSignals, setSimSignals] = useState<any[]>([]);
  const [agentTrades, setAgentTrades] = useState<any[]>([]);
  const [simMetrics, setSimMetrics] = useState<any | null>(null);
  const [simFrames, setSimFrames] = useState<SimFrame[]>([]);
  const [simError, setSimError] = useState<string | null>(null);
  const [simLoading, setSimLoading] = useState<boolean>(false);
  const [simFramesMap, setSimFramesMap] = useState<Record<string, SimFrame>>({});
  const [isFrameLoading, setIsFrameLoading] = useState<boolean>(false);
  const isFrameLoadingRef = useRef<boolean>(false);
  useEffect(() => {
    isFrameLoadingRef.current = isFrameLoading;
  }, [isFrameLoading]);
  const [activeFrame, setActiveFrame] = useState<SimFrame | null>(null);
  const activeFrameAbortControllerRef = useRef<AbortController | null>(null);
  // ponytail: limit concurrent simulate-event fetches â€” drop excess, not queue
  const activeSimFetchesRef = useRef<number>(0);
  const pendingSimTimesRef = useRef<Set<string>>(new Set());
  const completedSimTimesRef = useRef<Set<string>>(new Set());
  const MAX_SIM_FETCHES = 3;
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

  // â”€â”€ Playback state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [speed, setSpeed] = useState<string>("1x");

  // â”€â”€ Strategy params state
  const [strategyParams, setStrategyParams] = useState({ ...DEFAULT_STRATEGY_PARAMS });
  const [vetoMode, setVetoMode] = useState<'hard' | 'soft' | 'none'>('hard');
  const [allowChochEntry, setAllowChochEntry] = useState(false);
  const [allowBosCycle1, setAllowBosCycle1] = useState(true);
  const [allowBosCycle2, setAllowBosCycle2] = useState(false);
  const [allowBosCycle3Plus, setAllowBosCycle3Plus] = useState(false);
  const [force24hClose, setForce24hClose] = useState(false);
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [scenarioName, setScenarioName] = useState("");
  const [isStrategyPanelOpen, setIsStrategyPanelOpen] = useState(false);

  // Running stats
  const [runningProfit, setRunningProfit] = useState(0);
  const [tradeStats, setTradeStats] = useState({ total: 0, wins: 0, losses: 0 });
  const [activePositions, setActivePositions] = useState<any[]>([]);

  // Monthly summary stats
  const [monthlyPNL, setMonthlyPNL] = useState<any[]>([]);
  const [monthlySummaryYearFilter, setMonthlySummaryYearFilter] = useState<string>("2026");
  const [monthlySummaryPerformanceFilter, setMonthlySummaryPerformanceFilter] = useState<string>("all");
  const [isYearDropdownOpen, setIsYearDropdownOpen] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalTitle, setModalTitle] = useState("");
  const [isLoadingTrades, setIsLoadingTrades] = useState(false);
  const [selectedMonthTrades, setSelectedMonthTrades] = useState<any[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<any>(null);
  const [isAgentModalOpen, setIsAgentModalOpen] = useState(false);
  const [selectedPattern, setSelectedPattern] = useState<any>(null);
  const [patternCandles, setPatternCandles] = useState<any[]>([]);
  const [patternStructures, setPatternStructures] = useState<any[]>([]);
  const [patternCandlesLoading, setPatternCandlesLoading] = useState(false);
  const [patternSort, setPatternSort] = useState<{ key: string; dir: "asc" | "desc" }>({ key: "similarity", dir: "desc" });
  const closeAgentModal = useCallback(() => {
    setIsAgentModalOpen(false);
    setSelectedPattern(null);
  }, []);
  const togglePatternSort = (key: string) => {
    setPatternSort(prev => (prev.key === key ? { key, dir: prev.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" }));
  };
  const availableYears = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"];

  useEffect(() => {
    if (!isAgentModalOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeAgentModal();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeAgentModal, isAgentModalOpen]);

  // â”€â”€ Fetch OHLC window + nearby BOS/CHoCH/HH/LL structures for the pattern-detail popup â”€â”€
  useEffect(() => {
    if (!selectedPattern) {
      setPatternCandles([]);
      setPatternStructures([]);
      return;
    }
    let cancelled = false;
    setPatternCandlesLoading(true);
    const params = new URLSearchParams({
      timestamp: selectedPattern.timestamp ?? "",
      timeframe: selectedPattern.timeframe ?? "M15",
    });

    fetch(`${BASE_URL}/trading/pattern-candles?${params.toString()}`)
      .then(res => (res.ok ? res.json() : Promise.reject(res.status)))
      .then(data => {
        if (cancelled) return;
        setPatternCandles(data.candles ?? []);
        setPatternStructures(data.structures ?? []);
      })
      .catch(() => {
        if (cancelled) return;
        setPatternCandles([]);
        setPatternStructures([]);
      })
      .finally(() => {
        if (!cancelled) setPatternCandlesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedPattern]);

  // Session zones for replay chart
  const fromDateStr = `${yearFrom}-${String(monthFrom).padStart(2, "0")}-01`;
  const { data: sessionZonesData } = useSessionZones(fromDateStr, "XAUUSD");
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

      // Orchestrator simulation signals
      for (const sig of simSignals) {
        if (sig.time <= lastCandle.time) {
          const isBuy = sig.signal === "BUY";
          markers.push({
            time: sig.time as any,
            position: isBuy ? "belowBar" : "aboveBar",
            color: isBuy ? "#22c55e" : "#ef4444",
            shape: isBuy ? "arrowUp" : "arrowDown",
            text: sig.signal,
            size: 1,
          });
        }
      }

      markersPluginRef.current?.setMarkers(markers);
    } else {
      markersPluginRef.current?.setMarkers([]);
      structurePrimitiveRef.current?.setLines([]);
      tradesPrimitiveRef.current?.setTrades([]);
    }
  }, [simSignals, replayData, currentIndex]);

  const stopPlayback = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  const handleStop = useCallback(() => {
    stopPlayback();
    setCurrentIndex(0);
    setRunningProfit(0);
    setTradeStats({ total: 0, wins: 0, losses: 0 });
    setActivePositions([]);
    setAgentTrades([]);
    setSimFramesMap({});
    setIsFrameLoading(false);
    setActiveFrame(null);
    completedSimTimesRef.current.clear();
    pendingSimTimesRef.current.clear();
    if (activeFrameAbortControllerRef.current) {
      activeFrameAbortControllerRef.current.abort();
      activeFrameAbortControllerRef.current = null;
    }

    // Clear backend replay cache and delete simulation decisions for the selected year range when stop is clicked
    fetch(`${BASE_URL}/trading/replay/clear-cache?year_from=${yearFrom}&year_to=${yearTo}`, { method: "POST" })
      .catch(err => console.error("Failed to clear replay cache:", err));

    if (replayData) {
      setChartDataToIndex(0, replayData);
    } else {
      // Clear chart series
      candleSeriesRef.current?.setData([]);
      emaSeriesRef.current?.setData([]);
      structurePrimitiveRef.current?.setLines([]);
      tradesPrimitiveRef.current?.setTrades([]);
    }
  }, [stopPlayback, replayData, setChartDataToIndex, yearFrom, yearTo]);

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

  // â”€â”€ Init chart â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
      timeScale: { borderColor: "rgba(100,116,139,0.2)", timeVisible: true, secondsVisible: false },
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

    // Init session zones primitive
    try {
      const sessionPrimitive = new SessionZonesPrimitive();
      (candleSeriesRef.current as any).attachPrimitive(sessionPrimitive);
      sessionZonesPrimitiveRef.current = sessionPrimitive;
    } catch (e) {
      console.warn("Could not attach session zones primitive in replay:", e);
    }

    emaSeriesRef.current = chart.addSeries(LineSeries, {
      color: "#facc15",
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      priceLineVisible: false,
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

  // â”€â”€ Fetch Available Months â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
      .catch(() => { });
  }, []);

  // Reset simulation cache and playback when parameters change
  useEffect(() => {
    if (activeFrameAbortControllerRef.current) {
      activeFrameAbortControllerRef.current.abort();
      activeFrameAbortControllerRef.current = null;
    }
    setSimFramesMap({});
    setActiveFrame(null);
    setSimSignals([]);
    setAgentTrades([]);
    completedSimTimesRef.current.clear();
    pendingSimTimesRef.current.clear();
    setCurrentIndex(0);
    setIsPlaying(false);
  }, [vetoMode, allowChochEntry, allowBosCycle1, allowBosCycle2, allowBosCycle3Plus, force24hClose]);

  // Re-simulate active positions and chart markers whenever strategy parameters change
  useEffect(() => {
    if (isPlaying) return; // Bypass re-simulation while replay is playing to prevent screen flickering glitch
    if (!replayData || currentIndex === 0) return;
    const activeIdx = Math.max(0, currentIndex - 1);
    const candle = replayData.candles[activeIdx];
    if (!candle) return;

    let profit = 0;
    let total = 0;
    let wins = 0;
    let losses = 0;
    const activePosList: any[] = [];

    for (const t of agentTrades) {
      const entryTs = t.entry_time ?? 0;
      if (entryTs <= candle.time) {
        if (t.status === "Rejected" || t.type === "REJECTED" || t.type === "HOLD") {
          activePosList.push({
            ticket: t.ticket,
            type: t.type,
            lot_size: t.lot_size || 0.0,
            entry_price: t.entry_price,
            current_price: t.entry_price,
            sl: null,
            tp: null,
            original_sl: null,
            original_tp: null,
            status: "Rejected",
            pnl: 0,
            be_trigger_price: null,
            is_be_active: false,
            tp_trigger_price: null,
            is_tp_maxed: false,
            signal_type: t.signal_type,
            reject_reason: t.reject_reason,
            reject_detail: t.reject_detail,
            entry_time: t.entry_time,
          });
          continue;
        }
        total++;
        const typeLower = t.type.toLowerCase();
        const lotSize = t.lot_size;
        const entryPrice = t.entry_price;
        const slPrice = t.sl;
        const tpPrice = t.tp;

        // Check candles since entryTs up to current candle.time
        const activeCandles = (replayData?.candles ?? []).filter(c => c.time >= entryTs && c.time <= candle.time);
        
        let isClosed = false;
        let exitPrice = null;
        let exitTime = null;
        let tradeProfit = 0;

        for (const c of activeCandles) {
          // Force 24h Close
          if (force24hClose && (c.time - entryTs) >= 86400) {
            isClosed = true;
            exitPrice = c.close;
            exitTime = c.time;
            break;
          }

          if (typeLower === "buy") {
            if (slPrice !== null && c.low <= slPrice) {
              isClosed = true;
              exitPrice = slPrice;
              exitTime = c.time;
              break;
            }
            if (tpPrice !== null && c.high >= tpPrice) {
              isClosed = true;
              exitPrice = tpPrice;
              exitTime = c.time;
              break;
            }
          } else {
            if (slPrice !== null && c.high >= slPrice) {
              isClosed = true;
              exitPrice = slPrice;
              exitTime = c.time;
              break;
            }
            if (tpPrice !== null && c.low <= tpPrice) {
              isClosed = true;
              exitPrice = tpPrice;
              exitTime = c.time;
              break;
            }
          }
        }

        if (isClosed && exitTime !== null) {
          // Closed trade
          if (typeLower === "buy") {
            tradeProfit = ((exitPrice ?? entryPrice) - entryPrice) * lotSize * 100;
          } else {
            tradeProfit = (entryPrice - (exitPrice ?? entryPrice)) * lotSize * 100;
          }
          profit += tradeProfit;
          if (tradeProfit > 0) wins++;
          else losses++;

          // ponytail: keep closed trades in list with status flag, don't drop on close
          activePosList.push({
            ticket: t.ticket,
            type: t.type,
            lot_size: lotSize,
            entry_price: entryPrice,
            current_price: exitPrice ?? entryPrice,
            sl: slPrice,
            tp: tpPrice,
            original_sl: slPrice,
            original_tp: tpPrice,
            status: tradeProfit >= 0 ? "Closed - Win" : "Closed - Loss",
            pnl: tradeProfit,
            be_trigger_price: null,
            is_be_active: false,
            tp_trigger_price: null,
            is_tp_maxed: false,
            signal_type: t.signal_type,
            reject_reason: t.reject_reason,
            reject_detail: t.reject_detail,
            entry_time: t.entry_time,
          });
        } else {
          // Open trade (active position)
          const currentClose = candle.close;
          let floatingPnL = 0;
          if (typeLower === "buy") {
            floatingPnL = (currentClose - entryPrice) * lotSize * 100;
          } else {
            floatingPnL = (entryPrice - currentClose) * lotSize * 100;
          }
          profit += floatingPnL;

          activePosList.push({
            ticket: t.ticket,
            type: t.type,
            lot_size: lotSize,
            entry_price: entryPrice,
            current_price: currentClose,
            sl: slPrice,
            tp: tpPrice,
            original_sl: slPrice,
            original_tp: tpPrice,
            status: "Running",
            pnl: floatingPnL,
            be_trigger_price: null,
            is_be_active: false,
            tp_trigger_price: null,
            is_tp_maxed: false,
            signal_type: t.signal_type,
            reject_reason: t.reject_reason,
            reject_detail: t.reject_detail,
            entry_time: t.entry_time,
          });
        }
      }
    }

    setRunningProfit(profit);
    setTradeStats({ total, wins, losses });
    setActivePositions(activePosList);

    // Also update chart markers
    if (tradesPrimitiveRef.current) {
      tradesPrimitiveRef.current.setTimeframe(activeTimeframe);
      const mapped = agentTrades
        .filter(t => (t.entry_time ?? 0) <= candle.time)
        .map(t => {
          const entryTs = t.entry_time ?? 0;
          const typeLower = t.type.toLowerCase();
          const lotSize = t.lot_size;
          const entryPrice = t.entry_price;
          const slPrice = t.sl;
          const tpPrice = t.tp;

          // Check if closed at or before candle.time
          const activeCandles = (replayData?.candles ?? []).filter(c => c.time >= entryTs && c.time <= candle.time);
          let isClosed = false;
          let exitPrice = null;
          let exitTime = null;
          let finalProfit = 0;

          for (const c of activeCandles) {
            // Force 24h Close
            if (force24hClose && (c.time - entryTs) >= 86400) {
              isClosed = true;
              exitPrice = c.close;
              exitTime = c.time;
              break;
            }

            if (typeLower === "buy") {
              if (slPrice !== null && c.low <= slPrice) {
                isClosed = true;
                exitPrice = slPrice;
                exitTime = c.time;
                break;
              }
              if (tpPrice !== null && c.high >= tpPrice) {
                isClosed = true;
                exitPrice = tpPrice;
                exitTime = c.time;
                break;
              }
            } else {
              if (slPrice !== null && c.high >= slPrice) {
                isClosed = true;
                exitPrice = slPrice;
                exitTime = c.time;
                break;
              }
              if (tpPrice !== null && c.low <= tpPrice) {
                isClosed = true;
                exitPrice = tpPrice;
                exitTime = c.time;
                break;
              }
            }
          }

          if (isClosed && exitTime !== null) {
            if (typeLower === "buy") {
              finalProfit = ((exitPrice ?? entryPrice) - entryPrice) * lotSize * 100;
            } else {
              finalProfit = (entryPrice - (exitPrice ?? entryPrice)) * lotSize * 100;
            }
          }

          return {
            type: t.type,
            entry_price: entryPrice,
            sl: slPrice,
            tp: tpPrice,
            profit: finalProfit,
            entry_time_ts: entryTs,
            exit_time_ts: isClosed ? exitTime : null,
          };
        });
      tradesPrimitiveRef.current.setTrades(mapped);
    }
  }, [strategyParams, replayData, currentIndex, agentTrades, activeTimeframe, force24hClose, isPlaying]);



  // â”€â”€ Load Data â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  const handleLoad = useCallback(async () => {
    if (isPlaying) stopPlayback();
    setIsLoading(true);
    setLoadError(null);
    setCurrentIndex(0);
    setRunningProfit(0);
    setTradeStats({ total: 0, wins: 0, losses: 0 });
    setActivePositions([]);

    // Clear chart
    candleSeriesRef.current?.setData([]);
    emaSeriesRef.current?.setData([]);
    structurePrimitiveRef.current?.setLines([]);
    tradesPrimitiveRef.current?.setTrades([]);

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

      // Close the "Loading Replay Data" popup as soon as replay data is ready.
      // The orchestrator simulation below runs independently (see simLoading),
      // so a slow/large simulation must NOT block the popup from closing.
      setLoadProgress(prev => ({ ...prev, visible: false }));

      setSimFramesMap({});
      setActiveFrame(null);
      setIsFrameLoading(false);
      if (activeFrameAbortControllerRef.current) {
        activeFrameAbortControllerRef.current.abort();
        activeFrameAbortControllerRef.current = null;
      }
      setSimSignals([]);
      setAgentTrades([]);
      setSimMetrics(null);
      setSimFrames([]);
      setSimError(null);
    } catch (err: unknown) {
      clearInterval(interval);
      setLoadError(err instanceof Error ? err.message : "Gagal memuat data");
      setSimSignals([]);
      setAgentTrades([]);
      setSimMetrics(null);
      setSimFrames([]);
      setSimFramesMap({});
      setActiveFrame(null);
      setIsFrameLoading(false);
    } finally {
      setIsLoading(false);
      setLoadProgress(prev => ({ ...prev, visible: false }));
    }
  }, [yearFrom, monthFrom, yearTo, monthTo, isPlaying, activeTimeframe, orchestratorEnabled]);

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

  // â”€â”€ Advance one candle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    // Update structure markers â€” all events up to this candle
    const markers: any[] = [];
    for (const s of data.structures) {
      if (s.time <= candle.time) {
        const color = STRUCTURE_COLORS[s.type?.toUpperCase()] ?? "#94a3b8";
        const typeUpper = s.type?.toUpperCase() ?? "";
        const dirLower = s.direction?.toLowerCase() ?? "";

        // HH/LH â†’ at the high (aboveBar), HL/LL â†’ at the low (belowBar)
        // CHoCH/BOS â†’ bearish = aboveBar, bullish = belowBar
        let position: "aboveBar" | "belowBar";
        if (typeUpper === "HH" || typeUpper === "LH") {
          position = "aboveBar";
        } else if (typeUpper === "HL" || typeUpper === "LL") {
          position = "belowBar";
        } else {
          // CHoCH, BOS â€” use direction field
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

    // Orchestrator simulation signals
    for (const sig of simSignals) {
      if (sig.time <= candle.time) {
        const isBuy = sig.signal === "BUY";
        markers.push({
          time: sig.time as any,
          position: isBuy ? "belowBar" : "aboveBar",
          color: isBuy ? "#22c55e" : "#ef4444",
          shape: isBuy ? "arrowUp" : "arrowDown",
          text: sig.signal,
          size: 1,
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
    const formedStructures = data.structures.filter(s => s.time <= currentCandleTime);
    const visibleStructureEvents = selectSetupExtremeEvents(formedStructures);

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
        if (!visibleStructureEvents.has(s)) {
          continue;
        }

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

    // Update trades overlay
    if (tradesPrimitiveRef.current) {
      const entries: TradeOverlayEntry[] = agentTrades
        .filter(t => (t.entry_time ?? 0) <= candle.time)
        .map(t => {
          const entryTs = t.entry_time ?? 0;
          const typeLower = t.type.toLowerCase();
          const lotSize = t.lot_size;
          const entryPrice = t.entry_price;
          const slPrice = t.sl;
          const tpPrice = t.tp;

          // Check if closed at or before candle.time
          const activeCandles = (replayData?.candles ?? []).filter(c => c.time >= entryTs && c.time <= candle.time);
          let isClosed = false;
          let exitPrice = null;
          let exitTime = null;
          let finalProfit = 0;

          for (const c of activeCandles) {
            // Force 24h Close
            if (force24hClose && (c.time - entryTs) >= 86400) {
              isClosed = true;
              exitPrice = c.close;
              exitTime = c.time;
              break;
            }

            if (typeLower === "buy") {
              if (slPrice !== null && c.low <= slPrice) {
                isClosed = true;
                exitPrice = slPrice;
                exitTime = c.time;
                break;
              }
              if (tpPrice !== null && c.high >= tpPrice) {
                isClosed = true;
                exitPrice = tpPrice;
                exitTime = c.time;
                break;
              }
            } else {
              if (slPrice !== null && c.high >= slPrice) {
                isClosed = true;
                exitPrice = slPrice;
                exitTime = c.time;
                break;
              }
              if (tpPrice !== null && c.low <= tpPrice) {
                isClosed = true;
                exitPrice = tpPrice;
                exitTime = c.time;
                break;
              }
            }
          }

          if (isClosed && exitTime !== null) {
            if (typeLower === "buy") {
              finalProfit = ((exitPrice ?? entryPrice) - entryPrice) * lotSize * 100;
            } else {
              finalProfit = (entryPrice - (exitPrice ?? entryPrice)) * lotSize * 100;
            }
          }

          return {
            type: t.type,
            entry_price: entryPrice,
            sl: slPrice,
            tp: tpPrice,
            profit: finalProfit,
            entry_time_ts: entryTs,
            exit_time_ts: isClosed ? exitTime : null,
          };
        });
      tradesPrimitiveRef.current.setTrades(entries);
      tradesPrimitiveRef.current.setLastCandleTime(candle.time);
      tradesPrimitiveRef.current.setTimeframe(activeTimeframe);
    }

    // Track running trade stats
    let profit = 0;
    let total = 0;
    let wins = 0;
    let losses = 0;
    const activePosList: any[] = [];
    for (const t of agentTrades) {
      const entryTs = t.entry_time ?? 0;
      if (entryTs <= candle.time) {
        if (t.status === "Rejected" || t.type === "REJECTED" || t.type === "HOLD") {
          activePosList.push({
            ticket: t.ticket,
            type: t.type,
            lot_size: t.lot_size || 0.0,
            entry_price: t.entry_price,
            current_price: t.entry_price,
            sl: null,
            tp: null,
            original_sl: null,
            original_tp: null,
            status: "Rejected",
            pnl: 0,
            be_trigger_price: null,
            is_be_active: false,
            tp_trigger_price: null,
            is_tp_maxed: false,
            signal_type: t.signal_type,
            reject_reason: t.reject_reason,
            reject_detail: t.reject_detail,
            entry_time: t.entry_time,
          });
          continue;
        }
        total++;
        const typeLower = t.type.toLowerCase();
        const lotSize = t.lot_size;
        const entryPrice = t.entry_price;
        const slPrice = t.sl;
        const tpPrice = t.tp;

        // Check candles since entryTs up to current candle.time
        const activeCandles = (replayData?.candles ?? []).filter(c => c.time >= entryTs && c.time <= candle.time);
        
        let isClosed = false;
        let exitPrice = null;
        let exitTime = null;
        let tradeProfit = 0;

        for (const c of activeCandles) {
          if (typeLower === "buy") {
            if (slPrice !== null && c.low <= slPrice) {
              isClosed = true;
              exitPrice = slPrice;
              exitTime = c.time;
              break;
            }
            if (tpPrice !== null && c.high >= tpPrice) {
              isClosed = true;
              exitPrice = tpPrice;
              exitTime = c.time;
              break;
            }
          } else {
            if (slPrice !== null && c.high >= slPrice) {
              isClosed = true;
              exitPrice = slPrice;
              exitTime = c.time;
              break;
            }
            if (tpPrice !== null && c.low <= tpPrice) {
              isClosed = true;
              exitPrice = tpPrice;
              exitTime = c.time;
              break;
            }
          }
        }

        if (isClosed && exitTime !== null) {
          // Closed trade
          if (typeLower === "buy") {
            tradeProfit = ((exitPrice ?? entryPrice) - entryPrice) * lotSize * 100;
          } else {
            tradeProfit = (entryPrice - (exitPrice ?? entryPrice)) * lotSize * 100;
          }
          profit += tradeProfit;
          if (tradeProfit > 0) wins++;
          else losses++;

          // ponytail: keep closed trades in list with status flag, don't drop on close
          activePosList.push({
            ticket: t.ticket,
            type: t.type,
            lot_size: lotSize,
            entry_price: entryPrice,
            current_price: exitPrice ?? entryPrice,
            sl: slPrice,
            tp: tpPrice,
            original_sl: slPrice,
            original_tp: tpPrice,
            status: tradeProfit >= 0 ? "Closed - Win" : "Closed - Loss",
            pnl: tradeProfit,
            be_trigger_price: null,
            is_be_active: false,
            tp_trigger_price: null,
            is_tp_maxed: false,
            signal_type: t.signal_type,
            reject_reason: t.reject_reason,
            reject_detail: t.reject_detail,
            entry_time: t.entry_time,
          });
        } else {
          // Open trade (active position)
          const currentClose = candle.close;
          let floatingPnL = 0;
          if (typeLower === "buy") {
            floatingPnL = (currentClose - entryPrice) * lotSize * 100;
          } else {
            floatingPnL = (entryPrice - currentClose) * lotSize * 100;
          }
          profit += floatingPnL;

          activePosList.push({
            ticket: t.ticket,
            type: t.type,
            lot_size: lotSize,
            entry_price: entryPrice,
            current_price: currentClose,
            sl: slPrice,
            tp: tpPrice,
            original_sl: slPrice,
            original_tp: tpPrice,
            status: "Running",
            pnl: floatingPnL,
            be_trigger_price: null,
            is_be_active: false,
            tp_trigger_price: null,
            is_tp_maxed: false,
            signal_type: t.signal_type,
            reject_reason: t.reject_reason,
            reject_detail: t.reject_detail,
            entry_time: t.entry_time,
          });
        }
      }
    }
    setRunningProfit(profit);
    setTradeStats({ total, wins, losses });
    setActivePositions(activePosList);

    return idx + 1;
  }, [strategyParams, simSignals, agentTrades, replayData, force24hClose]);

  // â”€â”€ Playback controls (continued) â”€â”€

  const startPlayback = useCallback(() => {
    if (!replayData || currentIndex >= replayData.candles.length) return;
    setIsPlaying(true);

    let idx = currentIndex;
    timerRef.current = setInterval(() => {
      if (isFrameLoadingRef.current) return;
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

  // â”€â”€ Derived â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  const totalCandles = replayData?.candles.length ?? 0;
  const progress = totalCandles > 0 ? Math.round((currentIndex / totalCandles) * 100) : 0;
  const currentCandle = replayData?.candles[Math.max(0, currentIndex - 1)];

  // Fetch and update activeFrame dynamically
  useEffect(() => {
    if (!replayData || !currentCandle || !orchestratorEnabled) {
      setActiveFrame(null);
      return;
    }

    // Find the latest structure event that occurred at or before the current candle
    const triggerEvents = replayData.structures.filter(
      s => s.time <= currentCandle.time && ["CHOCH", "HH", "LL", "BOS"].includes(s.type.toUpperCase())
    );

    if (triggerEvents.length === 0) {
      setActiveFrame(null);
      return;
    }

    // The most recent event
    const latestEvent = triggerEvents[triggerEvents.length - 1];
    const latestType = latestEvent.type.toUpperCase();

    // Orchestrator triggers on CHOCH, BOS, or HH/LL that appear AFTER a CHoCH.
    const hasPriorChoch = triggerEvents.some(
      s => s.type.toUpperCase() === "CHOCH" && s.time < latestEvent.time
    );
    const isHHorLL = ["HH", "LL"].includes(latestType);
    const isChochOrBos = ["CHOCH", "BOS"].includes(latestType);
    const shouldTrigger = isChochOrBos || (isHHorLL && hasPriorChoch);

    if (!shouldTrigger) {
      // No valid trigger â€” clear frame only if it's stale
      if (activeFrame && activeFrame.event_time !== latestEvent.time) setActiveFrame(null);
      return;
    }

    // Find the most recent baseline event (CHOCH or BOS) in history before latestEvent
    let recentBaseline: string | null = null;
    let recentChochDir: string | null = null;
    for (let i = triggerEvents.length - 2; i >= 0; i--) {
      const ev = triggerEvents[i];
      const t = ev.type.toUpperCase();
      if (t.includes("CHOCH") || t.includes("BOS")) {
        recentBaseline = t.includes("CHOCH") ? "CHOCH" : "BOS";
        if (t.includes("CHOCH")) {
          recentChochDir = (t.includes("BULL") || (ev.direction && ev.direction.toUpperCase().includes("BULL"))) ? "BULLISH" : "BEARISH";
        }
        break;
      }
    }

    const isPostBos = recentBaseline === "BOS";
    const isSetupActive = recentBaseline === "CHOCH";
    const isCounterSwing = !isChochOrBos && (isPostBos || (isSetupActive && (
      ((latestType.includes("LL") || latestType.includes("BEAR")) && recentChochDir === "BULLISH") ||
      ((latestType.includes("HH") || latestType.includes("BULL")) && recentChochDir === "BEARISH")
    )));

    const cacheKey = `${latestEvent.time}_${latestEvent.type}`;

    if (isCounterSwing) {
      if (!simFramesMap[cacheKey]) {
        setSimFramesMap(prev => ({
          ...prev,
          [cacheKey]: { event_time: latestEvent.time, is_counter_swing: true } as any
        }));
      }
      return;
    }

    // Check Ref cache (synchronous) to avoid duplicate fetching during render races
    if (completedSimTimesRef.current.has(cacheKey)) {
      const cached = simFramesMap[cacheKey];
      if (cached && !cached.is_counter_swing && activeFrame !== cached) {
        setActiveFrame(cached);
      }
      return;
    }

    // Check cache
    if (simFramesMap[cacheKey]) {
      if (!simFramesMap[cacheKey].is_counter_swing) {
        setActiveFrame(simFramesMap[cacheKey]);
      }
      return;
    }

    // Not in cache, fetch it if it's the exact current candle time (so we trigger it exactly when it forms)
    // or if we just jumped to a new index and need the active frame
    if (latestEvent.time === currentCandle.time || !activeFrame || activeFrame.event_time !== latestEvent.time) {
      // Skip if already fetching this same event time
      if (pendingSimTimesRef.current.has(cacheKey)) return;
      // Drop if too many concurrent requests
      if (activeSimFetchesRef.current >= MAX_SIM_FETCHES) return;

      // Abort previous fetch
      if (activeFrameAbortControllerRef.current) {
        activeFrameAbortControllerRef.current.abort();
      }

      const controller = new AbortController();
      activeFrameAbortControllerRef.current = controller;
      setIsFrameLoading(true);
      activeSimFetchesRef.current += 1;
      pendingSimTimesRef.current.add(cacheKey);

      const url = `${BASE_URL}/trading/simulate-event?time=${latestEvent.time}&timeframe=${activeTimeframe}&type=${latestEvent.type}&veto_mode=${vetoMode}`;
      fetch(url, { signal: controller.signal })
        .then(res => {
          if (!res.ok) throw new Error("Failed to fetch event simulation");
          return res.json();
        })
        .then(frame => {
          completedSimTimesRef.current.add(cacheKey);
          setSimFramesMap(prev => ({ ...prev, [cacheKey]: frame }));
          // Counter-swing events (e.g. LL after Bullish CHoCH+HH, HH after Bearish CHoCH+LL)
          // should NOT update the Agent Consensus panel â€” keep warm-up values frozen.
          if (!frame?.is_counter_swing) {
            setActiveFrame(frame);
          }
          setIsFrameLoading(false);

          // Add marker and dynamic position when a new tradeable signal is approved by agent
          if (frame) {
            // Evaluate event cycle dynamically
            const cycleInfo = getEventCycleInfo(latestEvent, triggerEvents);
            let isEntryAllowed = false;
            if (cycleInfo.isChoch && allowChochEntry) {
              isEntryAllowed = true;
            } else if (cycleInfo.isBos) {
              if (cycleInfo.cycle === 1 && allowBosCycle1) {
                isEntryAllowed = true;
              } else if (cycleInfo.cycle === 2 && allowBosCycle2) {
                isEntryAllowed = true;
              } else if (cycleInfo.cycle >= 3 && allowBosCycle3Plus) {
                isEntryAllowed = true;
              }
            }

            const isApproved = frame.approved && ["BUY", "SELL"].includes(frame.final_signal) && isEntryAllowed;
            if (isApproved) {
              setSimSignals(prev => {
                if (prev.some(s => s.time === frame.event_time)) return prev;
                const next = [...prev, { time: frame.event_time, signal: frame.final_signal }];
                // ponytail: instant marker render â€” don't wait for next candle tick
                if (markersPluginRef.current) {
                  const existingMarkers: any[] = [];
                  for (const sig of next) {
                    existingMarkers.push({
                      time: sig.time as any,
                      position: sig.signal === "BUY" ? "belowBar" : "aboveBar",
                      color: sig.signal === "BUY" ? "#22c55e" : "#ef4444",
                      shape: sig.signal === "BUY" ? "arrowUp" : "arrowDown",
                      text: sig.signal,
                      size: 1,
                    });
                  }
                  markersPluginRef.current.setMarkers(existingMarkers);
                }
                return next;
              });

              setAgentTrades(prev => {
                if (prev.some(t => t.entry_time === frame.event_time)) return prev;
                const slVal = frame.sl_tp?.sl_price || null;
                const tpVal = frame.sl_tp?.tp_price || null;
                const lotVal = frame.position_sizing?.lot_size || 0.01;
                const entryVal = frame.sl_tp?.entry_price || frame.event_price || 0.0;
                
                return [...prev, {
                  ticket: prev.length + 1,
                  type: frame.final_signal,
                  entry_time: frame.event_time,
                  entry_price: entryVal,
                  sl: slVal,
                  tp: tpVal,
                  lot_size: lotVal,
                  exit_time: null,
                  exit_price: null,
                  net_profit: null,
                  is_agent_trade: true,
                  status: "Running",
                  signal_type: getSignalType(frame.event_type),
                  reject_reason: null,
                  reject_detail: null,
                }];
              });
            } else {
              // Only add Rejected position for the first BOS of a cycle (after CHoCH + HH/LL)
              // HH, LL, CHoCH and subsequent BOS events are not added to Daftar Posisi
              if (frame.is_first_bos) {
                setAgentTrades(prev => {
                  if (prev.some(t => t.entry_time === frame.event_time)) return prev;
                  const entryVal = frame.event_price || 0.0;
                  const typeVal = frame.final_signal || "HOLD";
                  const reject = getRejectReason(frame);

                  return [...prev, {
                    ticket: prev.length + 1,
                    type: typeVal,
                    entry_time: frame.event_time,
                    entry_price: entryVal,
                    sl: null,
                    tp: null,
                    lot_size: 0.0,
                    exit_time: frame.event_time,
                    exit_price: entryVal,
                    net_profit: 0,
                    is_agent_trade: true,
                    status: "Rejected",
                    signal_type: getSignalType(frame.event_type),
                    reject_reason: reject.label,
                    reject_detail: reject.detail,
                  }];
                });
              }
            }
          }
        })
        .catch(err => {
          if (err.name !== "AbortError") {
            console.error("Simulation event fetch error:", err);
            setIsFrameLoading(false);
          }
        })
        .finally(() => {
          activeSimFetchesRef.current -= 1;
          pendingSimTimesRef.current.delete(cacheKey);
        });
    }
  }, [currentCandle, replayData, activeTimeframe, simFramesMap, orchestratorEnabled, activeFrame, vetoMode]);

  // Keep selectedAgent in sync with activeFrame updates while the modal is open
  useEffect(() => {
    if (isAgentModalOpen && selectedAgent && activeFrame) {
      const currentAgentData = (activeFrame.agents as Record<string, any>)?.[selectedAgent.key];
      if (currentAgentData) {
        setSelectedAgent((prev: any) => {
          if (!prev) return prev;
          if (
            prev.reasoning === currentAgentData.reasoning && 
            prev.signal === currentAgentData.signal &&
            prev.confidence === currentAgentData.confidence
          ) {
            return prev;
          }
          return {
            ...prev,
            ...currentAgentData
          };
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFrame, isAgentModalOpen, selectedAgent?.key]);

  // â”€â”€ Render â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  return (
    <div
      className="flex flex-col size-full text-[var(--text-primary)]"
      style={{ background: "var(--bg-page)", paddingLeft: "var(--sidebar-offset, 250px)", transition: "padding-left 0.3s cubic-bezier(0.22, 1, 0.36, 1)", overflow: "hidden" }}
    >
      {/* â”€â”€ Header â”€â”€ */}
      <div
        className="relative z-30 flex items-center justify-between px-6 py-4 border-b backdrop-blur-md bg-[rgba(255,255,255,0.65)]"
        style={{ borderColor: "rgba(var(--neon-blue-rgb), 0.15)", boxShadow: "0 4px 30px rgba(0,0,0,0.2)" }}
      >
        <div className="flex items-center gap-4">
          <div className={cn("flex items-center justify-center w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.08] backdrop-blur-md hover:scale-105 transition-transform duration-200 ease-out shadow-[0_0_15px_rgba(var(--neon-cyan-rgb),0.15)] select-none", isPlaying && "animate-pulse")}>
            <Ghost size={26} aria-hidden="true" className="text-[var(--text-primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)] leading-none mb-1">
              Ghost Engine
            </h1>
            <p className="text-[var(--text-tertiary)] text-xs">
              Replay trades and validate strategy outcomes
            </p>
          </div>
        </div>

        {/* Filter controls + Playback Controls */}
        <div className="flex items-center gap-2 flex-wrap flex-1 justify-end ml-4 min-w-0">
          {/* If replayData is loaded, render playback controls FIRST! */}
          {replayData && (
            <>
              {/* Playback Control Deck */}
              <div className="inline-flex items-center gap-1.5 p-1 bg-[rgba(240,247,255,0.7)] border border-blue-200/80 rounded-xl shadow-[inset_0_1.5px_3px_rgba(0,0,0,0.8)]">
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
                <div className="inline-flex p-0.5 bg-[rgba(240,247,255,0.75)] border border-blue-200/70 rounded-lg overflow-hidden">
                  {(["1x", "2x", "3x", "5x", "10x"] as const).map((s) => (
                    <button
                      key={s}
                      onClick={() => setSpeed(s)}
                      className={cn(
                        "px-2.5 py-1 rounded-md text-xs font-mono transition-all duration-200 active:scale-95 cursor-pointer",
                        speed === s
                          ? "bg-[rgba(34,211,238,0.25)] text-[#22d3ee] border border-cyan-500/30"
                          : "text-slate-400 hover:text-white"
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
                    className={cn(
                      "h-full rounded-full bg-gradient-to-r from-cyan-400 to-purple-500 transition-all duration-300",
                      isPlaying && "animate-pulse shadow-[0_0_8px_rgba(34,211,238,0.4)]"
                    )}
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-[var(--text-secondary,#94a3b8)] min-w-[28px] text-right">
                  {progress}%
                </span>
              </div>

              {/* Vertical separator */}
              <div className="w-[1px] h-6 bg-[#BFDBFE]/70 self-center" />
            </>
          )}

          <div className="flex items-center gap-2">
            {/* Timeframe selector (tiru 100% dari page trades) */}
            <div className="flex items-center gap-2 mr-2">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-secondary,#94a3b8)]">Timeframe</span>
              <div className="inline-flex items-center gap-1 p-0.5 bg-sky-100/40 border border-sky-200/80 rounded-xl shadow-sm">
                {["M15", "H1", "H4"].map((tf) => (
                  <button
                    key={tf}
                    disabled={isLoading}
                    onClick={() => handleTimeframeChange(tf)}
                    className={cn(
                      "px-2.5 py-1 rounded-md text-xs font-bold transition-all duration-200 active:scale-95 cursor-pointer disabled:opacity-40",
                      tf === activeTimeframe
                        ? "bg-sky-600 text-white shadow-sm border border-sky-600"
                        : "text-slate-600 hover:text-slate-900 hover:bg-white/80"
                    )}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>

            <Calendar size={16} className="text-[var(--neon-blue,#38bdf8)] animate-pulse" />

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
              className="w-32"
            />

            <ArrowRight size={13} className="text-slate-400 mx-0.5" />

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
              className="w-32"
            />

            {/* Custom Switch Toggle "Run Orchestrator" */}
            <div className="flex items-center gap-2 mr-2">
              <button
                type="button"
                onClick={() => setOrchestratorEnabled(!orchestratorEnabled)}
                className={cn(
                  "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out outline-none focus:outline-none",
                  orchestratorEnabled ? "bg-cyan-500" : "bg-slate-700"
                )}
                style={{
                  boxShadow: orchestratorEnabled ? "0 0 10px rgba(6,182,212,0.4)" : "none"
                }}
              >
                <span
                  className={cn(
                    "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out",
                    orchestratorEnabled ? "translate-x-4" : "translate-x-0"
                  )}
                />
              </button>
              <span
                onClick={() => setOrchestratorEnabled(!orchestratorEnabled)}
                className="text-xs font-semibold text-[var(--text-secondary,#94a3b8)] cursor-pointer select-none hover:text-white transition-colors"
              >
                Run Orchestrator
              </span>
            </div>

            <button
              onClick={handleLoad}
              disabled={isLoading}
              className={cn(
                "inline-flex items-center justify-center px-3.5 py-1.5 rounded-lg text-xs font-bold cursor-pointer border transition-all duration-200 active:scale-95 outline-none shrink-0 shadow-sm",
                isLoading
                  ? "bg-slate-200 text-slate-500 border-slate-300 cursor-not-allowed opacity-70"
                  : "bg-sky-600 hover:bg-sky-700 text-white border-sky-600 shadow-[0_2px_8px_rgba(2,132,199,0.25)]"
              )}
            >
              {isLoading ? (
                <>
                  <Loader2 size={12} className="animate-spin mr-1.5" />
                  <span>Loading...</span>
                </>
              ) : (
                <span>Load</span>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* â”€â”€ Scrollable Body â”€â”€ */}
      <div className="flex-1 overflow-y-auto elegant-scrollbar px-6 py-4 flex flex-col gap-6">
        {/* â”€â”€ Stats Bar â”€â”€ */}
        {replayData && (
          <div
            className="flex items-center justify-between gap-4 px-5 py-2.5 border border-blue-200/80 rounded-xl bg-white/70 backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]"
          >
            <div className="flex items-center gap-4 flex-wrap">
              {/* Date Range */}
              <div className="flex flex-col">
                <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Rentang Tanggal</span>
                <span className="text-xs font-semibold text-slate-600">
                  {replayData.meta.date_from} â†’ {replayData.meta.date_to}
                </span>
              </div>

              <div className="w-px h-4 bg-[#BFDBFE]/70 self-center" />

              {/* Candles */}
              <div className="flex flex-col">
                <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Lilin (Candles)</span>
                <span className="text-xs font-semibold text-slate-600 font-mono">
                  <span className="text-cyan-400">{currentIndex}</span>/{totalCandles}
                </span>
              </div>

              <div className="w-px h-4 bg-[#BFDBFE]/70 self-center" />

              {/* PnL */}
              <div className="flex flex-col">
                <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Total P&L</span>
                <span className={cn(
                  "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-bold font-mono border",
                  runningProfit > 0
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : runningProfit < 0
                      ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                      : "bg-[#BFDBFE]/60 text-slate-400 border-blue-200/70"
                )}>
                  {runningProfit >= 0 ? "+" : ""}{runningProfit.toFixed(2)}
                </span>
              </div>

              <div className="w-px h-4 bg-[#BFDBFE]/70 self-center" />

              {/* Balance */}
              <div className="flex flex-col">
                <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Saldo (Balance)</span>
                <span className={cn(
                  "text-xs font-bold font-mono",
                  (INITIAL_BALANCE + runningProfit) >= INITIAL_BALANCE ? "text-emerald-400" : "text-rose-400"
                )}>
                  ${(INITIAL_BALANCE + runningProfit).toFixed(2)}
                </span>
              </div>

              <div className="w-px h-4 bg-[#BFDBFE]/70 self-center" />

              {/* Trades */}
              <div className="flex flex-col">
                <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Transaksi (Trades)</span>
                <span className="text-xs font-semibold text-slate-800 font-mono">
                  {tradeStats.total} <span className="text-slate-500 text-[10px] ml-1">({tradeStats.wins}W / {tradeStats.losses}L)</span>
                </span>
              </div>
            </div>

            {/* Current Playhead Time */}
            {currentCandle && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-purple-500/8 border border-purple-500/20 shadow-[0_0_10px_rgba(168,85,247,0.1)] text-xs font-semibold text-purple-300 font-mono">
                <Clock3 size={12} aria-hidden="true" />
                <span>{new Date(currentCandle.time * 1000).toISOString().slice(0, 16).replace("T", " ")}</span>
              </div>
            )}
          </div>
        )}

        {/* â”€â”€ Orchestrator Simulation â”€â”€ */}
        {simLoading && (
          <p className="text-sm text-[var(--text-secondary)] mt-2 flex items-center gap-1.5"><Loader2 size={14} className="animate-spin" aria-hidden="true" /> Running Orchestrator Simulationâ€¦</p>
        )}
        {simError && (
          <div className="mt-2 px-3 py-2 rounded-lg bg-red-900/30 border border-red-500/30 text-red-400 text-sm flex items-start gap-1.5">
            <AlertTriangle size={14} className="shrink-0 mt-0.5" aria-hidden="true" /> {simError}
          </div>
        )}
        {simMetrics && simMetrics.total_signals > 0 && (
          <div className="mt-3 p-3 rounded-lg bg-[rgba(59,130,246,0.08)] border border-[rgba(59,130,246,0.25)]">
            <p className="text-sm font-semibold text-[var(--neon-blue)] mb-2 flex items-center gap-1.5"><Brain size={14} aria-hidden="true" /> Orchestrator Simulation</p>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-[var(--text-secondary)]">
              <span>Total signals: <strong className="text-[var(--text-primary)]">{simMetrics.total_signals}</strong></span>
              <span>Win rate: <strong className="text-[var(--text-primary)]">{(simMetrics.win_rate * 100).toFixed(1)}%</strong></span>
              <span>BUY / SELL: <strong className="text-[var(--text-primary)]">{simMetrics.buy} / {simMetrics.sell}</strong></span>
              <span>Wins / Losses: <strong className="text-[var(--text-primary)]">{simMetrics.wins} / {simMetrics.losses}</strong></span>
              <span>Avg confidence: <strong className="text-[var(--text-primary)]">{(simMetrics.avg_confidence * 100).toFixed(1)}%</strong></span>
              <span>Agreement w/ backtest: <strong className="text-[var(--text-primary)]">{(simMetrics.agreement_rate * 100).toFixed(1)}%</strong></span>
            </div>
          </div>
        )}
        {simMetrics && simMetrics.total_signals === 0 && (
          <p className="text-sm text-[var(--text-secondary)] mt-2 flex items-center gap-1.5"><Brain size={14} aria-hidden="true" /> Orchestrator Simulation: No signals.</p>
        )}

        {/* â”€â”€ Error â”€â”€ */}
        {loadError && (
          <div className="px-4 py-3 rounded bg-red-900/30 border border-red-500/30 text-red-400 text-sm">
            {loadError}
          </div>
        )}

        {/* â”€â”€ Empty state â”€â”€ */}
        {!replayData && !loadError && (
          <div
            className="flex items-center justify-center flex-col gap-3 text-[var(--text-secondary,#94a3b8)] flex-shrink-0"
            style={{ height: "700px" }}
          >
            <Clapperboard size={44} strokeWidth={1.5} aria-hidden="true" className="opacity-70" />
            <p className="text-sm">Pilih rentang tanggal dan klik <strong>Load</strong> untuk memulai replay.</p>
          </div>
        )}

        {/* â”€â”€ Chart â”€â”€ */}
        <div className="relative px-4 pt-3 pb-0 flex-shrink-0" style={{ height: "700px", display: replayData ? "block" : "none" }}>
          {/* Floating Tooltip/Legend */}
          {hoveredInfo && (
            <div className="absolute top-6 left-8 z-10 bg-white/95 border border-blue-200/80 rounded px-3 py-1.5 text-[10px] font-mono flex items-center gap-3 text-slate-600 backdrop-blur-md pointer-events-none shadow-xl">
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
                  <span className="text-slate-800">{hoveredInfo.high.toFixed(2)}</span>
                </span>
              )}
              {hoveredInfo.low !== null && (
                <span className="flex items-center gap-0.5">
                  <span className="text-slate-500">L</span>
                  <span className="text-slate-800">{hoveredInfo.low.toFixed(2)}</span>
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
                <span className="border-l border-blue-200 pl-3 flex items-center gap-1">
                  <span className="text-cyan-400">PRICE</span>
                  <span className="text-cyan-300 font-bold">{hoveredInfo.hoveredPrice.toFixed(2)}</span>
                </span>
              )}
            </div>
          )}

          <div
            ref={chartContainerRef}
            className="w-full h-full rounded-lg overflow-hidden"
            style={{ background: "rgba(224,237,255,0.6)" }}
          />
        </div>

        {/* â”€â”€ Agent Consensus (100% Copy of Dashboard Layout, bound to activeFrame) â”€â”€ */}
        <div className="glass-card mt-4">
          <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
            <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: 0 }} className="flex items-center gap-2"><Bot size={18} aria-hidden="true" /> Agent Consensus</h2>
            {isFrameLoading && (
              <span className="text-xs text-cyan-400 animate-pulse flex items-center gap-1.5 bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded-full">
                <Loader2 className="size-3 animate-spin" />
                Calculating...
              </span>
            )}
          </div>

          {/* Always render the 4 agents panel directly */}
          <div className="flex flex-col gap-3">
            {AGENT_PANEL_DEFS.map((def) => {
              const agent = activeFrame?.agents?.[def.key] as SimAgentState | undefined;
              const prediction = agent?.signal || 'HOLD';
              const confidence = agent?.confidence ?? 0;
              const isActive = !!activeFrame && !!agent;

              return (
                <div
                  key={def.key}
                  className={cn(
                    "agent-row rounded-xl p-3 border transition-all duration-300 flex items-center justify-between",
                    isActive 
                      ? "hover:bg-[#BFDBFE]/50 cursor-pointer border-blue-200/70 bg-[#F0F6FF]/40" 
                      : "opacity-40 border-blue-200/40 bg-[#F0F6FF]/30 pointer-events-none select-none"
                  )}
                  onClick={() => {
                    if (!isActive || !agent) return;
                    setSelectedAgent({
                      key: def.key,
                      name: def.name,
                      icon: def.icon,
                      color: def.color,
                      bg: def.bg,
                      ...agent
                    });
                    setIsAgentModalOpen(true);
                  }}
                >
                  <div className="agent-info flex items-center gap-3">
                    <div 
                      className="agent-icon size-8 rounded-lg flex items-center justify-center border font-bold text-base" 
                      style={{ 
                        background: isActive ? def.bg : 'rgba(30, 41, 59, 0.1)', 
                        borderColor: isActive ? def.color : 'rgba(71, 85, 105, 0.2)' 
                      }}
                    >
                      {def.icon && <def.icon size={16} aria-hidden="true" />}
                    </div>
                    <div className="agent-details">
                      <div className="agent-name font-semibold text-xs text-slate-800">{def.name}</div>
                      <div className="agent-signal text-[10px] text-slate-500 mt-0.5">
                        Signal: <span className={cn("font-bold", isActive ? "neon-text text-cyan-400" : "text-slate-600")}>{prediction}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div style={{ minWidth: '100px' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>
                      Confidence
                    </div>
                    <div className="progress-bar h-1.5 w-[100px] bg-[#DBEAFE] rounded-full overflow-hidden">
                      <div 
                        className="progress-fill h-full rounded-full transition-all duration-300" 
                        style={{ 
                          width: `${Math.min(100, Math.max(0, confidence * 100))}%`,
                          backgroundColor: isActive ? def.color : '#334155'
                        }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Consensus Summary */}
          <div style={{ marginTop: '20px', padding: '16px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, fontSize: '12px' }} className="text-slate-600">Overall Consensus</span>
              <span className="text-sm font-bold transition-all duration-300" style={{ color: activeFrame ? 'var(--neon-amber)' : '#475569' }}>
                {activeFrame?.final_signal || 'HOLD'}
              </span>
            </div>
            <div className="progress-bar h-1.5 bg-[#DBEAFE] rounded-full overflow-hidden mt-3">
              <div
                className="progress-fill h-full rounded-full transition-all duration-300"
                style={{
                  width: `${Math.min(100, Math.max(0, (activeFrame?.consensus_confidence ?? 0) * 100))}%`,
                  background: activeFrame 
                    ? 'linear-gradient(90deg, var(--neon-amber), var(--neon-ruby))' 
                    : '#1e293b'
                }}
              />
            </div>
            <div className="text-[10px] text-[var(--text-tertiary)] mt-2">
              {activeFrame?.consensus_level
                ? `${activeFrame.consensus_level} (${Math.round((activeFrame.consensus_confidence ?? 0) * 100)}%)`
                : "Consensus Standby (Start replay to view)"}
            </div>
          </div>
        </div>

        {/* â”€â”€ Strategy Params Panel â”€â”€ */}
        {replayData && (
          <div
            className="rounded-xl p-5 border transition-all duration-300 flex-shrink-0"
            style={{
              background: "rgba(15, 23, 42, 0.45)",
              backdropFilter: "blur(16px)",
              WebkitBackdropFilter: "blur(16px)",
              borderColor: "rgba(255, 255, 255, 0.06)",
              boxShadow: "0 8px 32px 0 rgba(0, 0, 0, 0.37)"
            }}
          >
            <button
              onClick={() => setIsStrategyPanelOpen(p => !p)}
              className="w-full flex items-center justify-between text-base font-bold text-slate-900 hover:text-white transition-colors focus:outline-none cursor-pointer"
            >
              <div className="flex items-center gap-2.5">
                <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/25">
                  <Settings size={14} aria-hidden="true" />
                </span>
                <span>Strategy Settings & Parameters</span>
              </div>
              <span className="text-slate-400 text-xs font-semibold px-2 py-1 rounded bg-[#DBEAFE]/60 border border-blue-200/80">
                {isStrategyPanelOpen ? "Tutup Panel â–²" : "Buka Panel â–¼"}
              </span>
            </button>

            {isStrategyPanelOpen && (
              <div className="mt-5 space-y-6">
                {/* Emil Kowalski style overrides block for layout hover glows */}
                <style>{`
                  .filter-card {
                    transition: border-color 200ms ease-out, background-color 200ms ease-out !important;
                  }
                  .filter-card:hover {
                    border-color: rgba(6, 182, 212, 0.2) !important;
                    background-color: rgba(255, 255, 255, 0.03) !important;
                  }
                  .premium-switch-bullet {
                    transition: width 150ms cubic-bezier(0.23, 1, 0.32, 1) !important;
                  }
                  .premium-switch:active .premium-switch-bullet {
                    width: 24px !important;
                  }
                `}</style>

                {/* Section C & D Consolidated: Strategy Settings Split Layout */}
                <div className="p-5 rounded-xl bg-[#F0F6FF]/70 border border-blue-200/60">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    
                    {/* Left Column: Trend & Cycle Schema Map */}
                    <div className="space-y-4">
                      <div className="flex items-center gap-1.5 border-b border-blue-200/50 pb-2">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider select-none inline-flex items-center gap-1"><Target size={11} aria-hidden="true" /> Trend &amp; Cycle Schema Map</span>
                      </div>
                      
                      <MarketStructure3DVisualizer
                        allowChoch={allowChochEntry}
                        allowBos1={allowBosCycle1}
                        allowBos2={allowBosCycle2}
                        allowBos3Plus={allowBosCycle3Plus}
                      />

                      {/* Toggle Filters List */}
                      <div className="flex flex-col divide-y divide-blue-200/50 text-xs border-t border-blue-200/50">
                        {/* CHoCH Toggle */}
                        <div className="flex items-center justify-between py-3 filter-card px-1">
                          <div className="flex flex-col gap-0.5">
                            <span className="font-semibold text-slate-800">CHoCH Entries</span>
                            <span className="text-[10px] text-slate-500">Change of Character patterns</span>
                          </div>
                          <motion.button
                            whileTap={{ scale: 0.94 }}
                            onClick={() => setAllowChochEntry(p => !p)}
                            className={cn(
                              "w-11 h-6 rounded-full p-[2.5px] focus:outline-none cursor-pointer premium-switch relative flex items-center bg-[#DBEAFE] border transition-colors duration-300",
                              allowChochEntry ? "border-cyan-500/30" : "border-blue-200/70"
                            )}
                          >
                            <motion.div 
                              className="absolute inset-0 bg-cyan-500/10 pointer-events-none rounded-full"
                              initial={false}
                              animate={{ opacity: allowChochEntry ? 1 : 0 }}
                              transition={{ duration: 0.25 }}
                            />
                            <motion.div
                              className="w-4 h-4 rounded-full premium-switch-bullet shadow-[0_1.5px_3px_rgba(0,0,0,0.5)]"
                              transition={{
                                type: "spring",
                                stiffness: 500,
                                damping: 30,
                                mass: 0.8
                              }}
                              animate={{
                                x: allowChochEntry ? 20 : 0,
                                backgroundColor: allowChochEntry ? "#06b6d4" : "#475569",
                                boxShadow: allowChochEntry ? "0 0 8px rgba(6, 182, 212, 0.6)" : "none",
                              }}
                            />
                          </motion.button>
                        </div>

                        {/* Cycle 1 Toggle */}
                        <div className="flex items-center justify-between py-3 filter-card px-1">
                          <div className="flex flex-col gap-0.5">
                            <span className="font-semibold text-slate-800">BOS Cycle 1 Entries</span>
                            <span className="text-[10px] text-slate-500">First BOS after CHoCH</span>
                          </div>
                          <motion.button
                            whileTap={{ scale: 0.94 }}
                            onClick={() => setAllowBosCycle1(p => !p)}
                            className={cn(
                              "w-11 h-6 rounded-full p-[2.5px] focus:outline-none cursor-pointer premium-switch relative flex items-center bg-[#DBEAFE] border transition-colors duration-300",
                              allowBosCycle1 ? "border-cyan-500/30" : "border-blue-200/70"
                            )}
                          >
                            <motion.div 
                              className="absolute inset-0 bg-cyan-500/10 pointer-events-none rounded-full"
                              initial={false}
                              animate={{ opacity: allowBosCycle1 ? 1 : 0 }}
                              transition={{ duration: 0.25 }}
                            />
                            <motion.div
                              className="w-4 h-4 rounded-full premium-switch-bullet shadow-[0_1.5px_3px_rgba(0,0,0,0.5)]"
                              transition={{
                                type: "spring",
                                stiffness: 500,
                                damping: 30,
                                mass: 0.8
                              }}
                              animate={{
                                x: allowBosCycle1 ? 20 : 0,
                                backgroundColor: allowBosCycle1 ? "#06b6d4" : "#475569",
                                boxShadow: allowBosCycle1 ? "0 0 8px rgba(6, 182, 212, 0.6)" : "none",
                              }}
                            />
                          </motion.button>
                        </div>

                        {/* Cycle 2 Toggle */}
                        <div className="flex items-center justify-between py-3 filter-card px-1">
                          <div className="flex flex-col gap-0.5">
                            <span className="font-semibold text-slate-800">BOS Cycle 2 Entries</span>
                            <span className="text-[10px] text-slate-500">Second BOS after CHoCH</span>
                          </div>
                          <motion.button
                            whileTap={{ scale: 0.94 }}
                            onClick={() => setAllowBosCycle2(p => !p)}
                            className={cn(
                              "w-11 h-6 rounded-full p-[2.5px] focus:outline-none cursor-pointer premium-switch relative flex items-center bg-[#DBEAFE] border transition-colors duration-300",
                              allowBosCycle2 ? "border-cyan-500/30" : "border-blue-200/70"
                            )}
                          >
                            <motion.div 
                              className="absolute inset-0 bg-cyan-500/10 pointer-events-none rounded-full"
                              initial={false}
                              animate={{ opacity: allowBosCycle2 ? 1 : 0 }}
                              transition={{ duration: 0.25 }}
                            />
                            <motion.div
                              className="w-4 h-4 rounded-full premium-switch-bullet shadow-[0_1.5px_3px_rgba(0,0,0,0.5)]"
                              transition={{
                                type: "spring",
                                stiffness: 500,
                                damping: 30,
                                mass: 0.8
                              }}
                              animate={{
                                x: allowBosCycle2 ? 20 : 0,
                                backgroundColor: allowBosCycle2 ? "#06b6d4" : "#475569",
                                boxShadow: allowBosCycle2 ? "0 0 8px rgba(6, 182, 212, 0.6)" : "none",
                              }}
                            />
                          </motion.button>
                        </div>

                        {/* Cycle 3+ Toggle */}
                        <div className="flex items-center justify-between py-3 filter-card px-1">
                          <div className="flex flex-col gap-0.5">
                            <span className="font-semibold text-slate-800">BOS Cycle 3+ Entries</span>
                            <span className="text-[10px] text-slate-500">Subsequent BOS cycles</span>
                          </div>
                          <motion.button
                            whileTap={{ scale: 0.94 }}
                            onClick={() => setAllowBosCycle3Plus(p => !p)}
                            className={cn(
                              "w-11 h-6 rounded-full p-[2.5px] focus:outline-none cursor-pointer premium-switch relative flex items-center bg-[#DBEAFE] border transition-colors duration-300",
                              allowBosCycle3Plus ? "border-cyan-500/30" : "border-blue-200/70"
                            )}
                          >
                            <motion.div 
                              className="absolute inset-0 bg-cyan-500/10 pointer-events-none rounded-full"
                              initial={false}
                              animate={{ opacity: allowBosCycle3Plus ? 1 : 0 }}
                              transition={{ duration: 0.25 }}
                            />
                            <motion.div
                              className="w-4 h-4 rounded-full premium-switch-bullet shadow-[0_1.5px_3px_rgba(0,0,0,0.5)]"
                              transition={{
                                type: "spring",
                                stiffness: 500,
                                damping: 30,
                                mass: 0.8
                              }}
                              animate={{
                                x: allowBosCycle3Plus ? 20 : 0,
                                backgroundColor: allowBosCycle3Plus ? "#06b6d4" : "#475569",
                                boxShadow: allowBosCycle3Plus ? "0 0 8px rgba(6, 182, 212, 0.6)" : "none",
                              }}
                            />
                          </motion.button>
                        </div>

                        {/* Force 24h Close Toggle */}
                        <div className="flex items-center justify-between py-3 filter-card px-1 border-t border-blue-200/50">
                          <div className="flex flex-col gap-0.5">
                            <span className="font-semibold text-slate-800">Force 24h Close</span>
                            <span className="text-[10px] text-slate-500">Automatically close any open trades after 24 hours</span>
                          </div>
                          <motion.button
                            whileTap={{ scale: 0.94 }}
                            onClick={() => setForce24hClose(p => !p)}
                            className={cn(
                              "w-11 h-6 rounded-full p-[2.5px] focus:outline-none cursor-pointer premium-switch relative flex items-center bg-[#DBEAFE] border transition-colors duration-300",
                              force24hClose ? "border-cyan-500/30" : "border-blue-200/70"
                            )}
                          >
                            <motion.div 
                              className="absolute inset-0 bg-cyan-500/10 pointer-events-none rounded-full"
                              initial={false}
                              animate={{ opacity: force24hClose ? 1 : 0 }}
                              transition={{ duration: 0.25 }}
                            />
                            <motion.div
                              className="w-4 h-4 rounded-full premium-switch-bullet shadow-[0_1.5px_3px_rgba(0,0,0,0.5)]"
                              transition={{
                                type: "spring",
                                stiffness: 500,
                                damping: 30,
                                mass: 0.8
                              }}
                              animate={{
                                x: force24hClose ? 20 : 0,
                                backgroundColor: force24hClose ? "#06b6d4" : "#475569",
                                boxShadow: force24hClose ? "0 0 8px rgba(6, 182, 212, 0.6)" : "none",
                              }}
                            />
                          </motion.button>
                        </div>
                      </div>
                    </div>

                    {/* Right Column: Veto Mode & Consensus Map */}
                    <div className="space-y-4">
                      <div className="flex items-center gap-1.5 border-b border-blue-200/50 pb-2">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider select-none flex items-center gap-1">
                          <Shield size={13} className="inline shrink-0" aria-hidden="true" /> Veto Mode &amp; Consensus Map
                          <StrategyTooltip fungsi="Menentukan tingkat toleransi terhadap Veto dari Market Structure Agent saat H1/H4 EMA tidak selaras." contoh="Hard Veto -> Menolak sepenuhnya (HOLD). Soft Veto -> Meloloskan jika ML Expected R:R &gt;= 1.35. No Veto -> Mengikuti voting demokratis." />
                        </span>
                      </div>

                      <VetoConsensus3DVisualizer vetoMode={vetoMode} />

                      {/* Veto Radio-Toggles List */}
                      <div className="flex flex-col divide-y divide-blue-200/50 text-xs border-t border-blue-200/50">
                        {/* Hard Veto Toggle */}
                        <div className="flex items-center justify-between py-3 filter-card px-1">
                          <div className="flex flex-col gap-0.5">
                            <span className="font-semibold text-slate-800">Hard Veto (Default)</span>
                            <span className="text-[10px] text-slate-500">Menolak sepenuhnya sinyal jika EMA H1/H4 tidak selaras</span>
                          </div>
                          <motion.button
                            whileTap={{ scale: 0.94 }}
                            onClick={() => setVetoMode("hard")}
                            className={cn(
                              "w-11 h-6 rounded-full p-[2.5px] focus:outline-none cursor-pointer premium-switch relative flex items-center bg-[#DBEAFE] border transition-colors duration-300",
                              vetoMode === "hard" ? "border-cyan-500/30" : "border-blue-200/70"
                            )}
                          >
                            <motion.div 
                              className="absolute inset-0 bg-cyan-500/10 pointer-events-none rounded-full"
                              initial={false}
                              animate={{ opacity: vetoMode === "hard" ? 1 : 0 }}
                              transition={{ duration: 0.25 }}
                            />
                            <motion.div
                              className="w-4 h-4 rounded-full premium-switch-bullet shadow-[0_1.5px_3px_rgba(0,0,0,0.5)]"
                              transition={{
                                type: "spring",
                                stiffness: 500,
                                damping: 30,
                                mass: 0.8
                              }}
                              animate={{
                                x: vetoMode === "hard" ? 20 : 0,
                                backgroundColor: vetoMode === "hard" ? "#06b6d4" : "#475569",
                                boxShadow: vetoMode === "hard" ? "0 0 8px rgba(6, 182, 212, 0.6)" : "none",
                              }}
                            />
                          </motion.button>
                        </div>

                        {/* Soft Veto Toggle */}
                        <div className="flex items-center justify-between py-3 filter-card px-1">
                          <div className="flex flex-col gap-0.5">
                            <span className="font-semibold text-slate-800">Soft Veto (Conditional)</span>
                            <span className="text-[10px] text-slate-500">Meloloskan jika rasio ML Expected R:R &gt;= 1.35</span>
                          </div>
                          <motion.button
                            whileTap={{ scale: 0.94 }}
                            onClick={() => setVetoMode("soft")}
                            className={cn(
                              "w-11 h-6 rounded-full p-[2.5px] focus:outline-none cursor-pointer premium-switch relative flex items-center bg-[#DBEAFE] border transition-colors duration-300",
                              vetoMode === "soft" ? "border-cyan-500/30" : "border-blue-200/70"
                            )}
                          >
                            <motion.div 
                              className="absolute inset-0 bg-cyan-500/10 pointer-events-none rounded-full"
                              initial={false}
                              animate={{ opacity: vetoMode === "soft" ? 1 : 0 }}
                              transition={{ duration: 0.25 }}
                            />
                            <motion.div
                              className="w-4 h-4 rounded-full premium-switch-bullet shadow-[0_1.5px_3px_rgba(0,0,0,0.5)]"
                              transition={{
                                type: "spring",
                                stiffness: 500,
                                damping: 30,
                                mass: 0.8
                              }}
                              animate={{
                                x: vetoMode === "soft" ? 20 : 0,
                                backgroundColor: vetoMode === "soft" ? "#06b6d4" : "#475569",
                                boxShadow: vetoMode === "soft" ? "0 0 8px rgba(6, 182, 212, 0.6)" : "none",
                              }}
                            />
                          </motion.button>
                        </div>

                        {/* No Veto Toggle */}
                        <div className="flex items-center justify-between py-3 filter-card px-1">
                          <div className="flex flex-col gap-0.5">
                            <span className="font-semibold text-slate-800">No Veto (Democratic)</span>
                            <span className="text-[10px] text-slate-500">Mengikuti keputusan voting mayoritas konsensus agen</span>
                          </div>
                          <motion.button
                            whileTap={{ scale: 0.94 }}
                            onClick={() => setVetoMode("none")}
                            className={cn(
                              "w-11 h-6 rounded-full p-[2.5px] focus:outline-none cursor-pointer premium-switch relative flex items-center bg-[#DBEAFE] border transition-colors duration-300",
                              vetoMode === "none" ? "border-cyan-500/30" : "border-blue-200/70"
                            )}
                          >
                            <motion.div 
                              className="absolute inset-0 bg-cyan-500/10 pointer-events-none rounded-full"
                              initial={false}
                              animate={{ opacity: vetoMode === "none" ? 1 : 0 }}
                              transition={{ duration: 0.25 }}
                            />
                            <motion.div
                              className="w-4 h-4 rounded-full premium-switch-bullet shadow-[0_1.5px_3px_rgba(0,0,0,0.5)]"
                              transition={{
                                type: "spring",
                                stiffness: 500,
                                damping: 30,
                                mass: 0.8
                              }}
                              animate={{
                                x: vetoMode === "none" ? 20 : 0,
                                backgroundColor: vetoMode === "none" ? "#06b6d4" : "#475569",
                                boxShadow: vetoMode === "none" ? "0 0 8px rgba(6, 182, 212, 0.6)" : "none",
                              }}
                            />
                          </motion.button>
                        </div>
                      </div>
                    </div>

                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* â”€â”€ Active Positions Panel â”€â”€ */}
        {replayData && (
          <div className="glass-card flex-shrink-0">
            <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-600 inline-block shadow-sm"></span>
              <Zap size={15} className="inline shrink-0 text-sky-600" aria-hidden="true" /> Daftar Posisi
              {activePositions.length > 0 && (
                <span className="ml-auto text-xs font-medium text-slate-600">
                  <span className="text-sky-700 font-bold">{activePositions.filter(p => !p.is_closed && !p.is_rejected).length}</span> aktif
                  {" • "}
                  <span className="text-slate-700 font-bold">{activePositions.filter(p => p.is_closed).length}</span> closed
                  {" • "}
                  <span className="text-rose-700 font-bold">{activePositions.filter(p => p.is_rejected).length}</span> rejected
                </span>
              )}
            </h2>

            {activePositions.length === 0 ? (
              <div className="py-8 text-center text-slate-600 font-medium text-sm bg-sky-50/50 rounded-lg border border-sky-200/80">
                Tidak ada posisi saat ini
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-sky-200/80 shadow-sm">
                <table className="min-w-full divide-y divide-sky-100 bg-white">
                  <thead className="bg-sky-100/70 text-sky-950 text-[11px] font-bold tracking-wider uppercase border-b border-sky-200">
                    <tr>
                      <th className="py-3 px-4 text-left">Ticket</th>
                      <th className="py-3 px-4 text-left">Signal Type</th>
                      <th className="py-3 px-4 text-left">Type</th>
                      <th className="py-3 px-4 text-right">Lot</th>
                      <th className="py-3 px-4 text-right">Entry Price</th>
                      <th className="py-3 px-4 text-right">Current Price</th>
                      <th className="py-3 px-4 text-right">SL (Orig → Curr)</th>
                      <th className="py-3 px-4 text-right">TP (Orig → Curr)</th>
                      <th className="py-3 px-4 text-left">Triggers (BE | TP-Ex)</th>
                      <th className="py-3 px-4 text-center">Status</th>
                      <th className="py-3 px-4 text-right">Floating PnL</th>
                      <th className="py-3 px-4 text-left">Reject Reason</th>
                      <th className="py-3 px-4 text-left">Entry Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-sky-100 text-slate-900 text-xs font-medium">
                    {[...activePositions]
                      .sort((a, b) => (b.entry_time ?? 0) - (a.entry_time ?? 0))
                      .map((pos) => {
                      const isWin = pos.pnl >= 0;
                      const isBuy = pos.type === "BUY";
                      const isClosed = pos.is_closed === true;
                      const isRejected = pos.is_rejected === true;

                      const hasSLChanged = pos.sl && pos.original_sl && Math.abs(pos.sl - pos.original_sl) > 0.01;
                      const hasTPChanged = pos.tp && pos.original_tp && Math.abs(pos.tp - pos.original_tp) > 0.01;

                      // Status Badge Classes
                      let badgeClass = "bg-slate-100 text-slate-700 border border-slate-300 font-bold";
                      if (isRejected) {
                        badgeClass = "bg-rose-100 text-rose-800 border border-rose-300 font-bold";
                      } else if (isClosed) {
                        badgeClass = isWin
                          ? "bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold"
                          : "bg-rose-100 text-rose-800 border border-rose-300 font-bold";
                      } else if (pos.status === "BE + TP Expanded") {
                        badgeClass = "bg-fuchsia-100 text-fuchsia-800 border border-fuchsia-300 font-bold shadow-xs";
                      } else if (pos.status === "Break-Even") {
                        badgeClass = "bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold shadow-xs";
                      } else if (pos.status === "TP Expanded") {
                        badgeClass = "bg-amber-100 text-amber-900 border border-amber-300 font-bold shadow-xs";
                      } else if (pos.status === "Trailing") {
                        badgeClass = "bg-sky-100 text-sky-900 border border-sky-300 font-bold shadow-xs";
                      }

                      let rowBg = "hover:bg-sky-50/70 transition-colors";
                      if (isRejected) {
                        rowBg = "bg-slate-50/80 hover:bg-slate-100/80 text-slate-500";
                      } else if (isClosed) {
                        rowBg = isWin ? "bg-emerald-50/30 hover:bg-emerald-50/60" : "bg-rose-50/30 hover:bg-rose-50/60";
                      } else {
                        rowBg = isBuy ? "bg-emerald-50/40 hover:bg-emerald-50/80" : "bg-rose-50/40 hover:bg-rose-50/80";
                      }

                      return (
                        <tr key={pos.ticket} className={rowBg}>
                          <td className="py-3.5 px-4 font-mono font-bold text-slate-700">#{pos.ticket}</td>
                          <td className="py-3.5 px-4">
                            <span className={cn(
                              "inline-block px-2 py-0.5 rounded text-[10px] font-bold tracking-wider border",
                              pos.signal_type === "CHOCH"
                                ? "bg-purple-100 text-purple-800 border-purple-300"
                                : pos.signal_type === "BOS"
                                ? "bg-amber-100 text-amber-900 border-amber-300"
                                : "bg-slate-100 text-slate-700 border-slate-300"
                            )}>
                              {pos.signal_type || "-"}
                            </span>
                          </td>
                          <td className="py-3.5 px-4">
                            <span className={cn(
                              "inline-block px-2.5 py-0.5 rounded text-[10px] font-bold tracking-wider border shadow-xs",
                              isBuy
                                ? "bg-emerald-100 text-emerald-800 border-emerald-300"
                                : "bg-rose-100 text-rose-800 border-rose-300"
                            )}>
                              {pos.type}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-900">{pos.lot_size.toFixed(2)}</td>
                          <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-900">${pos.entry_price.toFixed(2)}</td>
                          <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-900">${pos.current_price.toFixed(2)}</td>
                          <td className="py-3.5 px-4 text-right font-mono">
                            {hasSLChanged ? (
                              <span className="flex items-center justify-end gap-1.5">
                                <span className="text-slate-500 line-through">${pos.original_sl.toFixed(2)}</span>
                                <ArrowRight size={10} className="text-slate-400" />
                                <span className="text-rose-700 font-bold">${pos.sl.toFixed(2)}</span>
                              </span>
                            ) : (
                              <span className="text-slate-600 font-medium">${pos.original_sl ? pos.original_sl.toFixed(2) : "-"}</span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono">
                            {hasTPChanged ? (
                              <span className="flex items-center justify-end gap-1.5">
                                <span className="text-slate-500 line-through">${pos.original_tp.toFixed(2)}</span>
                                <ArrowRight size={10} className="text-slate-400" />
                                <span className="text-emerald-700 font-bold">${pos.tp.toFixed(2)}</span>
                              </span>
                            ) : (
                              <span className="text-slate-600 font-medium">${pos.original_tp ? pos.original_tp.toFixed(2) : "-"}</span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-left font-mono text-[10px] space-y-0.5">
                            <div className="flex items-center gap-1.5">
                              <span className="text-slate-500 font-semibold">BE:</span>
                              {pos.be_trigger_price == null ? (
                                <span className="text-slate-400">-</span>
                              ) : pos.is_be_active ? (
                                <span className="px-1.5 py-0.2 bg-emerald-100 text-emerald-800 border border-emerald-300 rounded font-bold">Active</span>
                              ) : (
                                <span className="text-slate-700 font-medium">${pos.be_trigger_price.toFixed(2)}</span>
                              )}
                            </div>
                            <div className="flex items-center gap-1.5">
                              <span className="text-slate-500 font-semibold">TP-Ex:</span>
                              {pos.is_tp_maxed ? (
                                <span className="px-1.5 py-0.2 bg-rose-100 text-rose-800 border border-rose-300 rounded font-bold text-[9px]">Maxed</span>
                              ) : pos.tp_trigger_price == null ? (
                                <span className="text-slate-400">-</span>
                              ) : (
                                <span className="text-sky-800 font-bold">${pos.tp_trigger_price.toFixed(2)}</span>
                              )}
                            </div>
                          </td>
                          <td className="py-3.5 px-4 text-center">
                            <span className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold transition-all duration-300 ${badgeClass}`}>
                              {pos.status}
                            </span>
                          </td>
                          <td className={cn(
                            "py-3.5 px-4 text-right font-mono font-bold text-sm",
                            isRejected ? "text-slate-500" : isWin ? "text-emerald-700" : "text-rose-700"
                          )}>
                            {isWin && !isRejected ? "+" : ""}${pos.pnl.toFixed(2)}
                          </td>
                          <td className="py-3.5 px-4 text-left">
                            {pos.reject_reason ? (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-300 cursor-help">
                                    {pos.reject_reason}
                                  </span>
                                </TooltipTrigger>
                                <TooltipContent
                                  side="top"
                                  sideOffset={8}
                                  className="max-w-xs border border-rose-300 bg-white text-slate-900 shadow-md backdrop-blur-md"
                                >
                                  <div className="space-y-1.5">
                                    <div className="flex items-center gap-1.5">
                                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-rose-600 shadow-sm" />
                                      <span className="text-[10px] font-bold uppercase tracking-wider text-rose-700">
                                        {pos.reject_reason}
                                      </span>
                                    </div>
                                    <p className="text-[11px] leading-relaxed text-slate-700 font-medium">
                                      {pos.reject_detail || pos.reject_reason}
                                    </p>
                                  </div>
                                </TooltipContent>
                              </Tooltip>
                            ) : (
                              <span className="text-slate-400">-</span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-left font-mono text-xs text-slate-600 font-medium whitespace-nowrap">
                            {pos.entry_time ? new Date(pos.entry_time * 1000).toLocaleString("en-GB", {
                              day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
                            }) : "-"}
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

        {/* â”€â”€ Monthly Summary Section (100% Identical to trades.tsx) â”€â”€ */}
        <div className="glass-card mt-2 flex-shrink-0">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <h2 className="text-xl font-semibold inline-flex items-center gap-2"><ClipboardList size={18} aria-hidden="true" /> Monthly Performance Summary</h2>

            {/* Filter Controls */}
            <div className="flex flex-wrap items-center gap-3">
              {/* Year Select Dropdown */}
              <div className="relative">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 font-medium">Tahun:</span>
                  <button
                    onClick={() => setIsYearDropdownOpen((prev) => !prev)}
                    className="flex items-center justify-between gap-2 bg-sky-50 hover:bg-sky-100 border border-sky-300/80 text-sky-950 rounded-lg px-3 py-1.5 text-xs font-bold focus:outline-none transition-all cursor-pointer shadow-sm min-w-[75px]"
                  >
                    <span>{monthlySummaryYearFilter}</span>
                    <ChevronDown size={13} className={`text-sky-600 transition-transform duration-200 ${isYearDropdownOpen ? "rotate-180" : ""}`} />
                  </button>
                </div>

                {isYearDropdownOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setIsYearDropdownOpen(false)}
                    />
                    <div className="absolute right-0 mt-1.5 w-24 bg-white/95 border border-sky-200 rounded-lg shadow-xl backdrop-blur-xl z-50 overflow-hidden py-1">
                      {availableYears.map((year) => (
                        <button
                          key={year}
                          onClick={() => {
                            setMonthlySummaryYearFilter(year);
                            setIsYearDropdownOpen(false);
                          }}
                          className={`w-full text-left px-3 py-2 text-xs transition-colors hover:bg-sky-50 hover:text-sky-900 font-semibold cursor-pointer ${monthlySummaryYearFilter === year ? "text-sky-700 bg-sky-100/80" : "text-slate-700"
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
              <div className="flex bg-sky-100/40 p-1 rounded-lg border border-sky-200/80 backdrop-blur-md shadow-sm gap-1">
                {(["all", "profit", "loss"] as const).map((perfFilter) => (
                  <button
                    key={perfFilter}
                    onClick={() => setMonthlySummaryPerformanceFilter(perfFilter)}
                    className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all cursor-pointer ${monthlySummaryPerformanceFilter === perfFilter
                      ? "bg-sky-600 text-white shadow-sm"
                      : "text-slate-600 hover:text-slate-900 hover:bg-white/80"
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
              <thead className="bg-white/60 border-b border-blue-200/70">
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
                      <td className="px-4 py-3.5 whitespace-nowrap font-medium text-slate-800">
                        {month.month_label || `${month.month ?? "N/A"}-${month.year ?? ""}`}
                      </td>
                      <td className="px-4 py-3.5 whitespace-nowrap font-mono">{month.executed_trades ?? month.trades ?? 0}</td>
                      <td className={`px-4 py-3.5 whitespace-nowrap font-semibold ${(month.win_rate ?? 0) > 50
                        ? "text-emerald-600"
                        : (month.win_rate ?? 0) === 50
                          ? "text-slate-700"
                          : "text-rose-600"
                        }`}>
                        {(month.win_rate ?? 0).toFixed(1)}%
                      </td>
                      <td className="px-4 py-3.5 whitespace-nowrap font-mono font-semibold text-emerald-600">{(month.profit ?? 0).toFixed(2)}</td>
                      <td className="px-4 py-3.5 whitespace-nowrap font-mono font-semibold text-rose-600">{(month.loss ?? 0).toFixed(2)}</td>
                      <td className={`px-4 py-3.5 whitespace-nowrap font-mono font-semibold ${(month.net_profit ?? 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                        {(month.net_profit ?? 0) >= 0 ? "+" : ""}{(month.net_profit ?? 0).toFixed(2)}
                      </td>
                      <td className={`px-4 py-3.5 whitespace-nowrap font-mono font-semibold ${((month.net_profit ?? 0) / 1000 * 100) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
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
        <div className="fixed inset-0 z-[200] flex items-center justify-center pointer-events-auto">
          {/* Backdrop Blur Saja - UI Ghost Engine Tetap Terlihat */}
          <div className="absolute inset-0 bg-[#F0F6FF]/45 backdrop-blur-xl animate-in fade-in duration-700" />

          <style>{`
            @keyframes floatGhost {
              0%, 100% { transform: translateY(0px) rotate(0deg) scale(1); }
              50% { transform: translateY(-10px) rotate(4deg) scale(1.02); }
            }
          `}</style>

          {/* Lapis 2: Card Popup Glassmorphism dengan pendaran neon */}
          <div 
            className="relative bg-white/[0.02] border border-white/[0.07] rounded-3xl p-10 w-[340px] text-center shadow-[0_32px_64px_rgba(0,0,0,0.5),0_0_40px_rgba(59,130,246,0.03),inset_0_1px_0_rgba(255,255,255,0.1)] transform perspective-1000 rotate-x-6 animate-in zoom-in-95 duration-500 z-10"
            style={{ transformStyle: "preserve-3d" }}
          >
            {/* Lapis 3: Floating Ghost SVG Icon */}
            <div className="mb-6 flex justify-center">
              <svg 
                className="w-14 h-14 text-blue-400 drop-shadow-[0_8px_16px_rgba(96,165,250,0.4)]"
                style={{ animation: "floatGhost 3s ease-in-out infinite" }}
                viewBox="0 0 24 24" 
                fill="none" 
                stroke="currentColor" 
                strokeWidth="1.5" 
                strokeLinecap="round" 
                strokeLinejoin="round"
              >
                <path d="M9 10h.01M15 10h.01" />
                <path d="M12 2a8 8 0 0 0-8 8v12l3-3 3 3 2-3 2 3 3-3 3 3V10a8 8 0 0 0-8-8z" />
              </svg>
            </div>

            {/* Spinner Berkepala Neon */}
            <div className="relative w-11 h-11 border-2 border-white/5 border-t-blue-500 rounded-full mx-auto mb-7 animate-spin shadow-[0_0_16px_rgba(59,130,246,0.4)]" />

            <h2 className="text-xs font-semibold tracking-[0.08em] text-white/90 uppercase mb-6">
              Loading 3D Engine
            </h2>

            {/* Progress Container & Bar */}
            <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden mb-4">
              <div 
                className="h-full bg-gradient-to-r from-blue-500 to-blue-400 shadow-[0_0_12px_rgba(59,130,246,0.6)] transition-all duration-150"
                style={{ width: `${loadProgress.percent}%` }}
              />
            </div>

            <span className="text-[11px] font-mono tracking-wider text-white/45">
              {loadProgress.percent}%
            </span>
            <div className="text-[9px] font-medium text-slate-500 max-w-[240px] truncate mt-2">
              {loadProgress.step}
            </div>
          </div>
        </div>
      )}

      {/* â”€â”€ Transaction Detail Pop-up Modal (100% Identical to trades.tsx) â”€â”€ */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-white/80 backdrop-blur-xl animate-in fade-in duration-200">
          <div className="w-full max-w-[95vw] xl:max-w-[1400px] bg-white/92 border border-blue-200 rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200 relative">
            {/* Premium Gradient Top Accent Line */}
            <div className="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-500" />

            {/* Header */}
            <div className="p-6 pt-7 border-b border-blue-200 flex items-center justify-between bg-white/70">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-300 border border-cyan-500/15">
                  <CalendarDays className="size-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900 tracking-tight">
                    Detail Transaksi - {modalTitle}
                  </h3>
                  <p className="text-xs text-slate-400">
                    Daftar transaksi yang ditutup pada bulan ini
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-800 hover:bg-[#BFDBFE] transition-all cursor-pointer hover:scale-105 active:scale-95 duration-150"
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
                    <div className="bg-[#F0F6FF]/55 border border-blue-200/70 rounded-xl p-4 flex flex-col">
                      <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">Total Trades</span>
                      <span className="text-2xl font-bold text-slate-800 font-mono">{selectedMonthTrades.length}</span>
                    </div>
                    <div className="bg-[#F0F6FF]/55 border border-blue-200/70 rounded-xl p-4 flex flex-col">
                      <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">Win Rate</span>
                      <span className="text-2xl font-bold text-cyan-400 font-mono">
                        {(() => {
                          const wins = selectedMonthTrades.filter(t => (t.net_profit ?? 0) > 0).length;
                          return ((wins / selectedMonthTrades.length) * 100).toFixed(1);
                        })()}%
                      </span>
                    </div>
                    <div className="bg-[#F0F6FF]/55 border border-blue-200/70 rounded-xl p-4 flex flex-col">
                      <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">Net P&L</span>
                      <span className={`text-2xl font-bold font-mono ${selectedMonthTrades.reduce((sum, t) => sum + (t.net_profit ?? 0), 0) >= 0 ? "text-emerald-400" : "text-rose-500"
                        }`}>
                        {selectedMonthTrades.reduce((sum, t) => sum + (t.net_profit ?? 0), 0) >= 0 ? "+" : ""}
                        ${selectedMonthTrades.reduce((sum, t) => sum + (t.net_profit ?? 0), 0).toFixed(2)}
                      </span>
                    </div>
                  </div>

                  {/* Trades Detail Table */}
                  <div className="border border-blue-200/80 rounded-xl overflow-hidden bg-[#F0F6FF]/40">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="bg-white/75 border-b border-blue-200 text-slate-400 text-xs uppercase font-semibold whitespace-nowrap">
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
                        <tbody className="divide-y divide-blue-200/70 text-slate-800">
                          {[...selectedMonthTrades]
                            .sort((a, b) => (a.entry_time || "").localeCompare(b.entry_time || ""))
                            .map((trade) => {
                              const isWin = (trade.net_profit ?? 0) >= 0;
                              return (
                                <tr key={trade.ticket} className="hover:bg-[#BFDBFE]/50 transition-colors whitespace-nowrap">
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
            <div className="p-4 border-t border-blue-200 bg-white/60 flex justify-end">
              <button
                onClick={() => setIsModalOpen(false)}
                className="px-5 py-2 rounded-xl bg-[#BFDBFE] hover:bg-slate-700 text-slate-800 text-sm font-semibold transition-all cursor-pointer"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* â”€â”€ Agent Detail Pop-up Modal â”€â”€ */}
      {isAgentModalOpen && selectedAgent && createPortal((
        <div
          className="fixed left-0 top-0 z-[9999] flex h-[100dvh] w-[100dvw] items-center justify-center p-4 bg-white/80 backdrop-blur-xl animate-in fade-in duration-200"
          onClick={closeAgentModal}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`${selectedAgent.name} detail`}
            onClick={event => event.stopPropagation()}
            className="w-[96vw] max-w-[96vw] h-[calc(100dvh-2rem)] max-h-[calc(100dvh-2rem)] bg-white/92 border border-blue-200 rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden flex flex-col animate-in zoom-in-95 duration-200 relative"
          >
            {/* Premium Gradient Top Accent Line */}
            <div
              className="absolute top-0 left-0 w-full h-[3px]"
              style={{ background: `linear-gradient(90deg, ${selectedAgent.color}, #6366f1)` }}
            />

            {/* Header */}
            <div className="shrink-0 p-6 pt-7 border-b border-blue-200 flex items-center justify-between bg-white/70">
              <div className="flex items-center gap-3">
                <div
                  className="p-2.5 rounded-xl text-lg border"
                  style={{ background: selectedAgent.bg, borderColor: selectedAgent.color }}
                >
                  {selectedAgent.icon && <selectedAgent.icon size={18} aria-hidden="true" />}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900 tracking-tight">
                    {selectedAgent.name}
                  </h3>
                  <p className="text-xs text-slate-400">
                    Detail analisis dan kondisi agen saat simulasi dibentuk
                  </p>
                </div>
              </div>
              <button
                onClick={closeAgentModal}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-800 hover:bg-[#BFDBFE] transition-all cursor-pointer hover:scale-105 active:scale-95 duration-150"
                title="Tutup"
              >
                <X className="size-5" />
              </button>
            </div>

            {/* Content Area */}
            <div className="min-h-0 flex-1 overflow-y-auto p-6 space-y-6">
              {/* Agent Status and Confidence Card */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-[#F0F6FF]/55 border border-blue-200/70 rounded-xl p-4 flex flex-col justify-between">
                  <span className="text-xs text-slate-400 uppercase tracking-wider mb-2">Signal & Status</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xl font-bold text-slate-800">
                      {selectedAgent.signal || "HOLD"}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase ${selectedAgent.status === "fired"
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                      : selectedAgent.status === "skipped"
                        ? "bg-slate-500/10 text-slate-400 border border-slate-500/20"
                        : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                      }`}>
                      {selectedAgent.status}
                    </span>
                  </div>
                </div>

                <div className="bg-[#F0F6FF]/55 border border-blue-200/70 rounded-xl p-4 flex flex-col justify-between">
                  <span className="text-xs text-slate-400 uppercase tracking-wider mb-2">Confidence Level</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xl font-bold font-mono text-cyan-400">
                      {Math.round((selectedAgent.confidence ?? 0) * 100)}%
                    </span>
                    <div className="flex-1 progress-bar h-2 bg-white/80 rounded-full overflow-hidden">
                      <div
                        className="progress-fill h-full bg-cyan-500"
                        style={{ width: `${Math.min(100, Math.max(0, (selectedAgent.confidence ?? 0) * 100))}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Specific Metadata Panel (e.g. LanceDB Pattern Matching for Market Structure) */}
              {selectedAgent.key === "market_structure" && activeFrame?.llm_msa?.display_report && (
                <LLMMSAReport
                  report={activeFrame.llm_msa.display_report}
                  status={activeFrame.llm_msa.status}
                />
              )}

              {!activeFrame?.llm_msa?.display_report && selectedAgent.meta && (selectedAgent.meta.win_rate !== undefined || selectedAgent.meta.pattern_count !== undefined) && (
                <div className="bg-[#F0F6FF]/40 border border-blue-200 rounded-xl p-5 space-y-4">
                  <h4 className="text-sm font-semibold text-slate-600 flex items-center gap-2"><Database size={14} aria-hidden="true" /> Database LanceDB Pattern Matching</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-xs text-slate-400">Pola Serupa Terdeteksi</div>
                      <div className="text-lg font-bold font-mono text-slate-800 mt-1">
                        {selectedAgent.meta.patterns
                          ? selectedAgent.meta.patterns.length
                          : (selectedAgent.meta.pattern_count ?? 0)} pola
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-400">Win Rate Pola Historis</div>
                      <div className={`text-lg font-bold font-mono mt-1 ${selectedAgent.meta.win_rate >= 0.60
                        ? "text-emerald-400"
                        : selectedAgent.meta.win_rate >= 0.45
                          ? "text-cyan-400"
                          : "text-rose-400"
                        }`}>
                        {((selectedAgent.meta.win_rate ?? 0) * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>

                  {/* Matching Patterns List */}
                  {selectedAgent.meta.patterns && selectedAgent.meta.patterns.length > 0 && (
                    <div className="pt-4 border-t border-blue-200/80 space-y-2">
                      <div className="text-xs font-semibold text-slate-400">Semua Pola Historis Serupa:</div>
                      <div className="border border-blue-200/80 rounded-lg overflow-hidden bg-[#F0F6FF]/60 text-xs">
                        <div className="overflow-x-auto max-h-[580px]">
                          <table className="w-full text-left">
                            <thead className="bg-white/70 border-b border-blue-200/80 text-slate-400 font-semibold sticky top-0 backdrop-blur">
                              <tr>
                                {[
                                  { key: "timestamp", label: "Waktu (Timestamp)", align: "left" as const },
                                  { key: "session", label: "Sesi", align: "left" as const },
                                  { key: "outcome", label: "Hasil", align: "right" as const },
                                  { key: "profit_pips", label: "Profit", align: "right" as const },
                                  { key: "similarity", label: "Kemiripan", align: "right" as const },
                                ].map(col => (
                                  <th
                                    key={col.key}
                                    onClick={() => togglePatternSort(col.key)}
                                    className={`py-2 px-3 cursor-pointer select-none hover:text-slate-800 transition-colors ${
                                      col.align === "right" ? "text-right" : "text-left"
                                    }`}
                                  >
                                    <span className={`inline-flex items-center gap-1 ${col.align === "right" ? "justify-end w-full" : ""}`}>
                                      {col.label}
                                      {patternSort.key === col.key ? (
                                        patternSort.dir === "asc" ? (
                                          <ArrowUp className="size-3 text-cyan-400" />
                                        ) : (
                                          <ArrowDown className="size-3 text-cyan-400" />
                                        )
                                      ) : (
                                        <ArrowUpDown className="size-3 opacity-40" />
                                      )}
                                    </span>
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/40 text-slate-600">
                              {[...selectedAgent.meta.patterns]
                                .sort((a: any, b: any) => {
                                  const { key, dir } = patternSort;
                                  const va = key === "timestamp" || key === "session" || key === "outcome"
                                    ? (a[key] || "")
                                    : (a[key] ?? 0);
                                  const vb = key === "timestamp" || key === "session" || key === "outcome"
                                    ? (b[key] || "")
                                    : (b[key] ?? 0);
                                  const cmp = typeof va === "string" ? va.localeCompare(vb) : va - vb;
                                  return dir === "asc" ? cmp : -cmp;
                                })
                                .map((p: any, idx: number) => {
                                const isWin = p.outcome?.toUpperCase() === "WIN";
                                return (
                                  <tr
                                    key={idx}
                                    className="hover:bg-[#BFDBFE]/50 transition-colors cursor-pointer"
                                    onClick={() => setSelectedPattern(p)}
                                  >
                                    <td className="py-2 px-3 font-mono text-[11px] text-slate-400">
                                      {p.timestamp ? p.timestamp.replace("T", " ").substring(0, 19) : "-"}
                                    </td>
                                    <td className="py-2 px-3">{p.session || "-"}</td>
                                    <td className="py-2 px-3 text-right">
                                      <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider ${isWin
                                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/10"
                                        : p.outcome?.toUpperCase() === "LOSS"
                                          ? "bg-rose-500/10 text-rose-400 border border-rose-500/10"
                                          : "bg-slate-500/10 text-slate-400 border border-slate-500/10"
                                        }`}>
                                        {p.outcome || "PENDING"}
                                      </span>
                                    </td>
                                    <td className={`py-2 px-3 text-right font-mono font-semibold ${isWin ? "text-emerald-400" : p.outcome?.toUpperCase() === "PENDING" ? "text-slate-400" : "text-rose-500"}`}>
                                      {isWin ? "+" : ""}{(p.profit_pips ?? 0).toFixed(1)} pips
                                    </td>
                                    <td className="py-2 px-3 text-right font-mono text-cyan-400">
                                      {((p.similarity ?? 0) * 100).toFixed(1)}%
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* â”€â”€ Nested Pattern Detail Popup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
              {selectedPattern && (
                <div
                  className="fixed inset-0 z-[200] flex items-center justify-center"
                  onClick={() => setSelectedPattern(null)}
                >
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
                    className="relative bg-[#0a0f1c] border border-blue-300/65 rounded-2xl p-6 shadow-2xl w-[640px] max-w-[90vw] space-y-4"
                    onClick={e => e.stopPropagation()}
                  >
                    <button
                      onClick={() => setSelectedPattern(null)}
                      className="absolute top-3 right-3 text-slate-500 hover:text-slate-600 transition-colors"
                    >
                      <X size={14} />
                    </button>
                    <div className="text-sm font-semibold text-slate-800">Detail Pola Historis</div>
                    <div className="text-[11px] font-mono text-slate-500">
                      {selectedPattern.timestamp ? selectedPattern.timestamp.replace("T", " ").substring(0, 19) : "-"}
                    </div>

                    {patternCandlesLoading ? (
                      <div className="w-full h-[320px] rounded-xl border border-blue-200/80 bg-[#F0F6FF]/80 flex items-center justify-center text-[11px] text-slate-500 animate-pulse">
                        Memuat candle historis...
                      </div>
                    ) : patternCandles.length > 0 ? (
                      <PatternCandle3DVisualizer candles={patternCandles} structures={patternStructures} />
                    ) : (
                      <div className="w-full h-[320px] rounded-xl border border-dashed border-blue-200/80 bg-[#F0F6FF]/60 flex items-center justify-center text-[11px] text-slate-500">
                        Data candle tidak tersedia
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <div className="text-slate-500 mb-0.5">Entry Price</div>
                        <div className="font-mono font-semibold text-slate-800">
                          {selectedPattern.price != null ? Number(selectedPattern.price).toFixed(2) : "-"}
                        </div>
                      </div>
                      <div>
                        <div className="text-slate-500 mb-0.5">Direction</div>
                        <div className={`font-semibold ${
                          (selectedPattern.direction || "").toLowerCase().includes("bull") ? "text-emerald-400" : "text-rose-400"
                        }`}>
                          {selectedPattern.direction || "-"}
                        </div>
                      </div>
                      <div>
                        <div className="text-slate-500 mb-0.5">Sesi</div>
                        <div className="text-slate-800">{selectedPattern.session || "-"}</div>
                      </div>
                      <div>
                        <div className="text-slate-500 mb-0.5">Status</div>
                        <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider ${
                          selectedPattern.outcome?.toUpperCase() === "WIN"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : selectedPattern.outcome?.toUpperCase() === "LOSS"
                              ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                              : "bg-slate-500/10 text-slate-400 border border-slate-500/20"
                        }`}>
                          {selectedPattern.outcome || "PENDING"}
                        </span>
                      </div>
                      <div>
                        <div className="text-slate-500 mb-0.5">Profit</div>
                        <div className={`font-mono font-semibold ${
                          selectedPattern.outcome?.toUpperCase() === "WIN" ? "text-emerald-400" : "text-rose-500"
                        }`}>
                          {selectedPattern.outcome?.toUpperCase() === "WIN" ? "+" : ""}
                          {(selectedPattern.profit_pips ?? 0).toFixed(1)} pips
                        </div>
                      </div>
                      <div>
                        <div className="text-slate-500 mb-0.5">Kemiripan</div>
                        <div className="font-mono font-semibold text-cyan-400">
                          {((selectedPattern.similarity ?? 0) * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  </motion.div>
                </div>
              )}

              {/* Sentiment Agent News & Calendar Block */}
              {selectedAgent.key === "sentiment" && activeFrame && (
                <div className="space-y-4">
                  {/* News Headlines */}
                  <div className="bg-[#F0F6FF]/40 border border-blue-200 rounded-xl p-5 space-y-3">
                    <h4 className="text-sm font-semibold text-slate-600 flex items-center gap-2">
                      <Newspaper size={13} aria-hidden="true" /> Berita Utama Pasar (Generasi LLM)
                    </h4>
                    {activeFrame.debug_news && activeFrame.debug_news.length > 0 ? (
                      <div className="space-y-2.5">
                        {activeFrame.debug_news.map((item: any, idx: number) => (
                          <div key={idx} className="bg-[#F0F6FF]/60 border border-blue-200/70 rounded-xl p-3.5 flex flex-col gap-1 hover:border-blue-300/65 transition-colors">
                            <span className="text-sm text-slate-800 font-medium leading-snug">
                              {item.headline}
                            </span>
                            <span className="text-[10px] font-mono text-slate-500">
                              {item.timestamp ? item.timestamp.replace("T", " ").substring(0, 19) : "-"}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-slate-500 py-2.5 italic text-center bg-[#F0F6FF]/60 rounded-xl border border-dashed border-blue-200">
                        Tidak ada data berita historis untuk tanggal ini.
                      </div>
                    )}
                  </div>

                  {/* Calendar Events */}
                  <div className="bg-[#F0F6FF]/40 border border-blue-200 rounded-xl p-5 space-y-3">
                    <h4 className="text-sm font-semibold text-slate-600 flex items-center gap-2">
                      <CalendarDays size={14} aria-hidden="true" /> Jadwal Rilis Data Ekonomi (Generasi LLM)
                    </h4>
                    {activeFrame.debug_events && activeFrame.debug_events.length > 0 ? (
                      <div className="border border-blue-200/80 rounded-xl overflow-hidden bg-[#F0F6FF]/60 text-xs">
                        <table className="w-full text-left">
                          <thead className="bg-white/70 border-b border-blue-200/80 text-slate-400 font-semibold">
                            <tr>
                              <th className="py-2.5 px-4">Nama Peristiwa / Data</th>
                              <th className="py-2.5 px-4 text-center">Dampak</th>
                              <th className="py-2.5 px-4 text-right">Waktu Rilis</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/40 text-slate-600">
                            {activeFrame.debug_events.map((item: any, idx: number) => {
                              const isHigh = item.impact?.toLowerCase() === "high";
                              return (
                                <tr key={idx} className="hover:bg-[#BFDBFE]/20 transition-colors">
                                  <td className="py-2.5 px-4 font-medium text-slate-800">
                                    {item.event}
                                  </td>
                                  <td className="py-2.5 px-4 text-center">
                                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                      isHigh 
                                        ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" 
                                        : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                                    }`}>
                                      {item.impact || "medium"}
                                    </span>
                                  </td>
                                  <td className="py-2.5 px-4 text-right font-mono text-slate-400">
                                    {item.time ? item.time.replace("T", " ").substring(0, 19) : "-"}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-xs text-slate-500 py-2.5 italic text-center bg-[#F0F6FF]/60 rounded-xl border border-dashed border-blue-200">
                        Tidak ada peristiwa ekonomi terjadwal untuk tanggal ini.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Reasoning Block */}
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-slate-600 flex items-center gap-2"><FileText size={14} aria-hidden="true" /> Analisis & Rationale (Reasoning)</h4>
                <div className="bg-[#F0F6FF]/60 border border-blue-200/80 rounded-xl p-4 text-sm text-slate-600 leading-relaxed font-sans min-h-[100px] whitespace-pre-wrap">
                  {selectedAgent.reasoning || "Tidak ada rincian analisis dari agen."}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="shrink-0 p-4 border-t border-blue-200 bg-white/60 flex justify-end">
              <button
                onClick={closeAgentModal}
                className="px-5 py-2 rounded-xl bg-[#BFDBFE] hover:bg-slate-700 text-slate-800 text-sm font-semibold transition-all cursor-pointer"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      ), document.body)}
    </div>
  );
}

// â”€â”€ 3D Market Structure Skema Visualizer Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
interface MarketStructure3DVisualizerProps {
  allowChoch: boolean;
  allowBos1: boolean;
  allowBos2: boolean;
  allowBos3Plus: boolean;
}

export function MarketStructure3DVisualizer({
  allowChoch,
  allowBos1,
  allowBos2,
  allowBos3Plus
}: MarketStructure3DVisualizerProps) {
  const mountRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Keep state variables synchronized for frame loop
  const stateRef = useRef({ allowChoch, allowBos1, allowBos2, allowBos3Plus });
  useEffect(() => {
    stateRef.current = { allowChoch, allowBos1, allowBos2, allowBos3Plus };
  }, [allowChoch, allowBos1, allowBos2, allowBos3Plus]);

  useEffect(() => {
    const canvas = mountRef.current;
    const parent = containerRef.current;
    if (!canvas || !parent) return;

    // Scene setup with ambient fog matching theme background
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020617, 0.04);

    // Camera setup (slightly skewed for 3D depth grid perspective)
    const camera = new THREE.PerspectiveCamera(40, parent.clientWidth / parent.clientHeight, 0.1, 50);
    camera.position.set(0.75, 1.1, 8.5);
    camera.lookAt(0.75, 0.35, 0);

    // Renderer
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(parent.clientWidth, parent.clientHeight);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.7);
    dirLight.position.set(5, 5, 5);
    scene.add(dirLight);

    // Cyberpunk grid plane
    const gridHelper = new THREE.GridHelper(40, 40, 0x1e293b, 0x0f172a);
    gridHelper.position.y = -1.2;
    gridHelper.position.z = -0.5;
    scene.add(gridHelper);

    // Trend path nodes coordinates (representing market structural stages)
    const points = [
      new THREE.Vector3(-4.5, -0.8, 0),
      new THREE.Vector3(-3.2, 0.8, 0),
      new THREE.Vector3(-1.9, -0.2, 0),
      new THREE.Vector3(-0.6, 1.2, 0), // CHoCH (Index 3)
      new THREE.Vector3(0.7, 0.2, 0),
      new THREE.Vector3(2.0, 1.2, 0),  // BOS 1 (Index 5)
      new THREE.Vector3(3.3, 0.2, 0),
      new THREE.Vector3(4.6, 1.2, 0),  // BOS 2 (Index 7)
      new THREE.Vector3(5.9, 0.2, 0),
      new THREE.Vector3(7.2, 1.2, 0)   // BOS 3+ (Index 9)
    ];

    // Build Connecting Line Paths
    const lineGeometry = new THREE.BufferGeometry().setFromPoints(points);
    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0x334155,
      linewidth: 2
    });
    const line = new THREE.Line(lineGeometry, lineMaterial);
    scene.add(line);

    // Spherical nodes
    const nodeGeometry = new THREE.SphereGeometry(0.18, 32, 32);

    const materialChoch = new THREE.MeshBasicMaterial();
    const materialBos1 = new THREE.MeshBasicMaterial();
    const materialBos2 = new THREE.MeshBasicMaterial();
    const materialBos3Plus = new THREE.MeshBasicMaterial();

    const meshChoch = new THREE.Mesh(nodeGeometry, materialChoch);
    meshChoch.position.copy(points[3]);
    scene.add(meshChoch);

    const meshBos1 = new THREE.Mesh(nodeGeometry, materialBos1);
    meshBos1.position.copy(points[5]);
    scene.add(meshBos1);

    const meshBos2 = new THREE.Mesh(nodeGeometry, materialBos2);
    meshBos2.position.copy(points[7]);
    scene.add(meshBos2);

    const meshBos3 = new THREE.Mesh(nodeGeometry, materialBos3Plus);
    meshBos3.position.copy(points[9]);
    scene.add(meshBos3);

    let containerWidth = parent.clientWidth;
    let containerHeight = parent.clientHeight;

    const clock = new THREE.Clock();
    let reqId: number;

    // Project coordinates from 3D to 2D HTML absolute divs overlaying canvas
    const updateLabels = () => {
      const { allowChoch, allowBos1, allowBos2, allowBos3Plus } = stateRef.current;
      const nodes = [
        { id: "label-choch", pos: points[3], active: allowChoch },
        { id: "label-bos1", pos: points[5], active: allowBos1 },
        { id: "label-bos2", pos: points[7], active: allowBos2 },
        { id: "label-bos3", pos: points[9], active: allowBos3Plus }
      ];

      const tempV = new THREE.Vector3();
      nodes.forEach(n => {
        const el = document.getElementById(n.id);
        if (!el) return;
        tempV.copy(n.pos);
        tempV.project(camera);
        const x = (tempV.x * 0.5 + 0.5) * containerWidth;
        const y = (-(tempV.y * 0.5) + 0.5) * containerHeight;
        el.style.transform = `translate(-50%, -100%) translate(${x}px, ${y - 8}px)`;
        el.style.color = n.active ? "#06b6d4" : "#475569";
        el.style.textShadow = n.active ? "0 0 8px rgba(6, 182, 212, 0.7)" : "none";
        el.style.fontWeight = n.active ? "bold" : "normal";
      });
    };

    const animate = () => {
      reqId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();
      const { allowChoch, allowBos1, allowBos2, allowBos3Plus } = stateRef.current;

      // Constant breathing neon cycle size oscillation
      const pulse = 1.0 + Math.sin(elapsed * 4) * 0.08;

      // CHoCH Node Lerping
      const targetScaleChoch = allowChoch ? 1.35 * pulse : 0.85;
      meshChoch.scale.setScalar(meshChoch.scale.x + (targetScaleChoch - meshChoch.scale.x) * 0.1);
      materialChoch.color.lerp(new THREE.Color(allowChoch ? 0x06b6d4 : 0x334155), 0.15);

      // BOS 1 Node Lerping
      const targetScaleBos1 = allowBos1 ? 1.35 * pulse : 0.85;
      meshBos1.scale.setScalar(meshBos1.scale.x + (targetScaleBos1 - meshBos1.scale.x) * 0.1);
      materialBos1.color.lerp(new THREE.Color(allowBos1 ? 0x06b6d4 : 0x334155), 0.15);

      // BOS 2 Node Lerping
      const targetScaleBos2 = allowBos2 ? 1.35 * pulse : 0.85;
      meshBos2.scale.setScalar(meshBos2.scale.x + (targetScaleBos2 - meshBos2.scale.x) * 0.1);
      materialBos2.color.lerp(new THREE.Color(allowBos2 ? 0x06b6d4 : 0x334155), 0.15);

      // BOS 3+ Node Lerping
      const targetScaleBos3 = allowBos3Plus ? 1.35 * pulse : 0.85;
      meshBos3.scale.setScalar(meshBos3.scale.x + (targetScaleBos3 - meshBos3.scale.x) * 0.1);
      materialBos3Plus.color.lerp(new THREE.Color(allowBos3Plus ? 0x06b6d4 : 0x334155), 0.15);

      // Add gentle cinematic dynamic drift camera angle
      camera.position.x = 0.75 + Math.sin(elapsed * 0.3) * 0.25;

      renderer.render(scene, camera);
      updateLabels();
    };

    animate();

    // ResizeObserver to always update viewport dynamic scaling
    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        containerWidth = parent.clientWidth || entry.contentRect.width;
        containerHeight = parent.clientHeight || entry.contentRect.height;
        camera.aspect = containerWidth / containerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(containerWidth, containerHeight);
      }
    });
    resizeObserver.observe(parent);

    // Garbage collection on component unmount
    return () => {
      cancelAnimationFrame(reqId);
      resizeObserver.disconnect();
      renderer.dispose();
      lineGeometry.dispose();
      lineMaterial.dispose();
      nodeGeometry.dispose();
      materialChoch.dispose();
      materialBos1.dispose();
      materialBos2.dispose();
      materialBos3Plus.dispose();
    };
  }, []);

  return (
    <div ref={containerRef} className="w-full h-[140px] relative overflow-hidden bg-[#F0F6FF]/80 rounded-xl border border-blue-200/80 mb-2">
      <canvas ref={mountRef} className="w-full h-full block" />
      
      {/* 2D Projected labels */}
      <div id="label-choch" className="absolute left-0 top-0 text-[10px] uppercase tracking-wider pointer-events-none transition-colors duration-150 select-none">CHoCH</div>
      <div id="label-bos1" className="absolute left-0 top-0 text-[10px] uppercase tracking-wider pointer-events-none transition-colors duration-150 select-none">BOS 1</div>
      <div id="label-bos2" className="absolute left-0 top-0 text-[10px] uppercase tracking-wider pointer-events-none transition-colors duration-150 select-none">BOS 2</div>
      <div id="label-bos3" className="absolute left-0 top-0 text-[10px] uppercase tracking-wider pointer-events-none transition-colors duration-150 select-none">BOS 3+</div>
    </div>
  );
}

// â”€â”€ 3D Veto Consensus Map Visualizer Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
interface VetoConsensus3DVisualizerProps {
  vetoMode: "hard" | "soft" | "none";
}

export function VetoConsensus3DVisualizer({ vetoMode }: VetoConsensus3DVisualizerProps) {
  const mountRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const stateRef = useRef({ vetoMode });
  useEffect(() => {
    stateRef.current = { vetoMode };
  }, [vetoMode]);

  useEffect(() => {
    const canvas = mountRef.current;
    const parent = containerRef.current;
    if (!canvas || !parent) return;

    // Scene setup with exponential background fog
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020617, 0.05);

    // Camera setup
    const camera = new THREE.PerspectiveCamera(40, parent.clientWidth / parent.clientHeight, 0.1, 50);
    camera.position.set(0, 0, 7.2);

    // Renderer
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(parent.clientWidth, parent.clientHeight);

    // Cyberpunk grid plane
    const gridHelper = new THREE.GridHelper(30, 30, 0x1e293b, 0x0f172a);
    gridHelper.position.y = -1.2;
    gridHelper.position.z = -0.5;
    scene.add(gridHelper);

    // Node relative coordinates
    const posMS = new THREE.Vector3(-1.8, 0.7, 0);   // Market Structure Agent
    const posML = new THREE.Vector3(1.8, 0.7, 0);    // ML Filter Agent
    const posSR = new THREE.Vector3(0, -0.9, 0);     // Risk & Sentiment Agent
    const posCore = new THREE.Vector3(0, 0.15, 0);   // Consensus Core

    // Sphere meshes
    const agentGeom = new THREE.SphereGeometry(0.16, 32, 32);
    const coreGeom = new THREE.SphereGeometry(0.23, 32, 32);

    const matMS = new THREE.MeshBasicMaterial();
    const matML = new THREE.MeshBasicMaterial();
    const matSR = new THREE.MeshBasicMaterial();
    const matCore = new THREE.MeshBasicMaterial();

    const meshMS = new THREE.Mesh(agentGeom, matMS);
    meshMS.position.copy(posMS);
    scene.add(meshMS);

    const meshML = new THREE.Mesh(agentGeom, matML);
    meshML.position.copy(posML);
    scene.add(meshML);

    const meshSR = new THREE.Mesh(agentGeom, matSR);
    meshSR.position.copy(posSR);
    scene.add(meshSR);

    const meshCore = new THREE.Mesh(coreGeom, matCore);
    meshCore.position.copy(posCore);
    scene.add(meshCore);

    // Connective Neon Lines
    const matLineMS = new THREE.LineBasicMaterial({ linewidth: 2 });
    const matLineML = new THREE.LineBasicMaterial({ color: 0x06b6d4, linewidth: 2 });
    const matLineSR = new THREE.LineBasicMaterial({ color: 0x06b6d4, linewidth: 2 });

    const lineMS = new THREE.Line(new THREE.BufferGeometry().setFromPoints([posMS, posCore]), matLineMS);
    const lineML = new THREE.Line(new THREE.BufferGeometry().setFromPoints([posML, posCore]), matLineML);
    const lineSR = new THREE.Line(new THREE.BufferGeometry().setFromPoints([posSR, posCore]), matLineSR);

    scene.add(lineMS);
    scene.add(lineML);
    scene.add(lineSR);

    let containerWidth = parent.clientWidth;
    let containerHeight = parent.clientHeight;
    
    const clock = new THREE.Clock();
    let reqId: number;

    // Track coordinates dynamic projection
    const updateLabels = () => {
      const nodes = [
        { id: "veto-label-ms", pos: posMS },
        { id: "veto-label-ml", pos: posML },
        { id: "veto-label-sr", pos: posSR },
        { id: "veto-label-core", pos: posCore }
      ];

      const tempV = new THREE.Vector3();
      nodes.forEach(n => {
        const el = document.getElementById(n.id);
        if (!el) return;
        tempV.copy(n.pos);
        tempV.project(camera);
        const x = (tempV.x * 0.5 + 0.5) * containerWidth;
        const y = (-(tempV.y * 0.5) + 0.5) * containerHeight;
        el.style.transform = `translate(-50%, -100%) translate(${x}px, ${y - 8}px)`;
      });
    };

    const animate = () => {
      reqId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();
      const { vetoMode } = stateRef.current;

      const pulse = 1.0 + Math.sin(elapsed * 5) * 0.08;

      // Auxiliary agents bounce animations
      matML.color.setHex(0x06b6d4);
      matSR.color.setHex(0x06b6d4);
      meshML.scale.setScalar(1.0 + Math.sin(elapsed * 3) * 0.04);
      meshSR.scale.setScalar(1.0 + Math.cos(elapsed * 3) * 0.04);

      // Adaptive color representation based on veto modes
      if (vetoMode === "hard") {
        matMS.color.lerp(new THREE.Color(0xef4444), 0.1);
        matCore.color.lerp(new THREE.Color(0xef4444), 0.1);
        matLineMS.color.lerp(new THREE.Color(0xef4444), 0.1);

        meshMS.scale.setScalar(1.35 * pulse);
        meshCore.scale.setScalar(1.0 + Math.sin(elapsed * 8) * 0.08); // rapid alert pulse
      } else if (vetoMode === "soft") {
        matMS.color.lerp(new THREE.Color(0xf59e0b), 0.1);
        matCore.color.lerp(new THREE.Color(0xf59e0b), 0.1);
        matLineMS.color.lerp(new THREE.Color(0xf59e0b), 0.1);

        meshMS.scale.setScalar(1.2 * pulse);
        meshCore.scale.setScalar(1.1 + Math.sin(elapsed * 3) * 0.04);
      } else {
        matMS.color.lerp(new THREE.Color(0x06b6d4), 0.1);
        matCore.color.lerp(new THREE.Color(0x10b981), 0.1); // emerald active green
        matLineMS.color.lerp(new THREE.Color(0x06b6d4), 0.1);

        meshMS.scale.setScalar(1.0 * pulse);
        meshCore.scale.setScalar(1.25 * pulse);
      }

      // Orbital parallax drift camera
      camera.position.x = Math.sin(elapsed * 0.25) * 0.5;
      camera.position.y = Math.cos(elapsed * 0.2) * 0.15;
      camera.lookAt(0, 0.1, 0);

      renderer.render(scene, camera);
      updateLabels();
    };

    animate();

    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        containerWidth = parent.clientWidth || entry.contentRect.width;
        containerHeight = parent.clientHeight || entry.contentRect.height;
        camera.aspect = containerWidth / containerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(containerWidth, containerHeight);
      }
    });
    resizeObserver.observe(parent);

    return () => {
      cancelAnimationFrame(reqId);
      resizeObserver.disconnect();
      renderer.dispose();
      agentGeom.dispose();
      coreGeom.dispose();
      matMS.dispose();
      matML.dispose();
      matSR.dispose();
      matCore.dispose();
      matLineMS.dispose();
      matLineML.dispose();
      matLineSR.dispose();
    };
  }, []);

  return (
    <div ref={containerRef} className="w-full h-[140px] relative overflow-hidden bg-[#F0F6FF]/80 rounded-xl border border-blue-200/80 mb-2">
      <canvas ref={mountRef} className="w-full h-full block" />
      
      {/* 2D Projected labels */}
      <div id="veto-label-ms" className="absolute left-0 top-0 text-[9px] uppercase font-bold tracking-wider pointer-events-none text-slate-400 select-none">Structure</div>
      <div id="veto-label-ml" className="absolute left-0 top-0 text-[9px] uppercase font-bold tracking-wider pointer-events-none text-slate-400 select-none">ML Filter</div>
      <div id="veto-label-sr" className="absolute left-0 top-0 text-[9px] uppercase font-bold tracking-wider pointer-events-none text-slate-400 select-none">Risk & Sent.</div>
      <div id="veto-label-core" className="absolute left-0 top-0 text-[9px] uppercase font-bold tracking-wider pointer-events-none text-slate-800 select-none">Consensus</div>
    </div>
  );
}

// â”€â”€ 3D Pattern Candle Formation Visualizer (MSA "Detail Pola Historis" popup) â”€â”€
interface PatternCandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  ema200: number | null;
}

// Same UTC-hour session buckets used server-side (orchestrator_simulator._detect_session).
function sessionAtHour(hour: number): string {
  if (hour >= 0 && hour < 8) return "Tokyo";
  if (hour >= 8 && hour < 12) return "London";
  if (hour >= 12 && hour < 17) return "London_NY_Overlap";
  if (hour >= 17 && hour < 21) return "NewYork";
  return "Offmarket";
}
const SESSION_COLORS: Record<string, number> = {
  Tokyo: 0x8b5cf6,
  London: 0x14b8a6,
  London_NY_Overlap: 0x2563eb,
  NewYork: 0xca8a04,
  Offmarket: 0x475569,
};
interface PatternStructureData {
  type: string;
  direction: string;
  price: number | null;
  time: number | null;
}
interface PatternCandle3DVisualizerProps {
  candles: PatternCandleData[];
  structures: PatternStructureData[];
}

function easeOutCubic(t: number) {
  return 1 - Math.pow(1 - t, 3);
}

export function PatternCandle3DVisualizer({ candles, structures }: PatternCandle3DVisualizerProps) {
  const mountRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const validStructures = structures.filter(s => s.price != null && s.time != null);

  useEffect(() => {
    const canvas = mountRef.current;
    const parent = containerRef.current;
    if (!canvas || !parent || candles.length === 0) return;

    const scene = new THREE.Scene();
    const fog = new THREE.FogExp2(0x020617, 0.06);
    scene.fog = fog;
    // Everything price-related (candles + break lines) lives under this group so
    // dragging the price-axis handle can rescale it vertically in one place,
    // like dragging the right price axis on the 2D chart.
    const contentGroup = new THREE.Group();
    scene.add(contentGroup);
    let verticalZoom = 1;
    // FogExp2 attenuates as (density * distance)^2, so a density tuned for a short
    // camera distance turns opaque once the camera pulls back for more candles.
    // Solve density from the camera's actual distance so the fog's visual weight
    // (target ~15% blend toward fog color) stays constant regardless of candle count.
    const FOG_TARGET_FACTOR = 0.15;
    const fogK = Math.sqrt(-Math.log(1 - FOG_TARGET_FACTOR));

    const camera = new THREE.PerspectiveCamera(38, parent.clientWidth / parent.clientHeight, 0.1, 50);

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(parent.clientWidth, parent.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    scene.add(new THREE.AmbientLight(0xffffff, 0.85));
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.15);
    dirLight.position.set(3, 4, 5);
    scene.add(dirLight);
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.5);
    fillLight.position.set(-4, -2, 4);
    scene.add(fillLight);

    // Price range: anchor on the candles' own high/low + EMA200 (the actual visible
    // price action). A structure's break price (LL/HH/BoS/CHoCH) can reference a much
    // older swing far outside this window; including it unconditionally used to blow
    // up the whole vertical scale and squeeze every candle into a thin band in the
    // middle of the frame. Nearby structures still expand the range so their line
    // isn't clipped -- only outliers beyond a reasonable multiple of the candle span
    // are left to render off toward the frame edge instead of dictating the zoom.
    const candleLows = candles.map(c => c.low);
    const candleHighs = candles.map(c => c.high);
    candles.forEach(c => {
      if (c.ema200 != null) {
        candleLows.push(c.ema200);
        candleHighs.push(c.ema200);
      }
    });
    const candleMinLow = Math.min(...candleLows);
    const candleMaxHigh = Math.max(...candleHighs);
    const candleSpan = Math.max(candleMaxHigh - candleMinLow, 0.01);
    const STRUCTURE_RANGE_EXPANSION = 0.6; // max extra range a structure price may add, as a multiple of candleSpan

    let minLow = candleMinLow;
    let maxHigh = candleMaxHigh;
    validStructures.forEach(s => {
      const p = s.price!;
      if (p < minLow && minLow - p <= candleSpan * STRUCTURE_RANGE_EXPANSION) minLow = p;
      if (p > maxHigh && p - maxHigh <= candleSpan * STRUCTURE_RANGE_EXPANSION) maxHigh = p;
    });
    const priceSpan = Math.max(maxHigh - minLow, 0.01);

    // Layout
    const spacingX = 0.5;
    const totalWidth = spacingX * (candles.length - 1);
    const startX = -totalWidth / 2;
    // Break lines extend a bit past the last candle, so include that in the fit width.
    const sceneWidth = totalWidth + spacingX * 1.2;

    // Size the content's vertical extent to match the container's aspect ratio
    // (instead of a fixed constant) so the perspective camera binds on both axes
    // at once -- otherwise whichever axis doesn't need the full zoom-out is left
    // with unused space around the candles, which is what created the blank
    // margins in this popup.
    const containerAspect = parent.clientWidth / parent.clientHeight;
    // Only a floor, no ceiling: with up to ~70 candles, sceneWidth can be 30+ units,
    // so matching a ~2:1 container legitimately needs a verticalScale around 15-18,
    // not the old fixed 2.2. An earlier version of this fix capped verticalScale at
    // 3.5, which silently defeated the aspect match for wide scenes -- that's why it
    // didn't visibly change anything.
    const verticalScale = Math.max(sceneWidth / Math.max(containerAspect, 0.1), 0.8);
    const normalizeY = (price: number) => ((price - minLow) / priceSpan) * verticalScale - verticalScale / 2;

    // Pull the camera back just far enough that every candle (and the break lines
    // extending past the last one) stays inside the frustum, at any container size.
    const fitCamera = () => {
      const aspect = parent.clientWidth / parent.clientHeight;
      const vFov = (camera.fov * Math.PI) / 180;
      // verticalScale is already derived to match containerAspect, so this margin
      // applies equally to both axes -- keep it tight so the chart reads as filling
      // the popup, not floating in a padded box. Just enough to keep wicks and the
      // break-line dashes off the literal edge.
      const margin = 1.04;
      const zForHeight = (verticalScale / 2) * margin / Math.tan(vFov / 2);
      const zForWidth = (sceneWidth / 2) * margin / (Math.tan(vFov / 2) * aspect);
      camera.position.z = Math.max(zForHeight, zForWidth, 3);
      camera.aspect = aspect;
      camera.updateProjectionMatrix();
      fog.density = fogK / camera.position.z;
    };
    camera.position.set(0, 0.1, 6.4);
    fitCamera();
    const bodyWidth = spacingX * 0.58;
    const wickWidth = spacingX * 0.1;
    const depth = 0.32;

    const bullColor = 0x10b981;
    const bearColor = 0xf43769;

    // Build one group per candle (body + wick), hidden initially (scale 0, opacity 0)
    const candleGroups: THREE.Group[] = [];
    const disposableGeometries: THREE.BufferGeometry[] = [];
    const disposableMaterials: THREE.Material[] = [];

    candles.forEach((c, i) => {
      const isBull = c.close >= c.open;
      const color = isBull ? bullColor : bearColor;
      const x = startX + i * spacingX;

      const group = new THREE.Group();
      group.position.x = x;

      const bodyTop = normalizeY(Math.max(c.open, c.close));
      const bodyBottom = normalizeY(Math.min(c.open, c.close));
      const bodyHeight = Math.max(bodyTop - bodyBottom, 0.02);

      const bodyGeom = new THREE.BoxGeometry(bodyWidth, bodyHeight, depth);
      const bodyMat = new THREE.MeshStandardMaterial({
        color,
        transparent: true,
        opacity: 0,
        metalness: 0.1,
        roughness: 0.3,
        emissive: color,
        emissiveIntensity: 0.45,
      });
      const bodyMesh = new THREE.Mesh(bodyGeom, bodyMat);
      bodyMesh.position.y = (bodyTop + bodyBottom) / 2;
      group.add(bodyMesh);

      const wickTop = normalizeY(c.high);
      const wickBottom = normalizeY(c.low);
      const wickGeom = new THREE.BoxGeometry(wickWidth, Math.max(wickTop - wickBottom, 0.01), wickWidth);
      const wickMat = new THREE.MeshStandardMaterial({
        color,
        transparent: true,
        opacity: 0,
        metalness: 0.1,
        roughness: 0.3,
        emissive: color,
        emissiveIntensity: 0.45,
      });
      const wickMesh = new THREE.Mesh(wickGeom, wickMat);
      wickMesh.position.y = (wickTop + wickBottom) / 2;
      group.add(wickMesh);

      group.scale.setScalar(0.9);
      contentGroup.add(group);
      candleGroups.push(group);
      disposableGeometries.push(bodyGeom, wickGeom);
      disposableMaterials.push(bodyMat, wickMat);
    });

    // Session background bands, one per contiguous run of same-session candles.
    // Kept on `scene` (not `contentGroup`) so they stay fixed to the time axis and
    // don't stretch when the price-axis handle is dragged.
    const sessionRuns: { session: string; startIdx: number; endIdx: number }[] = [];
    candles.forEach((c, i) => {
      const session = sessionAtHour(new Date(c.time * 1000).getUTCHours());
      const last = sessionRuns[sessionRuns.length - 1];
      if (last && last.session === session) {
        last.endIdx = i;
      } else {
        sessionRuns.push({ session, startIdx: i, endIdx: i });
      }
    });
    const zoneHeight = verticalScale * 3;
    sessionRuns.forEach(run => {
      const runStartX = startX + run.startIdx * spacingX - spacingX / 2;
      const runEndX = startX + run.endIdx * spacingX + spacingX / 2;
      const width = Math.max(runEndX - runStartX, 0.01);
      const geom = new THREE.PlaneGeometry(width, zoneHeight);
      const mat = new THREE.MeshBasicMaterial({
        color: SESSION_COLORS[run.session] ?? 0x475569,
        transparent: true,
        opacity: 0.07,
        fog: false,
        depthWrite: false,
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.position.set(runStartX + width / 2, 0, -0.4);
      scene.add(mesh);
      disposableGeometries.push(geom);
      disposableMaterials.push(mat);
    });

    // Dashed separator at every session boundary, same idea as the vertical session
    // dividers on the 2D chart. Also kept on `scene` so it stays fixed to time.
    for (let i = 1; i < sessionRuns.length; i++) {
      const boundaryX = startX + sessionRuns[i].startIdx * spacingX - spacingX / 2;
      const sepGeom = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(boundaryX, -zoneHeight / 2, -0.35),
        new THREE.Vector3(boundaryX, zoneHeight / 2, -0.35),
      ]);
      const sepMat = new THREE.LineDashedMaterial({
        color: 0xe2e8f0,
        transparent: true,
        opacity: 0.18,
        dashSize: 0.06,
        gapSize: 0.05,
        fog: false,
      });
      const sepLine = new THREE.Line(sepGeom, sepMat);
      sepLine.computeLineDistances();
      scene.add(sepLine);
      disposableGeometries.push(sepGeom);
      disposableMaterials.push(sepMat);
    }

    // EMA200 line, real data straight from the M15 table.
    const emaPoints: THREE.Vector3[] = [];
    candles.forEach((c, i) => {
      if (c.ema200 != null) {
        emaPoints.push(new THREE.Vector3(startX + i * spacingX, normalizeY(c.ema200), 0.02));
      }
    });
    let emaMat: THREE.LineBasicMaterial | null = null;
    if (emaPoints.length >= 2) {
      const emaGeom = new THREE.BufferGeometry().setFromPoints(emaPoints);
      emaMat = new THREE.LineBasicMaterial({ color: 0xf59e0b, transparent: true, opacity: 0, fog: false });
      const emaLine = new THREE.Line(emaGeom, emaMat);
      contentGroup.add(emaLine);
      disposableGeometries.push(emaGeom);
      disposableMaterials.push(emaMat);
    }

    // Every BOS/CHoCH/HH/LL structure in range gets its own break line, drawn
    // once the candle it belongs to has finished popping in. Kept short (~9
    // candles) instead of spanning the whole window.
    const structureLines = validStructures.map((s, idx) => {
      // Candles are ascending by open time; the structure is confirmed by whichever
      // candle's open time it falls on/after, i.e. the last candle whose open <= event time.
      const structureIndex = candles.reduce((acc, c, i) => (c.time <= s.time! ? i : acc), 0);

      const isBull = (s.direction || "").toLowerCase().includes("bull");
      const lineColor = isBull ? 0x06b6d4 : 0xf43769;
      const y = normalizeY(s.price!);
      // Start the line at the close (right edge) of the confirming candle, not its center.
      const lineStartX = startX + structureIndex * spacingX + bodyWidth / 2;

      // Stop the line at whichever candle actually closes back through the level --
      // that's what "breaks" the structure -- instead of always running a fixed
      // length. If nothing breaks it within the window, fall back to a ~9-candle run.
      let breakIndex = -1;
      for (let j = structureIndex + 1; j < candles.length; j++) {
        const closed = candles[j].close;
        if (isBull ? closed > s.price! : closed < s.price!) {
          breakIndex = j;
          break;
        }
      }
      const fallbackEndX = Math.min(lineStartX + spacingX * 9, startX + totalWidth + spacingX * 0.6);
      const lineEndX = breakIndex >= 0 ? startX + breakIndex * spacingX + bodyWidth / 2 : fallbackEndX;

      const geom = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(lineStartX, y, 0),
        new THREE.Vector3(lineEndX, y, 0),
      ]);
      const mat = new THREE.LineDashedMaterial({
        color: lineColor,
        dashSize: 0.08,
        gapSize: 0.06,
        transparent: true,
        opacity: 0,
      });
      const line = new THREE.Line(geom, mat);
      line.computeLineDistances();
      contentGroup.add(line);

      return { line, geom, mat, structureIndex, lineStartX, y, labelId: `pattern-structure-label-${idx}`, isBull, type: s.type, price: s.price! };
    });

    let containerWidth = parent.clientWidth;
    let containerHeight = parent.clientHeight;
    const clock = new THREE.Clock();
    let reqId: number;

    const updateStructureLabel = (sl: typeof structureLines[number], visible: boolean) => {
      const el = document.getElementById(sl.labelId);
      if (!el) return;
      if (!visible) {
        el.style.opacity = "0";
        return;
      }
      el.textContent = `${sl.type} ${sl.price.toFixed(2)}`;

      const tempV = new THREE.Vector3(sl.lineStartX, sl.y * verticalZoom, 0);
      tempV.project(camera);
      const rawX = (tempV.x * 0.5 + 0.5) * containerWidth;
      const rawY = (-(tempV.y * 0.5) + 0.5) * containerHeight;

      // Keep the label fully inside the popup instead of letting it clip at the edge.
      const halfLabelWidth = (el.offsetWidth || 60) / 2;
      const x = Math.min(Math.max(rawX, halfLabelWidth + 4), containerWidth - halfLabelWidth - 4);

      // Put the label on whichever side of the line has open space: below a swing
      // low (the candles cluster above it), above a swing high (they cluster below
      // it) -- the fixed "always above" offset used to land right on top of the
      // candle bodies for lows. Then clamp inside the popup: a point pinned to the
      // very top/bottom edge of the price range would otherwise push its label
      // past the container and get clipped to invisible instead of just close.
      const gap = 8;
      const labelHeight = el.offsetHeight || 18;
      const placeBelow = sl.y < 0;
      const rawLabelY = placeBelow ? rawY + gap : rawY - labelHeight - gap;
      const y = Math.min(Math.max(rawLabelY, 4), containerHeight - labelHeight - 4);

      el.style.transform = `translate(-50%, 0) translate(${x}px, ${y}px)`;
      el.style.opacity = "1";
    };

    const STAGGER = 0.09;
    const DURATION = 0.22;

    const animate = () => {
      reqId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      candleGroups.forEach((group, i) => {
        const localStart = i * STAGGER;
        const t = Math.min(Math.max((elapsed - localStart) / DURATION, 0), 1);
        const eased = easeOutCubic(t);
        group.scale.setScalar(0.9 + 0.1 * eased);
        group.children.forEach(child => {
          const mesh = child as THREE.Mesh;
          (mesh.material as THREE.MeshStandardMaterial).opacity = eased;
        });
      });

      structureLines.forEach(sl => {
        const revealT = Math.min(
          Math.max((elapsed - (sl.structureIndex * STAGGER + DURATION)) / DURATION, 0),
          1
        );
        sl.mat.opacity = revealT * 0.9;
        updateStructureLabel(sl, revealT > 0.05);
      });

      if (emaMat) {
        emaMat.opacity = Math.min(elapsed / 0.6, 1) * 0.85;
      }

      camera.position.x = Math.sin(elapsed * 0.2) * 0.2;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
    };

    animate();

    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        containerWidth = parent.clientWidth || entry.contentRect.width;
        containerHeight = parent.clientHeight || entry.contentRect.height;
        fitCamera();
        renderer.setSize(containerWidth, containerHeight);
      }
    });
    resizeObserver.observe(parent);

    // Drag the right-edge price-axis handle up/down to stretch or squash the
    // vertical scale, same interaction as dragging the price axis on the 2D chart.
    const axisHandle = document.getElementById("pattern-axis-handle");
    let isDraggingAxis = false;
    let dragStartY = 0;
    let dragStartZoom = 1;
    const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), max);

    const onAxisPointerDown = (e: PointerEvent) => {
      isDraggingAxis = true;
      dragStartY = e.clientY;
      dragStartZoom = verticalZoom;
      if (axisHandle) axisHandle.style.background = "rgba(6, 182, 212, 0.12)";
      e.preventDefault();
    };
    const onAxisPointerMove = (e: PointerEvent) => {
      if (!isDraggingAxis) return;
      const deltaY = e.clientY - dragStartY;
      verticalZoom = clamp(dragStartZoom * Math.pow(2, deltaY / 120), 0.4, 3);
      contentGroup.scale.y = verticalZoom;
    };
    const onAxisPointerUp = () => {
      isDraggingAxis = false;
      if (axisHandle) axisHandle.style.background = "transparent";
    };
    axisHandle?.addEventListener("pointerdown", onAxisPointerDown);
    window.addEventListener("pointermove", onAxisPointerMove);
    window.addEventListener("pointerup", onAxisPointerUp);

    return () => {
      cancelAnimationFrame(reqId);
      resizeObserver.disconnect();
      renderer.dispose();
      disposableGeometries.forEach(g => g.dispose());
      disposableMaterials.forEach(m => m.dispose());
      structureLines.forEach(sl => {
        sl.geom.dispose();
        sl.mat.dispose();
        const el = document.getElementById(sl.labelId);
        if (el) el.style.opacity = "0";
      });
      axisHandle?.removeEventListener("pointerdown", onAxisPointerDown);
      window.removeEventListener("pointermove", onAxisPointerMove);
      window.removeEventListener("pointerup", onAxisPointerUp);
    };
  }, [candles, structures]);

  if (candles.length === 0) return null;

  return (
    <div ref={containerRef} className="w-full h-[320px] relative overflow-hidden bg-[#F0F6FF]/80 rounded-xl border border-blue-200/80">
      <canvas ref={mountRef} className="w-full h-full block" />
      <div
        id="pattern-axis-handle"
        title="Drag untuk mengubah skala harga"
        className="absolute right-0 top-0 h-full w-6 cursor-ns-resize transition-colors duration-150"
        style={{ touchAction: "none" }}
      />
      {validStructures.map((s, idx) => {
        const isBull = (s.direction || "").toLowerCase().includes("bull");
        return (
          <div
            key={idx}
            id={`pattern-structure-label-${idx}`}
            className={`absolute left-0 top-0 text-[9px] font-mono font-bold tracking-wide pointer-events-none select-none transition-opacity duration-200 rounded px-1.5 py-0.5 border bg-white/90 whitespace-nowrap ${
              isBull ? "text-cyan-400 border-cyan-500/40" : "text-rose-400 border-rose-500/40"
            }`}
            style={{ opacity: 0 }}
          />
        );
      })}
    </div>
  );
}

