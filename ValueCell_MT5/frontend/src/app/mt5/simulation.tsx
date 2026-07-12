import { useEffect, useRef, useState, useCallback, useMemo } from "react";
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
import { Play, Pause, SkipForward, Square, Loader2, Calendar, CalendarDays, X, Rewind } from "lucide-react";
import {
  StructureLinesPrimitive,
  type StructureLineItem,
} from "@/components/valuecell/charts/structure-lines-primitive";
import {
  TradesOverlayPrimitive,
  type TradeOverlayEntry,
} from "@/components/valuecell/charts/trades-overlay-primitive";

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

// ── Constants ────────────────────────────────────────────────────────────────

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
}

function CustomSelect<T extends string | number>({
  value,
  onChange,
  options,
  getLabel,
  accent,
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
    <div ref={containerRef} className="relative select-none z-[100] group">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 border rounded-lg text-xs font-semibold text-white transition-all duration-200 active:scale-95 cursor-pointer whitespace-nowrap outline-none"
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
          className="absolute top-[calc(100%+6px)] right-0 min-w-[140px] bg-[var(--bg-surface,#0f172a)] border border-[var(--glass-border,rgba(255,255,255,0.1))] rounded-[10px] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.5)] z-[110] transition-all origin-top-right animate-in fade-in zoom-in-95 slide-in-from-top-2 duration-150 ease-out"
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
                className="px-2.5 py-2 rounded-md border border-transparent text-xs transition-all duration-150 active:scale-[0.98] cursor-pointer text-[var(--text-secondary,#cbd5e1)] hover:bg-[var(--bg-elevated,rgba(255,255,255,0.05))] hover:text-white"
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
  initial_sl_dist: number;     // USD, default 3.00 (300 poin)
  initial_tp_dist: number;     // USD, default 30.00 (3000 poin)
  sl_min_distance: number;     // USD, default 5.00 (500 poin)
  sl_safety_buffer: number;    // USD, default 10.00 (1000 poin)
}

export const DEFAULT_STRATEGY_PARAMS: StrategyParams = {
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

  const activeCandles = candles.filter(c => c.time >= (t.entry_time ?? 0) && c.time <= currentCandleTime);
  let expansionCount = 0;
  let beTriggered = false;
  let isClosedSimulated = false;
  let exitPriceSimulated: number | null = null;
  let exitTimeSimulated: number | null = null;

  for (const c of activeCandles) {
    const price = c.close;

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

// ── Agent Panel (cursor-following orchestrator frames) ─────────────────────────

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
  // Trade execution context — populated by backend _build_frame when the
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
  // Sentiment debug context — only populated by the single-event endpoint
  // (trading.py:simulate-event). Consumed by the modal's News & Calendar block.
  debug_news?: Array<{ headline?: string; timestamp?: string }>;
  debug_events?: Array<{ event?: string; impact?: string; time?: string }>;
  // Counter-swing flag: frontend should NOT update Agent Consensus panel
  // when true — keeps warm-up values from the setup swing event visible.
  is_counter_swing?: boolean;
}

const AGENT_PANEL_DEFS = [
  { key: "market_structure" as const, name: "Market Structure Agent", icon: "🏗️", color: "var(--neon-blue)", bg: "rgba(59,130,246,0.2)" },
  { key: "ml_prediction" as const, name: "ML Filter Agent", icon: "🧠", color: "var(--neon-purple)", bg: "rgba(139,92,246,0.2)" },
  { key: "sentiment" as const, name: "Sentiment Agent", icon: "📰", color: "var(--neon-emerald)", bg: "rgba(16,185,129,0.2)" },
  { key: "risk_management" as const, name: "Risk Manager", icon: "🛡️", color: "var(--neon-amber)", bg: "rgba(251,191,36,0.2)" },
];

// ── Types for simulation helper ──────────────────────────────────────────────

export default function SimulationOfDead() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const emaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<any> | null>(null);
  const structurePrimitiveRef = useRef<StructureLinesPrimitive | null>(null);
  const tradesPrimitiveRef = useRef<TradesOverlayPrimitive | null>(null);
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
  const [orchestratorEnabled, setOrchestratorEnabled] = useState<boolean>(true);
  const [simSignals, setSimSignals] = useState<any[]>([]);
  const [agentTrades, setAgentTrades] = useState<any[]>([]);
  const [simMetrics, setSimMetrics] = useState<any | null>(null);
  const [simFrames, setSimFrames] = useState<SimFrame[]>([]);
  const [simError, setSimError] = useState<string | null>(null);
  const [simLoading, setSimLoading] = useState<boolean>(false);
  const [simFramesMap, setSimFramesMap] = useState<Record<string, SimFrame>>({});
  const [isFrameLoading, setIsFrameLoading] = useState<boolean>(false);
  const [activeFrame, setActiveFrame] = useState<SimFrame | null>(null);
  const activeFrameAbortControllerRef = useRef<AbortController | null>(null);
  // ponytail: limit concurrent simulate-event fetches — drop excess, not queue
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

  // ── Playback state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [speed, setSpeed] = useState<string>("1x");

  // ── Strategy params state
  const [strategyParams, setStrategyParams] = useState({ ...DEFAULT_STRATEGY_PARAMS });
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
  const availableYears = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"];

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

    // Clear backend replay cache when stop is clicked
    fetch(`${BASE_URL}/trading/replay/clear-cache`, { method: "POST" })
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
  }, [stopPlayback, replayData, setChartDataToIndex]);

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
      .catch(() => { });
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

    for (const t of agentTrades) {
      const entryTs = t.entry_time ?? 0;
      if (entryTs <= candle.time) {
        total++;
        const typeLower = t.type.toLowerCase();
        const lotSize = t.lot_size;
        const entryPrice = t.entry_price;
        const slPrice = t.sl;
        const tpPrice = t.tp;

        // Check candles since entryTs up to current candle.time
        const activeCandles = replayData.candles.filter(c => c.time >= entryTs && c.time <= candle.time);
        
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
          });
        }
      }
    }

    setRunningProfit(profit);
    setTradeStats({ total, wins, losses });
    setActivePositions(activePosList);

    // Also update chart markers
    if (tradesPrimitiveRef.current) {
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
          const activeCandles = replayData.candles.filter(c => c.time >= entryTs && c.time <= candle.time);
          let isClosed = false;
          let exitPrice = null;
          let exitTime = null;
          let finalProfit = 0;

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
  }, [strategyParams, replayData, currentIndex, agentTrades]);



  // ── Load Data ────────────────────────────────────────────────────────────

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
      setAgentTrades([]);
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
          const activeCandles = replayData.candles.filter(c => c.time >= entryTs && c.time <= candle.time);
          let isClosed = false;
          let exitPrice = null;
          let exitTime = null;
          let finalProfit = 0;

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
      tradesPrimitiveRef.current.setTimeframe("M15");
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
        total++;
        const typeLower = t.type.toLowerCase();
        const lotSize = t.lot_size;
        const entryPrice = t.entry_price;
        const slPrice = t.sl;
        const tpPrice = t.tp;

        // Check candles since entryTs up to current candle.time
        const activeCandles = replayData.candles.filter(c => c.time >= entryTs && c.time <= candle.time);
        
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
          });
        }
      }
    }
    setRunningProfit(profit);
    setTradeStats({ total, wins, losses });
    setActivePositions(activePosList);

    return idx + 1;
  }, [strategyParams, simSignals, agentTrades, replayData]);

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
      // No valid trigger — clear frame only if it's stale
      if (activeFrame && activeFrame.event_time !== latestEvent.time) setActiveFrame(null);
      return;
    }

    const cacheKey = `${latestEvent.time}_${latestEvent.type}`;

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

      const url = `${BASE_URL}/trading/simulate-event?time=${latestEvent.time}&timeframe=${activeTimeframe}&type=${latestEvent.type}`;
      fetch(url, { signal: controller.signal })
        .then(res => {
          if (!res.ok) throw new Error("Failed to fetch event simulation");
          return res.json();
        })
        .then(frame => {
          completedSimTimesRef.current.add(cacheKey);
          setSimFramesMap(prev => ({ ...prev, [cacheKey]: frame }));
          // Counter-swing events (e.g. LL after Bullish CHoCH+HH, HH after Bearish CHoCH+LL)
          // should NOT update the Agent Consensus panel — keep warm-up values frozen.
          if (!frame?.is_counter_swing) {
            setActiveFrame(frame);
          }
          setIsFrameLoading(false);

          // Add marker and dynamic position when a new tradeable signal is approved by agent
          if (frame && frame.approved && ["BUY", "SELL"].includes(frame.final_signal)) {
            setSimSignals(prev => {
              if (prev.some(s => s.time === frame.event_time)) return prev;
              return [...prev, {
                time: frame.event_time,
                signal: frame.final_signal,
              }];
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
              }];
            });
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
  }, [currentCandle, replayData, activeTimeframe, simFramesMap, orchestratorEnabled, activeFrame]);

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div
      className="flex flex-col size-full text-[var(--text-primary)]"
      style={{ background: "var(--bg-primary, #0f172a)", paddingLeft: "250px", overflow: "hidden" }}
    >
      {/* ── Header ── */}
      <div
        className="flex items-center justify-between px-6 py-4 border-b backdrop-blur-md bg-[rgba(15,23,42,0.45)]"
        style={{ borderColor: "rgba(59,130,246,0.15)", boxShadow: "0 4px 30px rgba(0,0,0,0.2)" }}
      >
        <h1 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-purple-500 bg-clip-text text-transparent flex-shrink-0">
          🎬 Replay Trades
        </h1>

        {/* Filter controls + Playback Controls */}
        <div className="flex items-center gap-2 flex-nowrap flex-1 justify-end ml-4 min-w-0 overflow-x-auto whitespace-nowrap">
          {/* If replayData is loaded, render playback controls FIRST! */}
          {replayData && (
            <>
              {/* Rewind */}
              <button
                onClick={handlePrev}
                disabled={isPlaying || currentIndex <= 0}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold text-xs transition-all duration-150 active:scale-95 disabled:opacity-40 cursor-pointer"
                style={{
                  background: "rgba(167,139,250,0.15)",
                  color: "#a78bfa",
                  border: "1px solid rgba(167,139,250,0.3)",
                }}
              >
                <Rewind size={12} />
                Rewind
              </button>

              {/* Play / Pause */}
              <button
                onClick={isPlaying ? stopPlayback : startPlayback}
                disabled={currentIndex >= totalCandles}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold text-xs transition-all duration-150 active:scale-95 disabled:opacity-40 cursor-pointer"
                style={{
                  background: isPlaying ? "rgba(248,113,113,0.15)" : "rgba(34,211,238,0.15)",
                  color: isPlaying ? "#f87171" : "#22d3ee",
                  border: `1px solid ${isPlaying ? "rgba(248,113,113,0.3)" : "rgba(34,211,238,0.3)"}`,
                }}
              >
                {isPlaying ? <Pause size={12} /> : <Play size={12} />}
                {isPlaying ? "Pause" : "Play"}
              </button>

              {/* Next */}
              <button
                onClick={handleNext}
                disabled={isPlaying || currentIndex >= totalCandles}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold text-xs transition-all duration-150 active:scale-95 disabled:opacity-40 cursor-pointer"
                style={{
                  background: "rgba(167,139,250,0.15)",
                  color: "#a78bfa",
                  border: "1px solid rgba(167,139,250,0.3)",
                }}
              >
                <SkipForward size={12} />
                Next
              </button>

              {/* Stop */}
              <button
                onClick={handleStop}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold text-xs transition-all duration-150 active:scale-95 hover:bg-[rgba(239,68,68,0.2)] cursor-pointer"
                style={{
                  background: "rgba(239,68,68,0.12)",
                  color: "#ef4444",
                  border: "1px solid rgba(239,68,68,0.25)",
                }}
              >
                <Square size={12} />
                Stop
              </button>

              {/* Speed */}
              <div className="flex items-center gap-1.5 ml-1">
                <span className="text-xs text-[var(--text-secondary,#94a3b8)]">Speed:</span>
                <div className="inline-flex p-0.5 bg-[rgba(15,23,42,0.6)] border border-slate-800/60 rounded-lg overflow-hidden">
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

              {/* Legend */}
              <div className="flex items-center gap-2 ml-1 text-xs">
                {Object.entries(STRUCTURE_COLORS).map(([k, c]) => (
                  <span key={k} className="flex items-center gap-0.5">
                    <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: c }} />
                    <span className="text-[10px] scale-90 origin-left">{k}</span>
                  </span>
                ))}
                <span className="flex items-center gap-0.5">
                  <span className="w-3 h-0.5 inline-block" style={{ background: "#facc15" }} />
                  <span className="text-[10px] scale-90 origin-left">EMA200</span>
                </span>
              </div>

              {/* Vertical separator */}
              <div className="w-[1px] h-6 bg-slate-800/60 self-center" />
            </>
          )}

          <div className="flex items-center gap-2">
            {/* Timeframe selector (tiru 100% dari page trades) */}
            <div className="flex items-center gap-2 mr-2">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-secondary,#94a3b8)]">Timeframe</span>
              <div className="inline-flex p-0.5 bg-[rgba(15,23,42,0.6)] border border-slate-800/60 rounded-lg overflow-hidden">
                {["M15", "H1", "H4"].map((tf) => (
                  <button
                    key={tf}
                    disabled={isLoading}
                    onClick={() => handleTimeframeChange(tf)}
                    className={cn(
                      "px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-200 active:scale-95 cursor-pointer disabled:opacity-40",
                      tf === activeTimeframe
                        ? "bg-[rgba(6,182,212,0.2)] text-cyan-400 border border-cyan-500/25"
                        : "text-slate-400 hover:text-white"
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
              className="inline-flex items-center justify-center px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer border transition-all duration-200 active:scale-95 outline-none hover:bg-[rgba(255,255,255,0.08)] hover:border-[rgba(255,255,255,0.25)] hover:text-white"
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
        {replayData && (
          <div
            className="flex items-center justify-between gap-4 px-5 py-2.5 border border-slate-800/80 rounded-xl bg-slate-900/40 backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]"
          >
            <div className="flex items-center gap-4 flex-wrap">
              {/* Date Range */}
              <div className="flex flex-col">
                <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Rentang Tanggal</span>
                <span className="text-xs font-semibold text-slate-300">
                  {replayData.meta.date_from} → {replayData.meta.date_to}
                </span>
              </div>

              <div className="w-px h-4 bg-slate-800/60 self-center" />

              {/* Candles */}
              <div className="flex flex-col">
                <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Lilin (Candles)</span>
                <span className="text-xs font-semibold text-slate-300 font-mono">
                  <span className="text-cyan-400">{currentIndex}</span>/{totalCandles}
                </span>
              </div>

              <div className="w-px h-4 bg-slate-800/60 self-center" />

              {/* PnL */}
              <div className="flex flex-col">
                <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Total P&L</span>
                <span className={cn(
                  "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-bold font-mono border",
                  runningProfit > 0
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : runningProfit < 0
                      ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                      : "bg-slate-800/40 text-slate-400 border-slate-800/60"
                )}>
                  {runningProfit >= 0 ? "+" : ""}{runningProfit.toFixed(2)}
                </span>
              </div>

              <div className="w-px h-4 bg-slate-800/60 self-center" />

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

              <div className="w-px h-4 bg-slate-800/60 self-center" />

              {/* Trades */}
              <div className="flex flex-col">
                <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">Transaksi (Trades)</span>
                <span className="text-xs font-semibold text-slate-200 font-mono">
                  {tradeStats.total} <span className="text-slate-500 text-[10px] ml-1">({tradeStats.wins}W / {tradeStats.losses}L)</span>
                </span>
              </div>
            </div>

            {/* Current Playhead Time */}
            {currentCandle && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-purple-500/8 border border-purple-500/20 shadow-[0_0_10px_rgba(168,85,247,0.1)] text-xs font-semibold text-purple-300 font-mono">
                <span>🕒</span>
                <span>{new Date(currentCandle.time * 1000).toISOString().slice(0, 16).replace("T", " ")}</span>
              </div>
            )}
          </div>
        )}

        {/* ── Orchestrator Simulation ── */}
        {simLoading && (
          <p className="text-sm text-[var(--text-secondary)] mt-2">⏳ Running Orchestrator Simulation…</p>
        )}
        {simError && (
          <div className="mt-2 px-3 py-2 rounded-lg bg-red-900/30 border border-red-500/30 text-red-400 text-sm">
            ⚠️ {simError}
          </div>
        )}
        {simMetrics && simMetrics.total_signals > 0 && (
          <div className="mt-3 p-3 rounded-lg bg-[rgba(59,130,246,0.08)] border border-[rgba(59,130,246,0.25)]">
            <p className="text-sm font-semibold text-[var(--neon-blue)] mb-2">🧠 Orchestrator Simulation</p>
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
          <p className="text-sm text-[var(--text-secondary)] mt-2">🧠 Orchestrator Simulation: No signals.</p>
        )}

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

          <div
            ref={chartContainerRef}
            className="w-full h-full rounded-lg overflow-hidden"
            style={{ background: "rgba(15,23,42,0.5)" }}
          />
        </div>

        {/* ── Agent Consensus (100% Copy of Dashboard Layout, bound to activeFrame) ── */}
        <div className="glass-card mt-4">
          <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
            <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: 0 }}>🤖 Agent Consensus</h2>
            {isFrameLoading && (
              <span className="text-xs text-cyan-400 animate-pulse flex items-center gap-1.5 bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded-full">
                <Loader2 className="size-3 animate-spin" />
                Calculating...
              </span>
            )}
          </div>

          {replayData && activeFrame ? (
            <>
              {AGENT_PANEL_DEFS.map((def) => {
                const agent = activeFrame.agents[def.key] as SimAgentState | undefined;
                if (!agent) return null;
                const prediction = agent.signal || 'HOLD';
                const confidence = agent.confidence ?? 0;

                return (
                  <div
                    key={def.key}
                    className="agent-row hover:bg-slate-800/30 cursor-pointer rounded-xl p-1.5 transition-all duration-200"
                    onClick={() => {
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
                    <div className="agent-info">
                      <div className="agent-icon" style={{ background: def.bg, borderColor: def.color }}>
                        {def.icon}
                      </div>
                      <div className="agent-details">
                        <div className="agent-name">{def.name}</div>
                        <div className="agent-signal">
                          Signal: <span className="neon-text">{prediction}</span>
                        </div>
                      </div>
                    </div>
                    <div style={{ minWidth: '100px' }}>
                      <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>
                        Confidence
                      </div>
                      <div className="progress-bar" style={{ width: '100px' }}>
                        <div className="progress-fill" style={{ width: `${Math.min(100, Math.max(0, confidence * 100))}%` }}></div>
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Consensus Summary */}
              <div style={{ marginTop: '20px', padding: '16px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600 }}>Overall Consensus</span>
                  <span style={{ fontSize: '18px', fontWeight: 700, color: 'var(--neon-amber)' }}>
                    {activeFrame.final_signal || 'HOLD'}
                  </span>
                </div>
                <div className="progress-bar" style={{ marginTop: '12px' }}>
                  <div
                    className="progress-fill"
                    style={{
                      width: `${Math.min(100, Math.max(0, (activeFrame.consensus_confidence ?? 0) * 100))}%`,
                      background: 'linear-gradient(90deg, var(--neon-amber), var(--neon-ruby))'
                    }}
                  ></div>
                </div>
                <div className="text-xs text-[var(--text-tertiary)] mt-2">
                  {activeFrame.consensus_level
                    ? `${activeFrame.consensus_level} (${Math.round((activeFrame.consensus_confidence ?? 0) * 100)}%)`
                    : "—"}
                </div>
              </div>
            </>
          ) : (
            <p style={{ color: 'var(--text-secondary)' }}>No consensus data available (Start replay to view)</p>
          )}
        </div>

        {/* ── Strategy Params Panel ── */}
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
              className="w-full flex items-center justify-between text-base font-bold text-slate-100 hover:text-white transition-colors focus:outline-none cursor-pointer"
            >
              <div className="flex items-center gap-2.5">
                <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/25">
                  ⚙️
                </span>
                <span>Strategy Settings & Parameters</span>
              </div>
              <span className="text-slate-400 text-xs font-semibold px-2 py-1 rounded bg-slate-850/50 border border-slate-800/80">
                {isStrategyPanelOpen ? "Tutup Panel ▲" : "Buka Panel ▼"}
              </span>
            </button>

            {isStrategyPanelOpen && (
              <div className="mt-5 space-y-6">
                {/* Load existing scenario */}
                {scenarios.length > 0 && (
                  <div className="p-3.5 rounded-lg bg-slate-900/30 border border-slate-800/60 flex flex-col gap-2">
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Muat Skenario Tersimpan</span>
                    <div className="flex items-center gap-2 flex-wrap">
                      {scenarios.map((sc: any) => (
                        <div key={sc.id} className="flex items-center gap-1 bg-cyan-500/5 hover:bg-cyan-500/10 border border-cyan-500/20 hover:border-cyan-500/40 rounded-lg pl-3 pr-1 py-1 transition-all">
                          <button
                            onClick={() => {
                              setStrategyParams({
                                trailing_distance: sc.trailing_distance,
                                tp_trigger: sc.tp_trigger,
                                tp_ekspansi: sc.tp_ekspansi,
                                max_ekspansi: sc.max_ekspansi,
                                enable_breakeven: sc.enable_breakeven,
                                breakeven_trigger: sc.breakeven_trigger,
                                breakeven_buffer: sc.breakeven_buffer,
                                lot_override: sc.lot_override ?? 0.00,
                                initial_sl_dist: sc.initial_sl_dist ?? DEFAULT_STRATEGY_PARAMS.initial_sl_dist,
                                initial_tp_dist: sc.initial_tp_dist ?? DEFAULT_STRATEGY_PARAMS.initial_tp_dist,
                                sl_min_distance: sc.sl_min_distance ?? DEFAULT_STRATEGY_PARAMS.sl_min_distance,
                                sl_safety_buffer: sc.sl_safety_buffer ?? DEFAULT_STRATEGY_PARAMS.sl_safety_buffer,
                              });
                              setScenarioName(sc.name);
                            }}
                            className="text-xs font-semibold text-cyan-400 cursor-pointer focus:outline-none"
                          >
                            {sc.name}
                          </button>
                          <button
                            onClick={async (e) => {
                              e.stopPropagation();
                              try {
                                const res = await fetch(`${BASE_URL}/scenarios/${sc.id}`, { method: "DELETE" });
                                if (res.ok) {
                                  setScenarios(prev => prev.filter(item => item.id !== sc.id));
                                  if (scenarioName === sc.name) {
                                    setScenarioName("");
                                    setStrategyParams({ ...DEFAULT_STRATEGY_PARAMS });
                                  }
                                }
                              } catch { }
                            }}
                            className="w-5 h-5 rounded flex items-center justify-center text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-all cursor-pointer text-[10px] font-bold"
                            title="Hapus skenario"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Parameters Grid layout */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Section A: Stop Loss & Break Even */}
                  <div className="p-4 rounded-xl bg-slate-900/20 border border-slate-800/40 space-y-4">
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800/50 pb-2">🛡️ Stop Loss & Break-Even</h3>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">Trailing SL (USD) <StrategyTooltip fungsi="Jarak Stop Loss dinamis yang menyeret naik (BUY) / turun (SELL) mengikuti harga tertinggi/terendah baru." contoh="Jarak 3.00 USD. Entry BUY di 2000.00. Jika harga naik ke 2005.00, SL terseret naik ke 2002.00. Jika harga turun, SL tetap diam di 2002.00." /></label>
                        <input
                          type="number"
                          step={1}
                          min={0.1}
                          value={strategyParams.trailing_distance}
                          onChange={e => setStrategyParams(p => ({ ...p, trailing_distance: parseFloat(e.target.value) || 0.1 }))}
                          className="bg-slate-950/60 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3 py-1.5 font-mono text-cyan-300 focus:outline-none transition-all w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">Break-Even State <StrategyTooltip fungsi="Mengaktifkan pemindahan SL otomatis ke level aman (di atas entry) ketika target profit tercapai." contoh="Aktif -> Mengunci resiko transaksi menjadi nol setelah harga bergerak menguntungkan." /></label>
                        <button
                          onClick={() => setStrategyParams(p => ({ ...p, enable_breakeven: !p.enable_breakeven }))}
                          className="w-full py-1.5 rounded-lg text-xs font-bold border transition-all cursor-pointer"
                          style={{
                            background: strategyParams.enable_breakeven ? "rgba(34,197,94,0.08)" : "rgba(255,255,255,0.02)",
                            borderColor: strategyParams.enable_breakeven ? "rgba(34,197,94,0.3)" : "rgba(255,255,255,0.06)",
                            color: strategyParams.enable_breakeven ? "#4ade80" : "#94a3b8",
                          }}
                        >
                          {strategyParams.enable_breakeven ? "✓ BE Aktif" : "✗ BE Nonaktif"}
                        </button>
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">BE Trigger (USD Profit) <StrategyTooltip fungsi="Target profit minimum (jarak dari entry) yang harus dicapai agar SL dipindahkan ke Break-Even." contoh="Trigger 15.00 USD. Entry BUY di 2000.00. BE baru terpicu saat harga menyentuh 2015.00." /></label>
                        <input
                          type="number"
                          step={1}
                          min={0.1}
                          disabled={!strategyParams.enable_breakeven}
                          value={strategyParams.breakeven_trigger}
                          onChange={e => setStrategyParams(p => ({ ...p, breakeven_trigger: parseFloat(e.target.value) || 0.1 }))}
                          className="bg-slate-950/60 disabled:opacity-30 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3 py-1.5 font-mono text-cyan-300 focus:outline-none transition-all w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">BE Buffer (USD) <StrategyTooltip fungsi="Jarak aman untuk meletakkan SL di atas harga entry (BUY) atau di bawah harga entry (SELL)." contoh="Buffer 1.00 USD. Entry BUY di 2000.00. Saat BE terpicu, SL dikunci di level aman 2001.00." /></label>
                        <input
                          type="number"
                          step={0.1}
                          min={0}
                          disabled={!strategyParams.enable_breakeven}
                          value={strategyParams.breakeven_buffer}
                          onChange={e => setStrategyParams(p => ({ ...p, breakeven_buffer: parseFloat(e.target.value) || 0 }))}
                          className="bg-slate-950/60 disabled:opacity-30 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3 py-1.5 font-mono text-cyan-300 focus:outline-none transition-all w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">SL Min Distance (USD) <StrategyTooltip fungsi="Batas minimal jarak SL awal (LL/HH) ke harga entry. Jika jarak aktual kurang dari nilai ini, maka SL dipasang di SL_lama - safety_buffer (untuk BUY)." contoh="Min Distance 5.00 USD. Jika jarak Entry ke LL/HH kurang dari 5.00 USD (500 poin), maka aturan safety buffer akan aktif." /></label>
                        <input
                          type="number"
                          step={1}
                          min={0.1}
                          value={strategyParams.sl_min_distance}
                          onChange={e => setStrategyParams(p => ({ ...p, sl_min_distance: parseFloat(e.target.value) || 0.1 }))}
                          className="bg-slate-950/60 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3 py-1.5 font-mono text-cyan-300 focus:outline-none transition-all w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">SL Safety Buffer (USD) <StrategyTooltip fungsi="Buffer/jarak tambahan yang dikurangkan dari LL (BUY) atau ditambahkan ke HH (SELL) jika SL awal terlalu dekat." contoh="Safety Buffer 10.00 USD. Jika jarak LL ke Entry hanya 1.50 USD (di bawah 5.00 USD), maka SL baru dipasang di LL - 10.00 USD." /></label>
                        <input
                          type="number"
                          step={0.1}
                          min={0}
                          value={strategyParams.sl_safety_buffer}
                          onChange={e => setStrategyParams(p => ({ ...p, sl_safety_buffer: parseFloat(e.target.value) || 0 }))}
                          className="bg-slate-950/60 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3 py-1.5 font-mono text-cyan-300 focus:outline-none transition-all w-full"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Section B: Take Profit & Lot Override */}
                  <div className="p-4 rounded-xl bg-slate-900/20 border border-slate-800/40 space-y-4">
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800/50 pb-2">🎯 Take Profit & Volume</h3>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">Initial SL (USD Jarak) <StrategyTooltip fungsi="Jarak SL awal kustom sejak pembukaan transaksi baru (0 = pakai SL asli database)." contoh="Jarak 3.00 USD. Entry BUY di 2000.00. SL awal langsung terpasang di 1997.00." /></label>
                        <input
                          type="number"
                          step={1}
                          min={0}
                          value={strategyParams.initial_sl_dist}
                          onChange={e => setStrategyParams(p => ({ ...p, initial_sl_dist: parseFloat(e.target.value) || 0 }))}
                          className="bg-slate-950/60 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3 py-1.5 font-mono text-cyan-300 focus:outline-none transition-all w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">Initial TP (USD Jarak) <StrategyTooltip fungsi="Jarak TP awal kustom sejak pembukaan transaksi baru (0 = pakai TP asli database)." contoh="Jarak 30.00 USD. Entry BUY di 2000.00. TP awal langsung terpasang di 2030.00." /></label>
                        <input
                          type="number"
                          step={1}
                          min={0}
                          value={strategyParams.initial_tp_dist}
                          onChange={e => setStrategyParams(p => ({ ...p, initial_tp_dist: parseFloat(e.target.value) || 0 }))}
                          className="bg-slate-950/60 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3 py-1.5 font-mono text-cyan-300 focus:outline-none transition-all w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">TP Trigger (USD Jarak) <StrategyTooltip fungsi="Batas jarak harga berjalan mendekati TP aktif sebelum memicu ekspansi (pelebaran) TP baru." contoh="Trigger 10.00 USD. TP aktif di 2030.00. Jika harga naik mendekati TP ke level 2020.00, ekspansi TP akan berjalan." /></label>
                        <input
                          type="number"
                          step={1}
                          min={0.1}
                          value={strategyParams.tp_trigger}
                          onChange={e => setStrategyParams(p => ({ ...p, tp_trigger: parseFloat(e.target.value) || 0.1 }))}
                          className="bg-slate-950/60 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3 py-1.5 font-mono text-cyan-300 focus:outline-none transition-all w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">TP Ekspansi (USD) <StrategyTooltip fungsi="Jarak pelebaran target profit baru ketika TP Trigger tersentuh." contoh="Ekspansi 20.00 USD. TP aktif di 2030.00 akan diundur sejauh 20.00 USD ke 2050.00 saat harga mendekat." /></label>
                        <input
                          type="number"
                          step={1}
                          min={0.1}
                          value={strategyParams.tp_ekspansi}
                          onChange={e => setStrategyParams(p => ({ ...p, tp_ekspansi: parseFloat(e.target.value) || 0.1 }))}
                          className="bg-slate-950/60 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3 py-1.5 font-mono text-cyan-300 focus:outline-none transition-all w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">Max Ekspansi (0=∞) <StrategyTooltip fungsi="Batasan berapa kali target TP boleh diperluas/ekspansi." contoh="Setel 2. TP hanya bisa mundur/bertambah jauh sebanyak maksimal 2 kali. Setel 0 untuk ekspansi tidak terbatas." /></label>
                        <input
                          type="number"
                          step={1}
                          min={0}
                          value={strategyParams.max_ekspansi}
                          onChange={e => setStrategyParams(p => ({ ...p, max_ekspansi: parseInt(e.target.value) || 0 }))}
                          className="bg-slate-950/60 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3 py-1.5 font-mono text-cyan-300 focus:outline-none transition-all w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-slate-400 font-medium">Lot Override (0=Auto) <StrategyTooltip fungsi="Mengubah volume ukuran lot transaksi secara manual untuk simulasi PnL kustom." contoh="Lot 0.10. Semua transaksi akan disimulasikan menggunakan ukuran 0.10 lot, mengesampingkan lot asli dari database." /></label>
                        <input
                          type="number"
                          step={0.01}
                          min={0}
                          value={strategyParams.lot_override}
                          onChange={e => setStrategyParams(p => ({ ...p, lot_override: parseFloat(e.target.value) || 0 }))}
                          className="bg-slate-950/60 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3 py-1.5 font-mono text-cyan-300 focus:outline-none transition-all w-full"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Save scenario form actions */}
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-4 border-t border-slate-800/40">
                  <input
                    type="text"
                    placeholder="Nama skenario baru (misal: Trailing 2000 + BE)..."
                    value={scenarioName}
                    onChange={e => setScenarioName(e.target.value)}
                    className="flex-1 bg-slate-950/50 border border-slate-800 focus:border-cyan-500/40 rounded-lg px-3.5 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none transition-all"
                  />
                  <div className="flex items-center gap-2">
                    <button
                      disabled={!scenarioName.trim()}
                      onClick={async () => {
                        if (!scenarioName.trim()) return;
                        try {
                          const res = await fetch(`${BASE_URL}/scenarios`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ name: scenarioName.trim(), ...strategyParams }),
                          });
                          if (res.ok) {
                            const saved = await res.json();
                            setScenarios(prev => [saved, ...prev]);
                            setScenarioName("");
                          }
                        } catch { }
                      }}
                      className="px-4 py-2 rounded-lg text-xs font-bold border cursor-pointer transition-all disabled:opacity-40"
                      style={{
                        background: "rgba(6, 182, 212, 0.12)",
                        borderColor: "rgba(6, 182, 212, 0.35)",
                        color: "#67e8f9",
                        boxShadow: "0 0 10px rgba(6, 182, 212, 0.1)"
                      }}
                    >
                      💾 Simpan Skenario
                    </button>
                    <button
                      onClick={() => {
                        setStrategyParams({ ...DEFAULT_STRATEGY_PARAMS });
                        setScenarioName("");
                      }}
                      className="px-4 py-2 rounded-lg text-xs font-bold border border-slate-800 hover:bg-slate-800/30 text-slate-400 hover:text-slate-300 transition-all cursor-pointer"
                    >
                      Reset
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Active Positions Panel ── */}
        {replayData && (
          <div className="glass-card flex-shrink-0">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <span className="animate-pulse w-2.5 h-2.5 rounded-full bg-cyan-400 inline-block"></span>
              ⚡ Daftar Posisi
            </h2>

            {activePositions.length === 0 ? (
              <div className="py-8 text-center text-slate-400 text-sm bg-slate-900/20 rounded-lg border border-slate-800/40">
                Tidak ada posisi saat ini
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-800/50">
                <table className="min-w-full divide-y divide-slate-800/60 bg-slate-900/10">
                  <thead className="bg-slate-900/40 text-slate-400 text-[11px] font-semibold tracking-wider uppercase">
                    <tr>
                      <th className="py-3 px-4 text-left">Ticket</th>
                      <th className="py-3 px-4 text-left">Type</th>
                      <th className="py-3 px-4 text-right">Lot</th>
                      <th className="py-3 px-4 text-right">Entry Price</th>
                      <th className="py-3 px-4 text-right">Current Price</th>
                      <th className="py-3 px-4 text-right">SL (Orig → Curr)</th>
                      <th className="py-3 px-4 text-right">TP (Orig → Curr)</th>
                      <th className="py-3 px-4 text-left">Triggers (BE | TP-Ex)</th>
                      <th className="py-3 px-4 text-center">Status</th>
                      <th className="py-3 px-4 text-right">Floating PnL</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-200 text-xs font-medium">
                    {activePositions.map((pos) => {
                      const isWin = pos.pnl >= 0;
                      const isBuy = pos.type === "BUY";

                      const hasSLChanged = pos.sl && pos.original_sl && Math.abs(pos.sl - pos.original_sl) > 0.01;
                      const hasTPChanged = pos.tp && pos.original_tp && Math.abs(pos.tp - pos.original_tp) > 0.01;

                      // Status Badge Classes
                      let badgeClass = "bg-slate-800/40 text-slate-400 border border-slate-700/30";
                      if (pos.status === "BE + TP Expanded") {
                        badgeClass = "bg-fuchsia-500/15 text-fuchsia-400 border border-fuchsia-500/30 shadow-[0_0_8px_rgba(217,70,239,0.15)]";
                      } else if (pos.status === "Break-Even") {
                        badgeClass = "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shadow-[0_0_8px_rgba(16,185,129,0.15)]";
                      } else if (pos.status === "TP Expanded") {
                        badgeClass = "bg-amber-500/15 text-amber-400 border border-amber-500/30 shadow-[0_0_8px_rgba(245,158,11,0.15)]";
                      } else if (pos.status === "Trailing") {
                        badgeClass = "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 shadow-[0_0_8px_rgba(6,182,212,0.15)]";
                      } else if (pos.status === "Closed - Win") {
                        badgeClass = "bg-green-500/15 text-green-400 border border-green-500/30 shadow-[0_0_8px_rgba(34,197,94,0.15)]";
                      } else if (pos.status === "Closed - Loss") {
                        badgeClass = "bg-red-500/15 text-red-400 border border-red-500/30 shadow-[0_0_8px_rgba(239,68,68,0.15)]";
                      }

                      return (
                        <tr key={pos.ticket} className="hover:bg-slate-800/20 transition-colors">
                          <td className="py-3.5 px-4 font-mono text-slate-400">#{pos.ticket}</td>
                          <td className="py-3.5 px-4">
                            <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${isBuy
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                              : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                              }`}>
                              {pos.type}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono">{pos.lot_size.toFixed(2)}</td>
                          <td className="py-3.5 px-4 text-right font-mono">${pos.entry_price.toFixed(2)}</td>
                          <td className="py-3.5 px-4 text-right font-mono">${pos.current_price.toFixed(2)}</td>
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
                          </td>
                          <td className="py-3.5 px-4 text-center">
                            <span className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold transition-all duration-300 ${badgeClass}`}>
                              {pos.status}
                            </span>
                          </td>
                          <td className={`py-3.5 px-4 text-right font-mono font-bold text-sm ${isWin ? "text-emerald-400" : "text-rose-500"
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
                      <td className={`px-4 py-3.5 whitespace-nowrap font-semibold ${(month.win_rate ?? 0) > 50
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
        <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center z-[200] animate-in fade-in duration-300">
          <div 
            className="bg-slate-900/90 border border-purple-500/25 rounded-2xl p-6 w-96 shadow-[inset_0_1px_0_rgba(255,255,255,0.1),_0_25px_60px_rgba(0,0,0,0.8),_0_0_45px_rgba(168,85,247,0.18)] transform perspective-1000 rotate-x-6 animate-in zoom-in-90 duration-350 ease-out"
            style={{ transformStyle: "preserve-3d" }}
          >
            <div className="flex flex-col items-center justify-center text-center mb-5">
              <div className="relative flex items-center justify-center w-12 h-12 mb-3 bg-purple-500/10 rounded-full border border-purple-500/25 shadow-[0_0_15px_rgba(168,85,247,0.2)]">
                <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
              </div>
              <div className="text-purple-300 font-semibold text-xs tracking-wider uppercase mb-1">
                Loading Replay Data
              </div>
              <div className="text-3xl font-mono font-bold text-white mb-1 shadow-sm">
                {loadProgress.percent}%
              </div>
              <div className="text-[10px] font-medium text-slate-400 max-w-[240px] truncate">{loadProgress.step}</div>
            </div>
            <div className="w-full h-3 bg-slate-950/80 border border-slate-800/40 rounded-full shadow-[inset_0_2px_4px_rgba(0,0,0,0.8)] relative overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-500 via-fuchsia-500 to-cyan-500 rounded-full transition-all duration-150 shadow-[0_0_12px_rgba(168,85,247,0.5)] relative overflow-hidden"
                style={{ width: `${loadProgress.percent}%` }}
              >
                {/* cylindrical light reflection gloss overlay */}
                <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.15),transparent)]" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Transaction Detail Pop-up Modal (100% Identical to trades.tsx) ── */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xl animate-in fade-in duration-200">
          <div className="w-full max-w-4xl bg-slate-900/90 border border-slate-800 rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200 relative">
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
                        <thead className="bg-slate-900/60 border-b border-slate-800 text-slate-400 text-xs uppercase font-semibold">
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
                                <tr key={trade.ticket} className="hover:bg-slate-800/30 transition-colors">
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

      {/* ── Agent Detail Pop-up Modal ── */}
      {isAgentModalOpen && selectedAgent && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xl animate-in fade-in duration-200">
          <div className="w-[96vw] max-w-[96vw] bg-slate-900/90 border border-slate-800 rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden flex flex-col max-h-[135vh] h-[135vh] animate-in zoom-in-95 duration-200 relative">
            {/* Premium Gradient Top Accent Line */}
            <div
              className="absolute top-0 left-0 w-full h-[3px]"
              style={{ background: `linear-gradient(90deg, ${selectedAgent.color}, #6366f1)` }}
            />

            {/* Header */}
            <div className="p-6 pt-7 border-b border-slate-800 flex items-center justify-between bg-slate-900/40">
              <div className="flex items-center gap-3">
                <div
                  className="p-2.5 rounded-xl text-lg border"
                  style={{ background: selectedAgent.bg, borderColor: selectedAgent.color }}
                >
                  {selectedAgent.icon}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-100 tracking-tight">
                    {selectedAgent.name}
                  </h3>
                  <p className="text-xs text-slate-400">
                    Detail analisis dan kondisi agen saat simulasi dibentuk
                  </p>
                </div>
              </div>
              <button
                onClick={() => { setIsAgentModalOpen(false); setSelectedPattern(null); }}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all cursor-pointer hover:scale-105 active:scale-95 duration-150"
                title="Tutup"
              >
                <X className="size-5" />
              </button>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Agent Status and Confidence Card */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-slate-950/30 border border-slate-800/60 rounded-xl p-4 flex flex-col justify-between">
                  <span className="text-xs text-slate-400 uppercase tracking-wider mb-2">Signal & Status</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xl font-bold text-slate-200">
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

                <div className="bg-slate-950/30 border border-slate-800/60 rounded-xl p-4 flex flex-col justify-between">
                  <span className="text-xs text-slate-400 uppercase tracking-wider mb-2">Confidence Level</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xl font-bold font-mono text-cyan-400">
                      {Math.round((selectedAgent.confidence ?? 0) * 100)}%
                    </span>
                    <div className="flex-1 progress-bar h-2 bg-slate-950/80 rounded-full overflow-hidden">
                      <div
                        className="progress-fill h-full bg-cyan-500"
                        style={{ width: `${Math.min(100, Math.max(0, (selectedAgent.confidence ?? 0) * 100))}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Specific Metadata Panel (e.g. LanceDB Pattern Matching for Market Structure) */}
              {selectedAgent.meta && (selectedAgent.meta.win_rate !== undefined || selectedAgent.meta.pattern_count !== undefined) && (
                <div className="bg-slate-950/20 border border-slate-800 rounded-xl p-5 space-y-4">
                  <h4 className="text-sm font-semibold text-slate-300">📊 Database LanceDB Pattern Matching</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-xs text-slate-400">Pola Serupa Terdeteksi</div>
                      <div className="text-lg font-bold font-mono text-slate-200 mt-1">
                        {selectedAgent.meta.pattern_count ?? 0} pola
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
                    <div className="pt-4 border-t border-slate-800/80 space-y-2">
                      <div className="text-xs font-semibold text-slate-400">10 Pola Historis Paling Mirip (Top 10):</div>
                      <div className="border border-slate-800/80 rounded-lg overflow-hidden bg-slate-950/40 text-xs">
                        <div className="overflow-x-auto max-h-[580px]">
                          <table className="w-full text-left">
                            <thead className="bg-slate-900/40 border-b border-slate-800/80 text-slate-400 font-semibold sticky top-0 backdrop-blur">
                              <tr>
                                <th className="py-2 px-3">Waktu (Timestamp)</th>
                                <th className="py-2 px-3">Sesi</th>
                                <th className="py-2 px-3 text-right">Hasil</th>
                                <th className="py-2 px-3 text-right">Profit</th>
                                <th className="py-2 px-3 text-right">Kemiripan</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/40 text-slate-300">
                              {selectedAgent.meta.patterns.map((p: any, idx: number) => {
                                const isWin = p.outcome?.toUpperCase() === "WIN";
                                return (
                                  <tr
                                    key={idx}
                                    className="hover:bg-slate-800/30 transition-colors cursor-pointer"
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
                                    <td className={`py-2 px-3 text-right font-mono font-semibold ${isWin ? "text-emerald-400" : "text-rose-500"}`}>
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

              {/* ── Nested Pattern Detail Popup ─────────────────────────────── */}
              {selectedPattern && (
                <div
                  className="fixed inset-0 z-[200] flex items-center justify-center"
                  onClick={() => setSelectedPattern(null)}
                >
                  <div
                    className="relative bg-[#0a0f1c] border border-slate-700/60 rounded-2xl p-6 shadow-2xl w-80 space-y-4"
                    onClick={e => e.stopPropagation()}
                  >
                    <button
                      onClick={() => setSelectedPattern(null)}
                      className="absolute top-3 right-3 text-slate-500 hover:text-slate-300 transition-colors"
                    >
                      <X size={14} />
                    </button>
                    <div className="text-sm font-semibold text-slate-200">Detail Pola Historis</div>
                    <div className="text-[11px] font-mono text-slate-500">
                      {selectedPattern.timestamp ? selectedPattern.timestamp.replace("T", " ").substring(0, 19) : "-"}
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <div className="text-slate-500 mb-0.5">Entry Price</div>
                        <div className="font-mono font-semibold text-slate-200">
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
                        <div className="text-slate-200">{selectedPattern.session || "-"}</div>
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
                  </div>
                </div>
              )}

              {/* Sentiment Agent News & Calendar Block */}
              {selectedAgent.key === "sentiment" && activeFrame && (
                <div className="space-y-4">
                  {/* News Headlines */}
                  <div className="bg-slate-950/20 border border-slate-800 rounded-xl p-5 space-y-3">
                    <h4 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                      📰 Berita Utama Pasar (Generasi LLM)
                    </h4>
                    {activeFrame.debug_news && activeFrame.debug_news.length > 0 ? (
                      <div className="space-y-2.5">
                        {activeFrame.debug_news.map((item: any, idx: number) => (
                          <div key={idx} className="bg-slate-950/40 border border-slate-800/60 rounded-xl p-3.5 flex flex-col gap-1 hover:border-slate-700/60 transition-colors">
                            <span className="text-sm text-slate-200 font-medium leading-snug">
                              {item.headline}
                            </span>
                            <span className="text-[10px] font-mono text-slate-500">
                              {item.timestamp ? item.timestamp.replace("T", " ").substring(0, 19) : "-"}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-slate-500 py-2.5 italic text-center bg-slate-950/40 rounded-xl border border-dashed border-slate-800">
                        Tidak ada data berita historis untuk tanggal ini.
                      </div>
                    )}
                  </div>

                  {/* Calendar Events */}
                  <div className="bg-slate-950/20 border border-slate-800 rounded-xl p-5 space-y-3">
                    <h4 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                      📅 Jadwal Rilis Data Ekonomi (Generasi LLM)
                    </h4>
                    {activeFrame.debug_events && activeFrame.debug_events.length > 0 ? (
                      <div className="border border-slate-800/80 rounded-xl overflow-hidden bg-slate-950/40 text-xs">
                        <table className="w-full text-left">
                          <thead className="bg-slate-900/40 border-b border-slate-800/80 text-slate-400 font-semibold">
                            <tr>
                              <th className="py-2.5 px-4">Nama Peristiwa / Data</th>
                              <th className="py-2.5 px-4 text-center">Dampak</th>
                              <th className="py-2.5 px-4 text-right">Waktu Rilis</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/40 text-slate-300">
                            {activeFrame.debug_events.map((item: any, idx: number) => {
                              const isHigh = item.impact?.toLowerCase() === "high";
                              return (
                                <tr key={idx} className="hover:bg-slate-800/20 transition-colors">
                                  <td className="py-2.5 px-4 font-medium text-slate-200">
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
                      <div className="text-xs text-slate-500 py-2.5 italic text-center bg-slate-950/40 rounded-xl border border-dashed border-slate-800">
                        Tidak ada peristiwa ekonomi terjadwal untuk tanggal ini.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Reasoning Block */}
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-slate-300">📝 Analisis & Rationale (Reasoning)</h4>
                <div className="bg-slate-950/40 border border-slate-800/80 rounded-xl p-4 text-sm text-slate-300 leading-relaxed font-sans min-h-[100px] whitespace-pre-wrap">
                  {selectedAgent.reasoning || "Tidak ada rincian analisis dari agen."}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-800 bg-slate-900/30 flex justify-end">
              <button
                onClick={() => { setIsAgentModalOpen(false); setSelectedPattern(null); }}
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
