import { useEffect, useRef, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import {
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  CandlestickSeries,
  LineSeries,
  LineStyle,
} from "lightweight-charts";
import { Play, Pause, SkipForward, Square, Loader2, Calendar, FileCode, Rewind } from "lucide-react";
import { followReplayPlayhead } from "./replay-chart";

// ── Types ────────────────────────────────────────────────────────────────────

interface StrategyOption {
  id: string;
  filename: string;
  label: string;
  path: string;
}

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

const API_BASE = "http://localhost:8000/api/v1";

export default function ReplayOriginal() {
  // Strategy selector state
  const [strategies, setStrategies] = useState<StrategyOption[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<string>("Dev_Bot_v12_GoldO.cs");
  
  // Date & Timeframe selector state
  const [yearFrom, setYearFrom] = useState<number>(2024);
  const [monthFrom, setMonthFrom] = useState<number>(1);
  const [yearTo, setYearTo] = useState<number>(2024);
  const [monthTo, setMonthTo] = useState<number>(1);
  const [timeframe, setTimeframe] = useState<string>("M15");

  // Data states
  const [candles, setCandles] = useState<ReplayCandle[]>([]);
  const [structures, setStructures] = useState<StructureEvent[]>([]);
  const [trades, setTrades] = useState<ReplayTrade[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Playback state
  const [playIndex, setPlayIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [speed, setSpeed] = useState<string>("3x");
  const timerRef = useRef<any>(null);

  // Chart References
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const emaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<any> | null>(null);

  // 1. Fetch available strategies list
  useEffect(() => {
    async function fetchStrategies() {
      try {
        const res = await fetch(`${API_BASE}/trading/strategies`);
        if (res.ok) {
          const data = await res.json();
          if (data.strategies && data.strategies.length > 0) {
            setStrategies(data.strategies);
            setSelectedStrategy(data.strategies[0].filename);
          }
        }
      } catch (err) {
        console.error("Failed to load strategies:", err);
      }
    }
    fetchStrategies();
  }, []);

  // 2. Fetch Replay Data for selected strategy & date
  const loadReplayData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setIsPlaying(false);
    if (timerRef.current) clearInterval(timerRef.current);

    try {
      const url = `${API_BASE}/trading/replay-original?strategy_file=${encodeURIComponent(
        selectedStrategy
      )}&year_from=${yearFrom}&month_from=${monthFrom}&year_to=${yearTo}&month_to=${monthTo}&timeframe=${timeframe}`;

      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);

      const data = await res.json();
      setCandles(data.candles || []);
      setStructures(data.structures || []);
      setTrades(data.trades || []);
      setPlayIndex(data.candles?.length ? 1 : 0);
    } catch (err: any) {
      console.error("Replay fetch error:", err);
      setError(err.message || "Failed to load replay data");
    } finally {
      setLoading(false);
    }
  }, [selectedStrategy, yearFrom, monthFrom, yearTo, monthTo, timeframe]);

  // 3. Initialize Chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(148, 163, 184, 0.05)" },
        horzLines: { color: "rgba(148, 163, 184, 0.05)" },
      },
      crosshair: {
        mode: 1,
      },
      timeScale: {
        borderColor: "rgba(148, 163, 184, 0.2)",
        timeVisible: true,
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const emaSeries = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      title: "EMA200",
    });

    const markersPlugin = createSeriesMarkers(series as any, []);

    chartRef.current = chart;
    seriesRef.current = series;
    emaSeriesRef.current = emaSeries;
    markersPluginRef.current = markersPlugin as any;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    const resizeObserver = new ResizeObserver(() => {
      handleResize();
    });

    if (chartContainerRef.current) {
      resizeObserver.observe(chartContainerRef.current);
    }

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      resizeObserver.disconnect();
      chart.remove();
    };
  }, []);

  // 4. Update Chart on PlayIndex change
  useEffect(() => {
    if (!seriesRef.current || !emaSeriesRef.current || candles.length === 0) return;

    const visibleCandles = candles.slice(0, playIndex);
    seriesRef.current.setData(visibleCandles as any);

    const emaData = visibleCandles
      .filter((c) => c.ema200 !== null)
      .map((c) => ({ time: c.time as any, value: c.ema200! }));
    emaSeriesRef.current.setData(emaData);

    if (visibleCandles.length > 0 && chartRef.current) {
      followReplayPlayhead(chartRef.current);
    }

    const currentMaxTime = visibleCandles.length > 0 ? visibleCandles[visibleCandles.length - 1].time : 0;
    
    // Create markers for trade entries
    const markers: SeriesMarker<any>[] = [];
    trades.forEach((t) => {
      if (t.entry_time && t.entry_time <= currentMaxTime) {
        const isBuy = t.type.toUpperCase().includes("BUY");
        markers.push({
          time: t.entry_time as any,
          position: isBuy ? "belowBar" : "aboveBar",
          color: isBuy ? "#22c55e" : "#ef4444",
          shape: isBuy ? "arrowUp" : "arrowDown",
          text: `${t.type} @ ${t.entry_price}`,
        });
      }
    });

    if (markersPluginRef.current) {
      markersPluginRef.current.setMarkers(markers);
    }
  }, [playIndex, candles, trades]);

  // 5. Playback Loop Control
  useEffect(() => {
    if (isPlaying) {
      const intervalMs = SPEED_MAP[speed] || 100;
      timerRef.current = setInterval(() => {
        setPlayIndex((prev) => {
          if (prev >= candles.length) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, intervalMs);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, speed, candles.length]);

  // Performance metrics calculation
  const currentReplayTime = playIndex > 0 ? candles[playIndex - 1]?.time ?? null : null;
  const completedTrades = currentReplayTime === null
    ? []
    : trades.filter((trade) => trade.exit_time !== null && trade.exit_time <= currentReplayTime);
  const totalTradesCount = completedTrades.length;
  const winningTrades = completedTrades.filter((t) => (t.net_profit ?? 0) > 0).length;
  const winRate = totalTradesCount > 0 ? ((winningTrades / totalTradesCount) * 100).toFixed(1) : "0.0";
  const totalNetProfit = completedTrades.reduce((acc, t) => acc + (t.net_profit ?? 0), 0).toFixed(2);

  return (
    <div
      className="flex flex-col h-screen w-full bg-[var(--bg-primary,#0f172a)] text-slate-200 p-4 gap-4 overflow-hidden transition-all duration-300 ease-in-out box-border"
      style={{ paddingLeft: "var(--sidebar-offset, 250px)", boxSizing: "border-box", maxWidth: "100vw" }}
    >
      {/* Single-line title and replay toolbar */}
      <div className="flex items-center gap-3 p-3 glass-card rounded-xl border border-slate-800 bg-slate-900/60 overflow-x-auto">
        <div className="flex shrink-0 items-center gap-2 pr-3 border-r border-slate-700/80">
          <span className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <FileCode className="w-4 h-4" />
          </span>
          <h1 className="text-sm font-bold text-slate-100 whitespace-nowrap">Replay Original</h1>
          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 whitespace-nowrap">
            Rule-Based C#
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={() => setPlayIndex(candles.length > 0 ? 1 : 0)}
            disabled={isPlaying || playIndex <= 1}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-violet-400 bg-violet-500/10 border border-violet-500/30 transition-colors hover:bg-violet-500/20 disabled:opacity-40"
          >
            <Rewind className="w-3 h-3" />
            Rewind
          </button>
          <button
            onClick={() => setIsPlaying((current) => !current)}
            disabled={playIndex >= candles.length}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-cyan-400 bg-cyan-500/10 border border-cyan-500/30 transition-colors hover:bg-cyan-500/20 disabled:opacity-40"
          >
            {isPlaying ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            {isPlaying ? "Pause" : "Play"}
          </button>
          <button
            onClick={() => setPlayIndex((current) => Math.min(current + 1, candles.length))}
            disabled={isPlaying || playIndex >= candles.length}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-violet-400 bg-violet-500/10 border border-violet-500/30 transition-colors hover:bg-violet-500/20 disabled:opacity-40"
          >
            <SkipForward className="w-3 h-3" />
            Next
          </button>
          <button
            onClick={() => {
              setIsPlaying(false);
              setPlayIndex(candles.length > 0 ? 1 : 0);
            }}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-rose-400 bg-rose-500/10 border border-rose-500/30 transition-colors hover:bg-rose-500/20"
          >
            <Square className="w-3 h-3" />
            Stop
          </button>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <span className="text-xs text-slate-400">Speed:</span>
          {Object.keys(SPEED_MAP).map((sp) => (
            <button
              key={sp}
              onClick={() => setSpeed(sp)}
              className={cn(
                "px-2 py-1 text-xs font-semibold rounded border transition-colors",
                speed === sp
                  ? "bg-cyan-500/15 text-cyan-400 border-cyan-500/30"
                  : "bg-slate-800/60 text-slate-400 border-slate-700/60 hover:text-slate-200"
              )}
            >
              {sp}
            </button>
          ))}
        </div>

        <div className="flex shrink-0 items-center gap-2 pl-3 border-l border-slate-700/80">
          {/* Strategy Selector */}
          <div className="flex items-center gap-2 bg-slate-800/80 px-2.5 py-1.5 rounded-lg border border-slate-700">
            <span className="text-xs text-slate-400 font-medium">Strategy:</span>
            <select
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
              className="bg-transparent text-sm font-semibold text-blue-400 focus:outline-none cursor-pointer"
            >
              {strategies.map((s) => (
                <option key={s.id} value={s.filename} className="bg-slate-900 text-slate-200">
                  {s.label} ({s.filename})
                </option>
              ))}
            </select>
          </div>

          {/* Date Range Picker */}
          <div className="flex items-center gap-2 bg-slate-800/80 px-2.5 py-1.5 rounded-lg border border-slate-700">
            <Calendar className="w-4 h-4 text-slate-400" />
            <select
              value={yearFrom}
              onChange={(e) => setYearFrom(Number(e.target.value))}
              className="bg-transparent text-xs font-semibold text-slate-200 focus:outline-none cursor-pointer"
            >
              {[2024, 2025, 2026].map((y) => (
                <option key={y} value={y} className="bg-slate-900 text-slate-200">
                  {y}
                </option>
              ))}
            </select>
            <select
              value={monthFrom}
              onChange={(e) => setMonthFrom(Number(e.target.value))}
              className="bg-transparent text-xs font-semibold text-slate-200 focus:outline-none cursor-pointer"
            >
              {MONTHS.map((m, idx) => (
                <option key={idx + 1} value={idx + 1} className="bg-slate-900 text-slate-200">
                  {m}
                </option>
              ))}
            </select>
            <span className="text-xs font-semibold text-slate-500">→</span>
            <select
              value={yearTo}
              onChange={(e) => setYearTo(Number(e.target.value))}
              className="bg-transparent text-xs font-semibold text-slate-200 focus:outline-none cursor-pointer"
            >
              {[2024, 2025, 2026].map((y) => (
                <option key={y} value={y} className="bg-slate-900 text-slate-200">
                  {y}
                </option>
              ))}
            </select>
            <select
              value={monthTo}
              onChange={(e) => setMonthTo(Number(e.target.value))}
              className="bg-transparent text-xs font-semibold text-slate-200 focus:outline-none cursor-pointer"
            >
              {MONTHS.map((m, idx) => (
                <option key={idx + 1} value={idx + 1} className="bg-slate-900 text-slate-200">
                  {m}
                </option>
              ))}
            </select>
          </div>

          {/* Timeframe Selector */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase text-slate-400">Timeframe</span>
            <div className="flex items-center bg-slate-800/80 p-1 rounded-lg border border-slate-700">
            {["M15", "H1", "H4"].map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={cn(
                  "px-2.5 py-1 text-xs font-semibold rounded transition-all",
                  timeframe === tf
                    ? "bg-blue-600 text-white shadow"
                    : "text-slate-400 hover:text-slate-200"
                )}
              >
                {tf}
              </button>
            ))}
            </div>
          </div>

          <button
            onClick={loadReplayData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-cyan-300 bg-cyan-500/15 border border-cyan-500/40 transition-colors hover:bg-cyan-500/25 disabled:opacity-40"
          >
            {loading && <Loader2 className="w-3 h-3 animate-spin" />}
            Load
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3 glass-card rounded-xl bg-slate-900/40 border border-slate-800">
          <p className="text-xs text-slate-400">Total Candle</p>
          <p className="text-lg font-bold text-slate-200">{playIndex} / {candles.length}</p>
        </div>
        <div className="p-3 glass-card rounded-xl bg-slate-900/40 border border-slate-800">
          <p className="text-xs text-slate-400">Total Trades</p>
          <p className="text-lg font-bold text-blue-400">{totalTradesCount}</p>
        </div>
        <div className="p-3 glass-card rounded-xl bg-slate-900/40 border border-slate-800">
          <p className="text-xs text-slate-400">Win Rate</p>
          <p className="text-lg font-bold text-emerald-400">{winRate}%</p>
        </div>
        <div className="p-3 glass-card rounded-xl bg-slate-900/40 border border-slate-800">
          <p className="text-xs text-slate-400">Net Profit</p>
          <p
            className={cn(
              "text-lg font-bold",
              Number(totalNetProfit) >= 0 ? "text-emerald-400" : "text-rose-400"
            )}
          >
            ${totalNetProfit}
          </p>
        </div>
      </div>

      {/* Main Chart Section */}
      <div className="relative flex-1 rounded-xl border border-slate-800 bg-slate-950/80 overflow-hidden">
        {loading && (
          <div className="absolute inset-0 z-30 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm">
            <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-slate-900 border border-slate-800">
              <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
              <span className="text-sm font-medium text-slate-300">
                Memuat data replay strategi...
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 z-30 flex items-center justify-center bg-slate-950/80">
            <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm max-w-md text-center">
              <p className="font-bold mb-1">Gagal Memuat Replay</p>
              <p className="text-xs text-slate-300">{error}</p>
            </div>
          </div>
        )}

        {/* Lightweight Charts Canvas */}
        <div ref={chartContainerRef} className="w-full h-full" />

      </div>
    </div>
  );
}
