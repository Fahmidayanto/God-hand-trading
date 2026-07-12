import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { CalendarDays, X, Loader2 } from "lucide-react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  CandlestickSeries,
  LineSeries,
  LineStyle,
} from "lightweight-charts";
import Particles from "@tsparticles/react";
import { useMarketStructureLines, useSessionZones, useBacktestTrades, type BacktestTrade } from "@/api/mt5_agents";
import {
  SessionZonesPrimitive,
  type SessionZoneBox,
} from "@/components/valuecell/charts/session-zones-primitive";
import {
  TradesOverlayPrimitive,
  type TradeOverlayEntry,
} from "@/components/valuecell/charts/trades-overlay-primitive";
import {
  StructureLinesPrimitive,
  type StructureLineItem,
} from "@/components/valuecell/charts/structure-lines-primitive";
import MT5Footer from "./components/MT5Footer";
import ChartToolbar from "./components/ChartToolbar";

interface Trade {
  trade_id: string;
  symbol: string;
  type: string;
  entry_price: number;
  exit_price: number | null;
  lot_size: number;
  pnl: number;
  status: string;
  open_time: string;
}

type ChartCandle = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  ema200?: number;
};

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

export default function TradesPage() {
  const [stats, setStats] = useState({
    total_trades: 0,
    win_rate: 0,
    total_pnl: 0,
    open_positions: 0,
  });
  const [trades, setTrades] = useState<Trade[]>([]);
  const [activeFilter, setActiveFilter] = useState("all");
  const [showStructure, setShowStructure] = useState(true);
  const [showSessions, setShowSessions] = useState(true);
  const [showEMA200, setShowEMA200] = useState(true);
  const [showTrades, setShowTrades] = useState(false);
  const [activeTimeframe, setActiveTimeframe] = useState("M15"); // Timeframe state
  const [chartCandles, setChartCandles] = useState<ChartCandle[]>([]);
  const latestProgressRef = useRef({ percent: 0, step: '', total: 0 });
  const [loadProgress, setLoadProgress] = useState<{
    visible: boolean;
    percent: number;
    step: string;
    total: number;
  }>({ visible: false, percent: 0, step: '', total: 0 });
  const [drawLineProgress, setDrawLineProgress] = useState<{
    visible: boolean;
    percent: number;
    current: number;
    total: number;
  }>({ visible: false, percent: 0, current: 0, total: 0 });

  // Data loading mode state
  const [dataMode, setDataMode] = useState<'recent' | 'full' | 'loading'>('recent');
  const [chartFromDate, setChartFromDate] = useState(() => {
    // Default: 6 months ago
    const date = new Date();
    date.setMonth(date.getMonth() - 6);
    return date.toISOString().split('T')[0];
  });
  const [candlesCount, setCandlesCount] = useState(0);

  // Year/Month Jump Navigation state
  const [selectedYear, setSelectedYear] = useState("2026");
  const [selectedMonth, setSelectedMonth] = useState("06");
  const [isJumping, setIsJumping] = useState(false);

  // Available years (2020-2026)
  const availableYears = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"];

  // Available months
  const availableMonths = [
    { value: "01", label: "January" },
    { value: "02", label: "February" },
    { value: "03", label: "March" },
    { value: "04", label: "April" },
    { value: "05", label: "May" },
    { value: "06", label: "June" },
    { value: "07", label: "July" },
    { value: "08", label: "August" },
    { value: "09", label: "September" },
    { value: "10", label: "October" },
    { value: "11", label: "November" },
    { value: "12", label: "December" },
  ];

  // CHART TIMEZONE DEFAULT = UTC.
  // When the page first opens, UTC is always selected (per requirement).
  // The user can manually switch to 'broker' or 'local'; once switched, that
  // choice is preserved across data refreshes. UTC stays default until then.
  const [chartTimezone, setChartTimezone] = useState<{ broker_offset_hours: number, display_mode: string, candle_times_are_utc: boolean }>({
    broker_offset_hours: 3,
    display_mode: 'utc', // Default to UTC on every page open
    candle_times_are_utc: true
  });

  const [activeYear, setActiveYear] = useState<string>("2026");

  // Tab and Pop-up states for Monthly summary
  const [activeBottomTab, setActiveBottomTab] = useState<'recent-trades' | 'monthly-summary'>('recent-trades');
  const [monthlyPNL, setMonthlyPNL] = useState<any[]>([]);
  const [selectedMonthTrades, setSelectedMonthTrades] = useState<any[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalTitle, setModalTitle] = useState("");
  const [isLoadingTrades, setIsLoadingTrades] = useState(false);
  const [monthlySummaryYearFilter, setMonthlySummaryYearFilter] = useState<string>("2026");
  const [monthlySummaryPerformanceFilter, setMonthlySummaryPerformanceFilter] = useState<'all' | 'profit' | 'loss'>('all');
  const [isYearDropdownOpen, setIsYearDropdownOpen] = useState(false);

  const handleMonthRowClick = async (year: number, monthNum: number, monthLabel: string) => {
    setIsLoadingTrades(true);
    setModalTitle(monthLabel);
    setIsModalOpen(true);
    setSelectedMonthTrades([]);

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
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
  };

  const loadMonthlyPNL = async () => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const response = await fetch(`${apiUrl}/performance/monthly-pnl`);
      if (response.ok) {
        const res = await response.json();
        setMonthlyPNL(res.data && Array.isArray(res.data) ? res.data : []);
      }
    } catch (error) {
      console.error("Error loading monthly P&L:", error);
    }
  };
  // DISABLED: year/month dropdown
  // const availableYears = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"];
  // const [availableMonths, setAvailableMonths] = useState<Array<{label: string, value: number}>>([]);
  // const [selectedMonth, setSelectedMonth] = useState<string>("");
  // const monthsInitialized = useRef(false);

  // Track if user has manually changed timezone (don't override if true)
  const userChangedTimezone = useRef(false);

  // Helper function to format time based on timezone mode
  // This is separate so it can be called with fresh timezone values
  const indonesianMonths = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
  ];

  const formatChartTime = (time: number, displayMode: string, brokerOffset: number): string => {
    const date = new Date(time * 1000);
    let day: string, month: string, year: number, hours: string, minutes: string;

    if (displayMode === 'utc') {
      day = String(date.getUTCDate()).padStart(2, '0');
      month = indonesianMonths[date.getUTCMonth()];
      year = date.getUTCFullYear();
      hours = String(date.getUTCHours()).padStart(2, '0');
      minutes = String(date.getUTCMinutes()).padStart(2, '0');
    } else if (displayMode === 'broker') {
      const brokerTime = new Date((time + brokerOffset * 3600) * 1000);
      day = String(brokerTime.getUTCDate()).padStart(2, '0');
      month = indonesianMonths[brokerTime.getUTCMonth()];
      year = brokerTime.getUTCFullYear();
      hours = String(brokerTime.getUTCHours()).padStart(2, '0');
      minutes = String(brokerTime.getUTCMinutes()).padStart(2, '0');
    } else { // local
      day = String(date.getDate()).padStart(2, '0');
      month = indonesianMonths[date.getMonth()];
      year = date.getFullYear();
      hours = String(date.getHours()).padStart(2, '0');
      minutes = String(date.getMinutes()).padStart(2, '0');
    }

    return `${day} ${month} ${year} ${hours}:${minutes}`;
  };


  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartDataLoadedRef = useRef(false);
  const isLoadingChartDataRef = useRef(false);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema200SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const structureSeriesRef = useRef<ISeriesApi<"Line">[]>([]); // Line series for structure
  const sessionZonesPrimitiveRef = useRef<SessionZonesPrimitive | null>(null);
  const structurePrimitiveRef = useRef<StructureLinesPrimitive | null>(null);
  const tradesPrimitiveRef = useRef<TradesOverlayPrimitive | null>(null);
  // ponytail: shares overlayGuardRef with structure, no separate guard needed

  // Ref to always get the latest timezone state in formatter
  const chartTimezoneRef = useRef(chartTimezone);

  // ========================
  // CLIENT-SIDE CACHE SYSTEM
  // ========================
  // Cache full candle data in memory for instant navigation
  // Key format: "{timeframe}" (e.g., "M15", "H1")
  // This eliminates the need to fetch from API on every month jump
  const candleCacheRef = useRef<{
    [key: string]: {
      candles: ChartCandle[];
      loadedAt: number; // timestamp when cached
      fromDate: string; // e.g., "2020-01-01"
      toDate: string;   // e.g., "2026-06-25"
      totalCount: number;
    }
  }>({});

  // Flag to track if full history has been loaded for current timeframe
  const fullHistoryLoadedRef = useRef<{ [key: string]: boolean }>({});

  // Track if full cached data is currently DISPLAYED on chart (not just cached).
  // Prevents redundant setData + overlay rebuild on year/month jumps within same timeframe.
  const fullDataDisplayedRef = useRef<{ [key: string]: boolean }>({});

  // Debounce timer for scroll label re-render — prevents DOM churn at 60fps during pan/zoom
  const scrollLabelDebounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Save center time when switching timeframes to maintain date focus and auto-scale zoom
  const timeframeSwitchCenterTimeRef = useRef<number | null>(null);

  // Update ref whenever chartTimezone changes
  useEffect(() => {
    console.log('📍 chartTimezone state changed:', {
      oldState: chartTimezoneRef.current,
      newState: chartTimezone
    });
    chartTimezoneRef.current = chartTimezone;
  }, [chartTimezone]);

  // Load market structure lines (2020-01-01 to now, from all CSV files)
  const { data: structureLines } = useMarketStructureLines("2020-01-01");

  // Load session zones - sync with chart data mode
  const { data: sessionZonesData } = useSessionZones(chartFromDate);

  // Load backtest trades for Entry/SL/TP overlay
  const { data: backtestTradesData } = useBacktestTrades();

  const processCandles = (candles: any[]): ChartCandle[] =>
    candles.map((candle: any) => ({
      time: candle.time as number,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
      ema200: candle.ema200,
    }));

  const updateEma200Series = (candles: ChartCandle[]) => {
    if (!ema200SeriesRef.current) return;

    const ema200Data = candles
      .filter((candle) => candle.ema200 != null)
      .map((candle) => ({
        time: candle.time as number,
        value: candle.ema200 as number,
      }));

    ema200SeriesRef.current.setData(ema200Data as any);
  };

  const updateLoadedCandles = (candles: ChartCandle[], count = candles.length) => {
    candlestickSeriesRef.current?.setData(candles as any);
    setChartCandles(candles);
    setCandlesCount(count);
    updateEma200Series(candles);
    sessionZonesPrimitiveRef.current?.setCandleTimes(candles.map((candle) => candle.time));
  };

  const cacheFullHistory = (timeframe: string, candles: ChartCandle[]) => {
    candleCacheRef.current[timeframe] = {
      candles,
      loadedAt: Date.now(),
      fromDate: '2020-01-01',
      toDate: new Date(candles[candles.length - 1].time * 1000).toISOString().split('T')[0],
      totalCount: candles.length,
    };
    fullHistoryLoadedRef.current[timeframe] = true;
  };

  const focusChartOnDate = (centerDate: string, delayMs = 50, candles?: ChartCandle[]) => {
    const centerTimestamp = Date.parse(`${centerDate}T00:00:00Z`) / 1000;

    const doScroll = () => {
      const timeScale = chartRef.current?.timeScale();
      if (!timeScale) return;

      if (candles && candles.length > 0) {
        const idx = candles.findIndex((c: ChartCandle) => c.time >= centerTimestamp);
        if (idx >= 0) {
          timeScale.setVisibleLogicalRange({
            from: idx as any,
            to: Math.min(candles.length - 1, idx + 287) as any,
          });
        }
      }

      renderStructureLabelsOverlay(structureLabelsRef.current);
    };

    if (delayMs === 0) {
      requestAnimationFrame(doScroll);
    } else {
      setTimeout(() => requestAnimationFrame(doScroll), delayMs);
    }
  };

  const getWindowStartDate = (centerDate: string) => {
    const windowStart = new Date(`${centerDate}T00:00:00Z`);
    windowStart.setUTCMonth(windowStart.getUTCMonth() - 3);
    return windowStart.toISOString().split('T')[0];
  };

  useEffect(() => {
    console.log('📊 Chart initialization effect triggered');
    console.log('chartContainerRef.current:', !!chartContainerRef.current);
    console.log('chartRef.current:', !!chartRef.current);

    if (chartContainerRef.current && !chartRef.current) {
      console.log('✅ Initializing chart...');
      try {
        const chart = createChart(chartContainerRef.current, {
          autoSize: true, // Auto-fit chart to container size via ResizeObserver
          layout: {
            background: { color: "rgba(17, 24, 39, 0.3)" },
            textColor: "#cbd5e1",
          },
          grid: {
            vertLines: { color: "rgba(100, 116, 139, 0.1)" },
            horzLines: { color: "rgba(100, 116, 139, 0.1)" },
          },
          crosshair: {
            mode: 0, // Normal crosshair mode (0 = normal, 1 = magnet)
            vertLine: {
              width: 1,
              color: 'rgba(224, 227, 235, 0.5)',
              style: 0,
              labelBackgroundColor: 'rgba(59, 130, 246, 0.8)',
            },
            horzLine: {
              width: 1,
              color: 'rgba(224, 227, 235, 0.5)',
              style: 0,
              labelBackgroundColor: 'rgba(59, 130, 246, 0.8)',
            },
          },
          rightPriceScale: {
            borderColor: "rgba(100, 116, 139, 0.3)",
          },
          timeScale: {
            borderColor: "rgba(100, 116, 139, 0.3)",
            timeVisible: true,
            secondsVisible: false,
            barSpacing: 8,
            minBarSpacing: 0.01,
            fixLeftEdge: false,
            fixRightEdge: false,
            lockVisibleTimeRangeOnResize: false,
            rightBarStaysOnScroll: true,
            shiftVisibleRangeOnNewBar: false, // CRITICAL: Disable auto-scroll when data updates
          },
          localization: {
            locale: 'en-US',
            timeFormatter: (time: number) => {
              // Use ref to get latest timezone state (avoids stale closure)
              const currentTimezone = chartTimezoneRef.current;
              return formatChartTime(time, currentTimezone.display_mode, currentTimezone.broker_offset_hours);
            },
          },
        });

        // Log timezone info
        const timezoneOffset = new Date().getTimezoneOffset();
        console.log('🕐 Browser timezone offset (minutes):', timezoneOffset);
        console.log('🕐 This means browser is:', timezoneOffset > 0 ? `GMT-${timezoneOffset / 60}` : `GMT+${-timezoneOffset / 60}`);

        const candlestickSeries = chart.addSeries(CandlestickSeries, {
          upColor: "#10b981",
          downColor: "#ef4444",
          borderVisible: false,
          wickUpColor: "#10b981",
          wickDownColor: "#ef4444",
        });

        chartRef.current = chart;
        candlestickSeriesRef.current = candlestickSeries;

        // Add EMA 200 line series (initially hidden, data loaded via API)
        const ema200Series = chart.addSeries(LineSeries, {
          color: "#f59e0b",
          lineWidth: 2 as any,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "EMA 200",
          visible: showEMA200,
        });
        ema200SeriesRef.current = ema200Series;
        console.log('📉 EMA 200 series created:', {
          visible: showEMA200,
          color: '#f59e0b',
          seriesRef: !!ema200SeriesRef.current,
        });

        // Attach the session-zone shadow primitive (drawn beneath candles).
        try {
          const sessionPrimitive = new SessionZonesPrimitive();
          (candlestickSeries as any).attachPrimitive(sessionPrimitive);
          sessionZonesPrimitiveRef.current = sessionPrimitive;
        } catch (e) {
          console.warn("Could not attach session zones primitive:", e);
        }

        // Attach the structure lines primitive.
        try {
          const structPrimitive = new StructureLinesPrimitive();
          (candlestickSeries as any).attachPrimitive(structPrimitive);
          structurePrimitiveRef.current = structPrimitive;
        } catch (e) {
          console.warn("Could not attach structure lines primitive:", e);
        }

        console.log('✅ Chart initialized successfully');
        console.log('chartRef.current:', !!chartRef.current);
        console.log('candlestickSeriesRef.current:', !!candlestickSeriesRef.current);

        loadChartData(false);
      } catch (error) {
        console.error('❌ Error creating chart:', error);
      }
    } else {
      console.log('⏭️ Skipping chart init: already initialized or container not ready');
      if (chartContainerRef.current) {
        loadChartData(false);
      }
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && chartRef.current && chartContainerRef.current) {
          chartRef.current.applyOptions({
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
          });
        }
      });
    });

    if (chartContainerRef.current) observer.observe(chartContainerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    loadTradeHistory();
    if (activeBottomTab === 'monthly-summary') {
      loadMonthlyPNL();
    }
  }, [activeBottomTab]);

  useEffect(() => {
    // Auto-refresh chart data every 30 seconds (increased from 5s for performance)
    // ONLY refresh in recent mode AND only if user hasn't jumped to specific date
    // Disable auto-refresh when exploring historical data to prevent unwanted scrolling
    const chartInterval = setInterval(() => {
      if (activeTimeframe === "M1") return; // Skip API polling when M1 TradingView widget is active
      if (chartRef.current && candlestickSeriesRef.current && dataMode === 'recent' && !isJumping) {
        // Only auto-refresh if we're truly in recent mode (last 6 months)
        // Don't refresh if user is exploring historical data via jump
        const recentThreshold = new Date();
        recentThreshold.setMonth(recentThreshold.getMonth() - 6);

        // Check if chartFromDate is within recent range
        const chartDate = new Date(chartFromDate);
        if (chartDate >= recentThreshold) {
          console.log('🔄 Auto-refresh chart data (recent mode only)');
          loadChartData(false, 'recent');
        }
      }
    }, 30000); // 30 seconds instead of 5 seconds
    return () => clearInterval(chartInterval);
  }, [activeTimeframe, activeYear, dataMode, chartFromDate, isJumping]);

  // DISABLED: months generation from candle data
  // useEffect(() => {
  //   if (chartCandles.length === 0 || monthsInitialized.current) return;
  //   monthsInitialized.current = true;
  //
  //   const times = chartCandles.map(c => c.time);
  //   const minTime = Math.min(...times);
  //   const maxTime = Math.max(...times);
  //
  //   const months: Array<{label: string, value: number}> = [];
  //   const minDate = new Date(minTime * 1000);
  //   const maxDate = new Date(maxTime * 1000);
  //   const cursor = new Date(Date.UTC(minDate.getUTCFullYear(), minDate.getUTCMonth(), 1));
  //   const names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  //
  //   while (cursor <= maxDate) {
  //     const y = cursor.getUTCFullYear();
  //     const m = cursor.getUTCMonth();
  //     const start = Math.floor(Date.UTC(y, m, 1) / 1000);
  //     months.push({ label: names[m], value: start });
  //     cursor.setUTCMonth(m + 1);
  //   }
  //
  //   setAvailableMonths(months);
  //   setSelectedMonth(prev => prev === "" && months.length > 0 ? String(months[0].value) : prev);
  // }, [chartCandles]);

  const loadChartData = async (forceRefresh = false, loadMode?: 'recent' | 'full', timeframeOverride?: string) => {
    if (isLoadingChartDataRef.current && !forceRefresh) {
      console.log('⏭️ loadChartData: skipped (already loading)');
      return;
    }
    const timeframe = timeframeOverride || activeTimeframe;
    isLoadingChartDataRef.current = true;
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

      // Determine mode and from_date
      const mode = loadMode || dataMode;
      const fromDate = mode === 'full' ? '2020-01-01' : chartFromDate;

      const chartUrl = timeframe === "M1"
        ? `${apiUrl}/trading/chart/data?symbol=XAUUSD&timeframe=M1&count=6000`
        : `${apiUrl}/trading/chart/backtest-data?symbol=XAUUSD&timeframe=${timeframe}&from_date=${fromDate}&mode=${mode}`;
      console.log('🔄 Fetching chart data:', { mode, fromDate, url: chartUrl });

      const response = await fetch(chartUrl);

      console.log('Chart API response status:', response.status, response.ok);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('📉 [API ERROR]:', response.status, errorText);
      }

      if (response.ok) {
        const data = await response.json();
        console.log('✅ Chart API data received:', {
          mode: data.mode,
          from_date: data.from_date,
          candles: data.candles?.length,
          candlesCount: data.candles_count,
        });

        if (data.candles && candlestickSeriesRef.current) {
          const processedCandles = processCandles(data.candles);

          console.log('✅ Processed candles:', processedCandles.length);

          const timeScale = chartRef.current?.timeScale();
          const currentVisibleRange = timeScale?.getVisibleRange();

          updateLoadedCandles(processedCandles, data.candles_count || processedCandles.length);
          if (mode === 'full' && processedCandles.length > 0) {
            cacheFullHistory(timeframe, processedCandles);
          }

          // Restore viewport position or align timeline after switching timeframes
          if (timeScale && processedCandles.length > 0) {
            if (timeframeSwitchCenterTimeRef.current != null) {
              const targetTime = timeframeSwitchCenterTimeRef.current;
              timeframeSwitchCenterTimeRef.current = null; // Clear Ref

              // Find the index of the closest candle to the previous center time
              let closestIndex = 0;
              let minDiff = Infinity;
              for (let i = 0; i < processedCandles.length; i++) {
                const diff = Math.abs(processedCandles[i].time - targetTime);
                if (diff < minDiff) {
                  minDiff = diff;
                  closestIndex = i;
                }
              }

              // Calculate how many candles are in 5 days for the active timeframe
              let candlesPerDay = 96; // Default to M15 (24 * 4)
              if (activeTimeframe === "H1") {
                candlesPerDay = 24;
              } else if (activeTimeframe === "H4") {
                candlesPerDay = 6;
              } else if (activeTimeframe === "D1" || activeTimeframe === "D") {
                candlesPerDay = 1;
              }

              const totalCandles = candlesPerDay * 5;
              const halfCount = Math.max(15, Math.floor(totalCandles / 2)); // Minimum 15 candles

              const fromIndex = Math.max(0, closestIndex - halfCount);
              const toIndex = Math.min(processedCandles.length - 1, closestIndex + halfCount);

              setTimeout(() => {
                timeScale.setVisibleRange({
                  from: processedCandles[fromIndex].time as any,
                  to: processedCandles[toIndex].time as any,
                });
                // Reset right price scale option to auto-scale vertically
                chartRef.current?.priceScale('right').applyOptions({
                  autoScale: true,
                });
              }, 0);
            } else if (chartDataLoadedRef.current && currentVisibleRange && !forceRefresh) {
              setTimeout(() => {
                timeScale.setVisibleRange(currentVisibleRange);
              }, 0);
            } else if (!chartDataLoadedRef.current && processedCandles.length > 0) {
              // First load zoom: show the most recent 250 candles
              const count = Math.min(250, processedCandles.length);
              const fromIndex = processedCandles.length - count;
              setTimeout(() => {
                timeScale.setVisibleRange({
                  from: processedCandles[fromIndex].time as any,
                  to: processedCandles[processedCandles.length - 1].time as any,
                });
                chartRef.current?.priceScale('right').applyOptions({
                  autoScale: true,
                });
              }, 0);
              chartDataLoadedRef.current = true; // Mark as loaded to prevent subsequent zoom resets
            }
          }

          // Update mode state if loading was triggered
          if (loadMode) {
            setDataMode(loadMode);
          }

          // Store timezone info from API.
          // IMPORTANT: `display_mode` defaults to 'utc' and is NOT overridden by the
          // backend config on first load — UTC must be the default when the page opens.
          // We only pull `broker_offset_hours` (needed when user switches to broker mode).
          // If the user has manually picked a mode, we keep their choice entirely.
          if (data.timezone) {
            if (userChangedTimezone.current) {
              // Keep user's manually chosen mode, just refresh broker offset
              setChartTimezone(prev => ({
                ...prev,
                broker_offset_hours: data.timezone.broker_offset_hours ?? prev.broker_offset_hours,
              }));
              console.log('🚫 Skipping display_mode override (user manually changed it); refreshed broker offset only');
            } else {
              // Default path: force UTC as the display mode, only adopt broker offset from API
              setChartTimezone(prev => ({
                ...prev,
                broker_offset_hours: data.timezone.broker_offset_hours ?? prev.broker_offset_hours,
                display_mode: 'utc',
              }));
              console.log('🌍 Defaulting chart display_mode to UTC (broker offset from API:', data.timezone.broker_offset_hours, ')');
            }
          }
          console.log(`✅ Chart data loaded successfully (${data.mode} mode)`);

          // Trigger structure overlay with fresh candle data
          if (showStructure && structureLines) {
            console.log('🔄 Triggering structure overlay');
            await overlayMarketStructure(processedCandles, forceRefresh);
          }

          return; // Exit if API data loaded successfully
        }
      }
    } catch (error) {
      console.error("API error:", error);
      console.warn("⚠️ Unable to load chart data");
      setDataMode('recent'); // Reset to recent on error
    } finally {
      isLoadingChartDataRef.current = false;
    }
  };

  // Load full history function with caching
  const loadFullHistory = async () => {
    latestProgressRef.current = { percent: 0, step: 'Counting rows...', total: 0 };
    setLoadProgress({ visible: true, percent: 0, step: 'Counting rows...', total: 0 });

    const cacheKey = activeTimeframe;
    const cachedData = candleCacheRef.current[cacheKey];
    if (cachedData && fullHistoryLoadedRef.current[cacheKey]) {
      const ts = chartRef.current?.timeScale();
      const prevRange = ts?.getVisibleRange();
      const prevBarSpacing = ts?.options()?.barSpacing;
      setChartFromDate(cachedData.fromDate);
      updateLoadedCandles(cachedData.candles, cachedData.totalCount);
      setDataMode('full');
      if (showStructure && structureLines) {
        overlayMarketStructure(cachedData.candles, true);
      }
      if (prevRange && ts) {
        setTimeout(() => {
          ts.setVisibleRange(prevRange);
          if (prevBarSpacing != null) ts.applyOptions({ barSpacing: prevBarSpacing });
        }, 0);
      }
      fullDataDisplayedRef.current[cacheKey] = true;
      setLoadProgress({ visible: false, percent: 100, step: '', total: 0 });
      return;
    }

    setDataMode('loading');
    setChartFromDate('2020-01-01');

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const chartUrl = `${apiUrl}/trading/chart/backtest-data-stream?symbol=XAUUSD&timeframe=${activeTimeframe}&from_date=2020-01-01&mode=full`;

      const response = await fetch(chartUrl);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let completeData: any = null;

      let hasComplete = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          if (!line.trim()) continue;
          const msg = JSON.parse(line);

          if (msg.type === 'progress') {
            latestProgressRef.current = {
              percent: msg.percent,
              step: msg.step,
              total: msg.total_estimated ?? 0,
            };
          } else if (msg.type === 'complete') {
            completeData = msg.data;
            latestProgressRef.current = {
              percent: 100,
              step: 'Rendering...',
              total: msg.data.candles?.length || 0,
            };
            hasComplete = true;
            break;
          } else if (msg.type === 'error') {
            console.error('Backend error:', msg.message);
            setDataMode('recent');
            setLoadProgress({ visible: false, percent: 0, step: '', total: 0 });
            return;
          }

          if (i % 20 === 19) {
            await new Promise(r => setTimeout(r, 0));
          }
        }
        if (hasComplete) break;
      }

      if (!completeData) throw new Error('No complete event received');
      const { candles } = completeData;

      if (candles && candles.length > 0) {
        const processedCandles = processCandles(candles);
        cacheFullHistory(cacheKey, processedCandles);
        const ts = chartRef.current?.timeScale();
        const prevRange = ts?.getVisibleRange();
        const prevBarSpacing = ts?.options()?.barSpacing;
        if (candlestickSeriesRef.current) updateLoadedCandles(processedCandles);
        if (prevRange && ts) {
          setTimeout(() => {
            ts.setVisibleRange(prevRange);
            if (prevBarSpacing != null) ts.applyOptions({ barSpacing: prevBarSpacing });
          }, 0);
        }
        setDataMode('full');

        // Close download popup first
        latestProgressRef.current = { percent: 100, step: '', total: 0 };
        setLoadProgress({ visible: false, percent: 100, step: '', total: 0 });

        // Yield control to let Popup 1 close fully
        await new Promise((resolve) => setTimeout(resolve, 50));

        if (showStructure && structureLines) {
          await overlayMarketStructure(processedCandles, true);
        }
        fullDataDisplayedRef.current[cacheKey] = true;
      }
    } catch (error) {
      console.error('Stream error:', error);
      setDataMode('recent');
    } finally {
      setLoadProgress({ visible: false, percent: 100, step: '', total: 0 });
    }
  };

  // Jump to specific year/month function (refactored to use cache)
  const jumpToDate = async (year: string, month: string) => {
    const centerDate = `${year}-${month}-01`;
    console.log('🎯 jumpToDate ENTER', { year, month, centerDate, cacheKey: activeTimeframe });

    setIsJumping(true);

    const cacheKey = activeTimeframe;
    const cachedData = candleCacheRef.current[cacheKey];
    console.log('🎯 cache check', { hasCache: !!cachedData, fullLoaded: fullHistoryLoadedRef.current[cacheKey] });

    // Check if we have cached full history for this timeframe
    if (cachedData && fullHistoryLoadedRef.current[cacheKey]) {
      console.log('🎯 CACHED PATH', { branch: fullDataDisplayedRef.current[cacheKey] ? 'else' : 'if' });
      console.log('💾 Cache info:', {
        totalCandles: cachedData.totalCount,
        dateRange: `${cachedData.fromDate} to ${cachedData.toDate}`,
      });

      try {
        if (candlestickSeriesRef.current && chartRef.current && cachedData.candles.length > 0) {
          if (!fullDataDisplayedRef.current[cacheKey]) {
            // First time displaying this cached data for this timeframe
            console.log('📊 Displaying cached data for', cacheKey, ':', {
              totalCandles: cachedData.totalCount,
              dateRange: `${cachedData.fromDate} to ${cachedData.toDate}`,
            });
            updateLoadedCandles(cachedData.candles);
            setChartFromDate(cachedData.fromDate);
            setDataMode('full');
            fullDataDisplayedRef.current[cacheKey] = true;
            // Scroll first, overlay draws in next frame — prevents 1.5s freeze before scroll
            focusChartOnDate(centerDate, 50, cachedData.candles);
            if (showStructure && structureLines) {
              await overlayMarketStructure(cachedData.candles, true);
            }
          } else {
            // Data & overlay already on chart — instant scroll
            updateLoadedCandles(cachedData.candles);
            focusChartOnDate(centerDate, 0, cachedData.candles);
          }
          console.log('🎯 jumpToDate COMPLETE (cached)');
        }
      } catch (error) {
        console.error('❌ Error using cache:', error);
      } finally {
        setIsJumping(false);
      }
      return;
    }

    // No cache available - fetch from API (fallback to original behavior)
    console.log('⚠️ No cache available, fetching from API...');
    setDataMode('loading');

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const chartUrl = `${apiUrl}/trading/chart/backtest-data?symbol=XAUUSD&timeframe=${activeTimeframe}&center_date=${centerDate}`;

      console.log('🔄 Fetching windowed data:', chartUrl);
      const response = await fetch(chartUrl);

      if (response.ok) {
        const data = await response.json();
        console.log('✅ Windowed data received:', {
          mode: data.mode,
          center_date: data.center_date,
          candles: data.candles?.length,
        });

        if (data.candles && candlestickSeriesRef.current && chartRef.current) {
          // Process candles
          const processedCandles = processCandles(data.candles);

          updateLoadedCandles(processedCandles, data.candles_count || processedCandles.length);

          // Update session zones to match window
          setChartFromDate(getWindowStartDate(centerDate));

          // Don't set to 'recent' - keep as 'full' to prevent auto-refresh
          // Window mode should not trigger auto-refresh
          setDataMode('full');

          // Scroll chart to center date
          focusChartOnDate(centerDate, 50, processedCandles);

          // Defer overlay to next frame so scroll renders first without freeze
          if (showStructure && structureLines) {
            await overlayMarketStructure(processedCandles, true);
          }
          console.log(`✅ Jumped to ${centerDate} successfully`);
        }
      }
    } catch (error) {
      console.error('❌ Jump to date error:', error);
      setDataMode('recent');
    } finally {
      setIsJumping(false);
    }
  };

  // Handle year change - jump to January of selected year
  // Handle timeframe change - keep visible center date and reset zoom/auto-scale
  const handleTimeframeChange = (newTimeframe: string) => {
    if (chartRef.current) {
      const timeScale = chartRef.current.timeScale();
      const visibleRange = timeScale.getVisibleRange();
      if (visibleRange) {
        const centerTime = ((visibleRange.from as number) + (visibleRange.to as number)) / 2;
        timeframeSwitchCenterTimeRef.current = centerTime;
        console.log("⏱️ Saved center time for timeframe switch:", new Date(centerTime * 1000).toISOString());
      }
    }
    setActiveTimeframe(newTimeframe);
  };

  const handleYearChange = (newYear: string) => {
    setSelectedYear(newYear);
    setSelectedMonth("01"); // Reset to January when year changes
    jumpToDate(newYear, "01");
  };

  // Handle month change - jump to selected month of current year
  const handleMonthChange = (newMonth: string) => {
    setSelectedMonth(newMonth);
    jumpToDate(selectedYear, newMonth);
  };

  // Handle timezone change - extracted so it can be reused by the toolbar
  const handleTimezoneChange = (newMode: "utc" | "broker" | "local") => {
    console.log("🔄 TIMEZONE CHANGE TRIGGERED");
    console.log("  Previous mode:", chartTimezone.display_mode);
    console.log("  New mode:", newMode);
    console.log("  Previous state:", chartTimezone);

    // Mark that user manually changed timezone
    userChangedTimezone.current = true;
    console.log("  🔒 User changed timezone flag set to TRUE");

    const newTimezone = { ...chartTimezone, display_mode: newMode };
    console.log("  New state to set:", newTimezone);

    setChartTimezone(newTimezone);
    console.log("  ✅ setChartTimezone called");

    // Update chart localization in real-time
    if (chartRef.current) {
      console.log("  📊 Chart ref exists, updating options...");

      chartRef.current.applyOptions({
        localization: {
          locale: "en-US",
          timeFormatter: (time: number) => {
            return formatChartTime(time, newMode, newTimezone.broker_offset_hours);
          },
        },
      });
      console.log("  ✅ applyOptions called with new formatter");

      const timeScale = chartRef.current.timeScale();
      const visibleRange = timeScale.getVisibleRange();
      console.log("  Current visible range:", visibleRange);

      if (visibleRange) {
        const tempRange = {
          from: (visibleRange.from as number) - 0.0001,
          to: (visibleRange.to as number) + 0.0001,
        };
        console.log("  Setting temp range:", tempRange);
        timeScale.setVisibleRange(tempRange as any);

        setTimeout(() => {
          if (chartRef.current) {
            console.log("  Restoring original range:", visibleRange);
            chartRef.current.timeScale().setVisibleRange(visibleRange);
            console.log("  ✅ Force redraw complete");
          }
        }, 10);
      } else {
        console.warn("  ⚠️ No visible range available");
      }
    } else {
      console.warn("  ⚠️ Chart ref not available");
    }

    console.log("🔄 TIMEZONE CHANGE HANDLER COMPLETE\n");
  };

  // Zoom controls
  const handleZoomIn = () => {
    if (!chartRef.current) return;
    const ts = chartRef.current.timeScale();
    const current = ts.options().barSpacing ?? 8;
    ts.applyOptions({ barSpacing: Math.min(current * 1.2, 30) });
  };

  const handleZoomOut = () => {
    if (!chartRef.current) return;
    const ts = chartRef.current.timeScale();
    const current = ts.options().barSpacing ?? 8;
    ts.applyOptions({ barSpacing: Math.max(current / 1.2, 0.01) });
  };

  const handleResetZoom = () => {
    if (!chartRef.current) return;
    chartRef.current.priceScale('right').applyOptions({ autoScale: true });
    chartRef.current.timeScale().applyOptions({ barSpacing: 8 });
  };

  // Guard to prevent concurrent executions
  const overlayGuardRef = useRef(false);

  // Track structure lines version to skip redundant redraws on 30s refetch
  const structureLinesVersionRef = useRef('');

  // Store the latest labels so they can be re-rendered when the user pans/zooms
  const structureLabelsRef = useRef<Array<{
    time: number;
    price: number;
    color: string;
    text: string;
    isResistance: boolean;
  }>>([]);

  // Render structure labels as HTML overlay on the chart container.
  // lightweight-charts v5 has no setMarkers, so we position <span> elements
  // using series.priceToCoordinate() and series.timeToCoordinate().
  const renderStructureLabelsOverlay = (
    labels: Array<{
      time: number;
      price: number;
      color: string;
      text: string;
      isResistance: boolean;
    }>,
  ) => {
    structureLabelsRef.current = labels;
    const overlayEl = document.getElementById('structure-labels-overlay');
    if (!overlayEl || !chartRef.current || !candlestickSeriesRef.current) return;

    overlayEl.innerHTML = '';
    const series = candlestickSeriesRef.current;

    for (const lbl of labels) {
      // timeToCoordinate is on the timeScale, not on the series
      const x = chartRef.current.timeScale().timeToCoordinate(lbl.time as any);
      const y = series.priceToCoordinate(lbl.price);
      if (x === null || y === null) continue;

      const span = document.createElement('span');
      span.textContent = lbl.text;
      span.style.position = 'absolute';
      // Translate to center horizontally and offset vertically from the line
      span.style.transform = 'translateX(-50%)';
      // Resistance labels above the line, support labels below
      span.style.top = lbl.isResistance
        ? `${Math.max(2, (y as number) - 18)}px`
        : `${(y as number) + 4}px`;
      span.style.left = `${x as number}px`;
      span.style.color = lbl.color;
      span.style.fontSize = '10px';
      span.style.fontWeight = '600';
      span.style.fontFamily = 'monospace';
      span.style.background = 'rgba(17, 24, 39, 0.85)';
      span.style.padding = '1px 5px';
      span.style.borderRadius = '3px';
      span.style.border = `1px solid ${lbl.color}`;
      span.style.whiteSpace = 'nowrap';
      span.style.pointerEvents = 'none';
      overlayEl.appendChild(span);
    }
  };

  const renderTradesLabels = (trades: BacktestTrade[]) => {
    const overlayEl = document.getElementById('trades-labels-overlay');
    if (!overlayEl || !chartRef.current || !candlestickSeriesRef.current) return;
    overlayEl.innerHTML = '';
    const series = candlestickSeriesRef.current;
    const lastCandle = chartCandles.length > 0 ? chartCandles[chartCandles.length - 1]?.time : null;

    for (const trade of trades) {
      const endTs = trade.exit_time_ts ?? lastCandle;
      if (!endTs) continue;
      const midTime = Math.floor((trade.entry_time_ts + endTs) / 2) as any;
      const labels = [
        { price: trade.entry_price, color: '#3b82f6', text: `Entry ${trade.entry_price}` },
      ];
      if (trade.sl !== null) labels.push({ price: trade.sl, color: '#ef4444', text: `SL ${trade.sl}` });
      if (trade.tp !== null) labels.push({ price: trade.tp, color: '#22c55e', text: `TP ${trade.tp}` });

      for (const lbl of labels) {
        const x = chartRef.current.timeScale().timeToCoordinate(midTime);
        const y = series.priceToCoordinate(lbl.price);
        if (x === null || y === null) continue;
        const span = document.createElement('span');
        span.textContent = lbl.text;
        span.style.position = 'absolute';
        span.style.transform = 'translateX(-50%)';
        span.style.top = `${(y as number) - 10}px`;
        span.style.left = `${x as number}px`;
        span.style.color = lbl.color;
        span.style.fontSize = '10px';
        span.style.fontWeight = '600';
        span.style.fontFamily = 'monospace';
        span.style.background = 'rgba(17, 24, 39, 0.85)';
        span.style.padding = '1px 5px';
        span.style.borderRadius = '3px';
        span.style.border = `1px solid ${lbl.color}`;
        span.style.whiteSpace = 'nowrap';
        span.style.pointerEvents = 'none';
        overlayEl.appendChild(span);
      }
    }
  };

  const overlayTradeEntries = () => {
    if (tradesPrimitiveRef.current && candlestickSeriesRef.current) {
      try { candlestickSeriesRef.current.detachPrimitive(tradesPrimitiveRef.current); } catch (e) { }
    }
    tradesPrimitiveRef.current = null;
    const tradesEl = document.getElementById('trades-labels-overlay');
    if (tradesEl) tradesEl.innerHTML = '';

    if (!showTrades || !backtestTradesData || !chartRef.current || !candlestickSeriesRef.current) {
      return;
    }

    const trades = backtestTradesData.trades ?? [];
    if (trades.length === 0) {
      return;
    }

    console.log('💼 Trades overlay activated. Loaded trades:', trades.length);
    const lastCandle = chartCandles.length > 0 ? chartCandles[chartCandles.length - 1]?.time : null;

    // ponytail: all lines drawn via canvas primitive, no series needed
    const primitive = tradesPrimitiveRef.current ?? new TradesOverlayPrimitive();
    candlestickSeriesRef.current.attachPrimitive(primitive);
    const entries: TradeOverlayEntry[] = trades.map(t => ({
      type: t.type, entry_price: t.entry_price, sl: t.sl, tp: t.tp,
      profit: t.profit, entry_time_ts: t.entry_time_ts, exit_time_ts: t.exit_time_ts,
    }));
    primitive.setTrades(entries);
    primitive.setLastCandleTime(lastCandle as number | null);
    primitive.setTimeframe(activeTimeframe); // Pass active timeframe
    tradesPrimitiveRef.current = primitive;
    renderTradesLabels(trades);
  };

  const overlayMarketStructure = async (candles?: Array<{ time: number, open: number, high: number, low: number, close: number }>, forceRefresh = false) => {
    if (!chartRef.current || !showStructure || !structureLines) return;

    // Prevent concurrent executions
    if (overlayGuardRef.current) {
      console.log('⏸️ overlayMarketStructure already running, skipping');
      return;
    }
    overlayGuardRef.current = true;

    // Use provided candles or fall back to state (for effect-triggered calls)
    const candlesToUse = candles ?? chartCandles;

    const shouldFilterByTimeframe = activeTimeframe === "M15";
    const filterByTimeframe = <T extends { timeframe?: string }>(items: T[] | undefined | null): T[] => {
      if (!items) return [];
      return shouldFilterByTimeframe ? items.filter((item) => item.timeframe === "M15") : items;
    };

    // Filter structure lines by date to only draw visible/recent lines (prevents drawing thousands of off-screen lines)
    const fromTimestamp = candlesToUse.length > 0 ? candlesToUse[0].time : Date.parse(chartFromDate) / 1000;
    const filterByDateRange = <T extends { timestamp: number }>(items: T[] | undefined | null): T[] => {
      if (!items) return [];
      const threshold = fromTimestamp - 7 * 24 * 3600; // 7-day padding
      return items.filter((item) => {
        const t = item.timestamp > 1e10 ? Math.floor(item.timestamp / 1000) : item.timestamp;
        return t >= threshold;
      });
    };

    const filteredBosLines = filterByDateRange(filterByTimeframe(structureLines.bos_lines));
    const filteredChochLines = filterByDateRange(filterByTimeframe(structureLines.choch_lines));
    const filteredHhPoints = filterByDateRange(filterByTimeframe(structureLines.hh_points));
    const filteredLlPoints = filterByDateRange(filterByTimeframe(structureLines.ll_points));

    // Build O(1) lookup map once — eliminates O(n) candle scans per line (n=200k)
    const candleTimeMap = new Map<number, ChartCandle>();
    const candleTimeArray: number[] = [];
    for (let i = 0; i < candlesToUse.length; i++) {
      const c = candlesToUse[i];
      candleTimeMap.set(c.time, c as ChartCandle);
      candleTimeArray.push(c.time);
    }
    // Binary search helper: returns index of first candle with time >= target
    const lowerBound = (target: number): number => {
      let lo = 0, hi = candleTimeArray.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (candleTimeArray[mid] < target) lo = mid + 1;
        else hi = mid;
      }
      return lo;
    };

    // Clear primitive lines
    structurePrimitiveRef.current?.setLines([]);

    // Helper: find when a price level was first formed in HH/LL data.
    const PRICE_TOLERANCE_VAL = 0.05;
    const getPriceBucket = (p: number) => Math.round(p / PRICE_TOLERANCE_VAL);

    // Pre-group HH points by price bucket for O(1) lookup
    const hhFormationMap = new Map<number, number>();
    filteredHhPoints.forEach(point => {
      const bucket = getPriceBucket(point.price);
      const t = point.timestamp > 1e10 ? Math.floor(point.timestamp / 1000) : point.timestamp;
      const existing = hhFormationMap.get(bucket);
      if (existing === undefined || t < existing) {
        hhFormationMap.set(bucket, t);
      }
    });

    // Pre-group LL points by price bucket for O(1) lookup
    const llFormationMap = new Map<number, number>();
    filteredLlPoints.forEach(point => {
      const bucket = getPriceBucket(point.price);
      const t = point.timestamp > 1e10 ? Math.floor(point.timestamp / 1000) : point.timestamp;
      const existing = llFormationMap.get(bucket);
      if (existing === undefined || t < existing) {
        llFormationMap.set(bucket, t);
      }
    });

    // Helper: find when a price level was first formed in HH/LL data.
    const findLevelFormationTime = (
      levelPrice: number,
      direction: string, // 'BULLISH' or 'BEARISH'
    ): number | undefined => {
      const isBullish = direction === 'BULLISH';
      const bucket = getPriceBucket(levelPrice);
      
      let matchTime: number | undefined;
      const mapToUse = isBullish ? hhFormationMap : llFormationMap;
      
      // Check target bucket and adjacent buckets for floating point tolerance
      for (const b of [bucket - 1, bucket, bucket + 1]) {
        const t = mapToUse.get(b);
        if (t !== undefined) {
          if (matchTime === undefined || t < matchTime) {
            matchTime = t;
          }
        }
      }
      return matchTime;
    };

    // Collect all lines to draw
    const linesToDraw: StructureLineItem[] = [];

    const createHorizontalLine = (
      price: number,
      timestamp: number,
      color: string,
      lineWidth: number,
      lineStyle: number,
      label: string,
      lineType?: 'HH' | 'LL' | 'BOS_CHOCH',
      levelFormationTime?: number, // For BoS/CHoCH: when the broken level was first formed (seconds)
    ) => {
      try {
        // CRITICAL: Check if timestamp is in milliseconds or seconds
        const isMilliseconds = timestamp > 10000000000;
        const eventTimeSeconds = isMilliseconds ? Math.floor(timestamp / 1000) : timestamp;
        
        // Determine start and end time based on line type
        let startTimeSeconds: number;
        let endTimeSeconds: number;
        
        const timeframePeriods: {[key: string]: number} = {
          'M15': 900,   // 15 minutes
          'M30': 1800,  // 30 minutes
          'H1': 3600,   // 1 hour
          'H4': 14400,  // 4 hours
          'D1': 86400,  // 1 day
        };

        const lastCandleTime: number | null = candlesToUse.length > 0
          ? candlesToUse[candlesToUse.length - 1].time
          : null;
        
        if (lineType === 'BOS_CHOCH') {
          const timeframePeriod = timeframePeriods[activeTimeframe] ?? 900;
          const formationFallback = Math.max(0, eventTimeSeconds - timeframePeriod);
          startTimeSeconds = levelFormationTime ?? formationFallback;
          endTimeSeconds = eventTimeSeconds;

          // find the first candle after formation whose high/low crosses `price`
          const dirUp = color === '#10b981';
          const bosStart = lowerBound(startTimeSeconds + 1);
          for (let i = bosStart; i < candleTimeArray.length; i++) {
            const candle = candlesToUse[i];
            if (candle.time > endTimeSeconds) break;
            const crossed = dirUp ? candle.high > price : candle.low < price;
            if (crossed) {
              endTimeSeconds = candle.time;
              break;
            }
          }
        } else {
          startTimeSeconds = eventTimeSeconds;
          endTimeSeconds = lastCandleTime ?? eventTimeSeconds;
        }
        
        // Find the breaking candle for HH/LL lines — cap at 20 candles after formation
        if (lineType === 'HH' || lineType === 'LL') {
          const hhStart = lowerBound(startTimeSeconds + 1);
          const endIdx = Math.min(hhStart + 20, candleTimeArray.length);
          let broke = false;
          for (let i = hhStart; i < endIdx; i++) {
            const candle = candlesToUse[i];
            if ((lineType === 'HH' ? candle.high > price : candle.low < price)) {
              endTimeSeconds = candle.time;
              broke = true;
              break;
            }
          }
          if (!broke && endIdx > hhStart) {
            endTimeSeconds = candlesToUse[endIdx - 1].time;
          }
        }
        
        // Always start line from the actual candle OPEN time (not close time)
        let actualStartTime = startTimeSeconds;
        const matchingCandle = candleTimeMap.get(startTimeSeconds);
        
        if (!matchingCandle) {
          const idx = lowerBound(startTimeSeconds);
          if (idx > 0) {
            actualStartTime = candleTimeArray[idx - 1];
          } else if (idx < candleTimeArray.length) {
            actualStartTime = candleTimeArray[idx];
          }
        }
        
        // Safety check: skip if start >= end
        if (actualStartTime >= endTimeSeconds) {
          return false;
        }

        // Add to our linesToDraw array instead of creating a series!
        linesToDraw.push({
          price,
          startTime: actualStartTime,
          endTime: endTimeSeconds,
          color,
          lineWidth,
          lineStyle,
          label,
          isResistance: lineType !== 'LL',
        });
        return true;
      } catch (e) {
        console.error('Error creating line:', e);
        return false;
      }
    };

    // Add BoS lines to queue
    filteredBosLines.forEach((bos) => {
      const color = bos.direction === 'BULLISH' ? '#10b981' : '#ef4444';
      const formationTime = bos.price
        ? findLevelFormationTime(bos.price, bos.direction)
        : undefined;
      createHorizontalLine(
        bos.price,
        bos.timestamp,
        color,
        2,
        LineStyle.Solid,
        `BoS ${bos.price.toFixed(2)}`,
        'BOS_CHOCH',
        formationTime,
      );
    });

    // Add CHoCH lines to queue
    filteredChochLines.forEach((choch) => {
      const eventTime = choch.timestamp;
      const formationTime = choch.price
        ? findLevelFormationTime(choch.price, choch.direction)
        : undefined;
      const color = choch.direction === 'BULLISH' ? '#10b981' : '#ef4444';
      createHorizontalLine(
        choch.price,
        eventTime,
        color,
        2,
        LineStyle.Dashed,
        `CHoCH ${choch.price.toFixed(2)}`,
        'BOS_CHOCH',
        formationTime,
      );
    });

    // Add HH lines to queue
    const bosChochPrices = new Set<number>();
    const PRICE_TOLERANCE = 0.05;
    const allBos = filteredBosLines;
    const allChoch = filteredChochLines;
    [...allBos, ...allChoch].forEach((evt) => {
      if (evt.price != null) {
        bosChochPrices.add(Math.round(evt.price / PRICE_TOLERANCE));
      }
    });
    const priceMatchesBosChoch = (price: number): boolean => {
      if (bosChochPrices.size === 0) return false;
      const key = Math.round(price / PRICE_TOLERANCE);
      return bosChochPrices.has(key) ||
             bosChochPrices.has(key - 1) ||
             bosChochPrices.has(key + 1);
    };

    if (filteredHhPoints && filteredHhPoints.length > 0) {
      filteredHhPoints.forEach((hh) => {
        if (priceMatchesBosChoch(hh.price)) return;
        const isH1 = hh.timeframe === 'H1';
        const color = isH1 ? '#1e40af' : '#60a5fa'; // Dark blue for H1, Light blue for M15
        const lineWidth = isH1 ? 2 : 1.5;
        const lineStyle = isH1 ? LineStyle.Dashed : LineStyle.Dotted;
        const label = `HH [${hh.timeframe}] ${hh.price.toFixed(2)}`;
        createHorizontalLine(
          hh.price,
          hh.timestamp,
          color,
          lineWidth,
          lineStyle,
          label,
          'HH',
        );
      });
    }

    // Add LL lines to queue
    if (filteredLlPoints && filteredLlPoints.length > 0) {
      filteredLlPoints.forEach((ll) => {
        if (priceMatchesBosChoch(ll.price)) return;
        const isH1 = ll.timeframe === 'H1';
        const color = isH1 ? '#c2410c' : '#fb923c'; // Dark orange for H1, Light orange for M15
        const lineWidth = isH1 ? 2 : 1.5;
        const lineStyle = isH1 ? LineStyle.Dashed : LineStyle.Dotted;
        const label = `LL [${ll.timeframe}] ${ll.price.toFixed(2)}`;
        createHorizontalLine(
          ll.price,
          ll.timestamp,
          color,
          lineWidth,
          lineStyle,
          label,
          'LL',
        );
      });
    }

    const totalLines = linesToDraw.length;

    // Show drawing progress popup
    setDrawLineProgress({ visible: true, percent: 0, current: 0, total: totalLines });

    // Draw in chunks of 50 lines to keep progress animation smooth (primitive update is instant)
    const chunkSize = Math.max(10, Math.ceil(totalLines / 20));
    for (let startIdx = 0; startIdx < totalLines; startIdx += chunkSize) {
      const endIdx = Math.min(startIdx + chunkSize, totalLines);
      const percent = Math.round((endIdx / totalLines) * 100);
      
      // Update progress state
      setDrawLineProgress({ visible: true, percent, current: endIdx, total: totalLines });

      // Yield control (10ms)
      await new Promise((resolve) => setTimeout(resolve, 10));
    }

    // Set lines to primitive at the end
    structurePrimitiveRef.current?.setLines(linesToDraw);

    // Hide progress popup
    setDrawLineProgress({ visible: false, percent: 100, current: totalLines, total: totalLines });

    console.log('\n✅ ===== OVERLAY COMPLETE =====');
    console.log('Total structure lines parsed:', totalLines);
    
    overlayGuardRef.current = false;
  };

  // Apply structure overlay when data changes or toggle state changes
  // Note: activeTimeframe changes are handled by loadChartData -> overlayMarketStructure(forceRefresh)
  useEffect(() => {
    // Handle toggle OFF state
    if (!showStructure) {
      structurePrimitiveRef.current?.setLines([]);
      structurePrimitiveRef.current?.setVisible(false);
      structureLinesVersionRef.current = '';

      const overlayEl = document.getElementById('structure-labels-overlay');
      if (overlayEl) {
        overlayEl.innerHTML = '';
      }
      return;
    }

    // Only draw when structure data actually changed (hash comparison prevents
    // redundant redraws from 30s refetch cycles with identical data)
    if (showStructure && structureLines && chartRef.current && candlestickSeriesRef.current && chartCandles.length > 0) {
      structurePrimitiveRef.current?.setVisible(true);
      // Mirror the filtering logic in overlayMarketStructure so the hash changes
      // when the active timeframe switches between M15 (filtered) and others (all).
      const shouldFilterByTimeframe = activeTimeframe === "M15";
      const filterCount = (items?: Array<{ timeframe?: string }>) => {
        if (!items) return 0;
        return shouldFilterByTimeframe
          ? items.filter((item) => item.timeframe === "M15").length
          : items.length;
      };
      const lastCandleTime = chartCandles.length > 0 ? chartCandles[chartCandles.length - 1].time : 0;
      const hash = `${activeTimeframe}|${chartCandles.length}|${lastCandleTime}|${structureLines.total_points}|${filterCount(structureLines.bos_lines)}|${filterCount(structureLines.choch_lines)}|${filterCount(structureLines.hh_points)}|${filterCount(structureLines.ll_points)}`;
      if (hash !== structureLinesVersionRef.current) {
        structureLinesVersionRef.current = hash;
        overlayMarketStructure(chartCandles);
      }
    }
  }, [showStructure, structureLines, chartCandles, activeTimeframe]);

  // Update session-zone shadows when data or toggle changes
  useEffect(() => {
    const primitive = sessionZonesPrimitiveRef.current;
    if (!primitive) {
      console.warn('⚠️ Session zones primitive not initialized');
      return;
    }

    primitive.setVisible(showSessions);

    const zones = sessionZonesData?.zones ?? [];
    const boxes: SessionZoneBox[] = zones
      .filter((z) => z.end_time > z.start_time)
      .map((z) => ({
        start: z.start_time,
        end: z.end_time,
        session: z.session,
        open: z.status === "OPEN",
      }));

    primitive.setBoxes(boxes);
    console.log('✅ Session zones updated successfully');
  }, [sessionZonesData, showSessions]);

  // Toggle EMA 200 visibility
  useEffect(() => {
    console.log('📉 [EMA DEBUG] showEMA200 toggled:', showEMA200);
    if (ema200SeriesRef.current) {
      ema200SeriesRef.current.applyOptions({ visible: showEMA200 });
      console.log('📉 [EMA DEBUG] EMA 200 visibility set to:', showEMA200);
    } else {
      console.warn('📉 [EMA DEBUG] ⚠️ Cannot toggle EMA 200 — series ref is NULL');
    }
  }, [showEMA200]);

  // On first chart data load — mark as loaded (zoom range is handled by loadChartData)
  useEffect(() => {
    console.log('📏 ChartCandles effect: trigger', {
      chartRef: !!chartRef.current,
      len: chartCandles.length,
      loaded: chartDataLoadedRef.current,
      first: chartCandles[0]?.time,
      last: chartCandles[chartCandles.length - 1]?.time,
    });
    if (!chartRef.current || chartCandles.length === 0 || chartDataLoadedRef.current) return;
    chartDataLoadedRef.current = true;
    // Disabled to prevent squashing/zooming out all history on refresh. The latest 250 candles zoom is managed by loadChartData.
    // const ts = chartRef.current.timeScale();
    // const first = chartCandles[0].time;
    // const last = chartCandles[chartCandles.length - 1].time;
    // const pad = (last - first) * 0.02;
    // ts.setVisibleRange({ from: (first - pad) as any, to: (last + pad) as any });
  }, [chartCandles]);

  // Toggle trade entries overlay
  useEffect(() => {
    overlayTradeEntries();
  }, [showTrades, backtestTradesData]);

  // Sync progress ref → state at 60fps during loading (avoids React batching swallows)
  useEffect(() => {
    if (!loadProgress.visible) return;
    let rafId: number;
    let currentPercent = 0;

    const sync = () => {
      setLoadProgress(prev => {
        // Guard: don't update if modal already closed
        if (!prev.visible) return prev;

        const l = latestProgressRef.current;

        let target = l.percent;
        // If backend hasn't reported progress yet, creep from 0% up to 18% slowly
        if (target <= 0) {
          currentPercent = Math.min(18, currentPercent + 0.12);
        } else {
          currentPercent = currentPercent + (target - currentPercent) * 0.15;
        }

        const displayVal = Math.min(100, Math.round(currentPercent));
        const displayStep = l.step || prev.step || 'Counting rows...';
        const displayTotal = l.total || prev.total || 0;

        // Auto-close once interpolated value hits 100 and backend confirms done
        if (displayVal >= 100 && target >= 100) {
          return { visible: false, percent: 100, step: '', total: displayTotal };
        }

        return displayVal !== prev.percent || displayStep !== prev.step || displayTotal !== prev.total
          ? { visible: true, percent: displayVal, step: displayStep, total: displayTotal }
          : prev;
      });
      rafId = requestAnimationFrame(sync);
    };
    rafId = requestAnimationFrame(sync);
    return () => cancelAnimationFrame(rafId);
  }, [loadProgress.visible]);

  const loadTradeHistory = async () => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';


      const response = await fetch(
        `${apiUrl}/trading/trades/history?days=30`
      );



      if (response.ok) {
        const data = await response.json();


        if (data.trades) {
          setTrades(data.trades);
          setStats({
            total_trades: data.total_trades ?? 0,
            win_rate: data.win_rate ?? 0,
            total_pnl: data.total_pnl ?? 0,
            open_positions: data.open_positions ?? 0,
          });

          return;
        }
      }
    } catch (error) {
      console.error("Error loading trades:", error);
      console.warn('⚠️ Unable to load trades data from MT5');
    }
  };

  const filterTrades = (filter: string) => {
    setActiveFilter(filter);
  };

  const changeTimeframe = (tf: string) => {
    console.log('🔄 Changing timeframe to:', tf);

    if (chartRef.current) {
      const timeScale = chartRef.current.timeScale();
      const visibleRange = timeScale.getVisibleRange();
      if (visibleRange) {
        const centerTime = ((visibleRange.from as number) + (visibleRange.to as number)) / 2;
        timeframeSwitchCenterTimeRef.current = centerTime;
        console.log("⏱️ Saved center time for timeframe switch:", new Date(centerTime * 1000).toISOString());
      }
    }

    // Check if we need to clear cache
    const previousTimeframe = activeTimeframe;
    const hasCachedData = !!(candleCacheRef.current[tf] && fullHistoryLoadedRef.current[tf]);
    if (previousTimeframe !== tf) {
      // Timeframe changed - check if new timeframe has cached data
      if (hasCachedData) {
        console.log(`✅ Timeframe ${tf} has cached data - will use cache`);
        setDataMode('full'); // Mark as full since we have cached data
      } else {
        console.log(`⚠️ Timeframe ${tf} has no cache - need to load data`);
        setDataMode('recent'); // Reset to recent mode for new timeframe
        // Note: Don't clear cache for old timeframe - keep it for when user switches back
      }
    }

    setActiveTimeframe(tf);

    // Reload with current mode (will use cache if available)
    if (chartRef.current && candlestickSeriesRef.current) {
      // If we have cache for this timeframe, use it instead of API call
      const cacheKey = tf;
      if (hasCachedData) {
        console.log('⚡ Using cached data for timeframe change');
        const cachedData = candleCacheRef.current[cacheKey];

        // Display cached data immediately
        updateLoadedCandles(cachedData.candles, cachedData.totalCount);
        setChartFromDate(cachedData.fromDate);
        if (showStructure && structureLines) {
          overlayMarketStructure(cachedData.candles, true);
        }
        fullDataDisplayedRef.current[cacheKey] = true;
      } else {
        // No cache - fetch from API
        loadChartData(true, 'recent', tf);
      }
    }
  };

  // DISABLED: year dropdown handler
  // const changeYear = (year: string) => {
  //   setActiveYear(year);
  //   monthsInitialized.current = false;
  //   if (chartRef.current && candlestickSeriesRef.current) {
  //     loadChartData(true, year);
  //   }
  // };

  // DISABLED: month scroll handler
  // const jumpToMonth = (unixStart: number) => {
  //   if (!chartRef.current) return;
  //   const ts = chartRef.current.timeScale();
  //   const vr = ts.getVisibleRange();
  //   if (!vr) return;
  //   const w = (vr.to as number) - (vr.from as number);
  //   ts.setVisibleRange({ from: unixStart as any, to: (unixStart + w) as any });
  // };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!chartContainerRef.current?.offsetParent) return;
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA") return;
      if (!chartRef.current) return;
      const ts = chartRef.current.timeScale();
      if (e.key === "ArrowLeft" && !e.shiftKey) {
        e.preventDefault();
        const lr = ts.getVisibleLogicalRange();
        if (!lr) return;
        const w = lr.to - lr.from;
        ts.setVisibleLogicalRange({ from: lr.from - w, to: lr.to - w });
      } else if (e.key === "ArrowRight" && !e.shiftKey) {
        e.preventDefault();
        const lr = ts.getVisibleLogicalRange();
        if (!lr) return;
        const w = lr.to - lr.from;
        ts.setVisibleLogicalRange({ from: lr.from + w, to: lr.to + w });
      } else if (e.key === "ArrowLeft" && e.shiftKey) {
        e.preventDefault();
        const vr = ts.getVisibleRange();
        if (!vr) return;
        const from = vr.from as number;
        const w = (vr.to as number) - from;
        const d = new Date(from * 1000);
        d.setUTCMonth(d.getUTCMonth() - 1);
        const newFrom = Math.floor(d.getTime() / 1000);
        ts.setVisibleRange({ from: newFrom as any, to: (newFrom + w) as any });
      } else if (e.key === "ArrowRight" && e.shiftKey) {
        e.preventDefault();
        const vr = ts.getVisibleRange();
        if (!vr) return;
        const from = vr.from as number;
        const w = (vr.to as number) - from;
        const d = new Date(from * 1000);
        d.setUTCMonth(d.getUTCMonth() + 1);
        const newFrom = Math.floor(d.getTime() / 1000);
        ts.setVisibleRange({ from: newFrom as any, to: (newFrom + w) as any });
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const filteredTrades = trades.filter((trade) => {
    if (activeFilter === "all") return true;
    if (activeFilter === "open") return trade.status === "OPEN";
    if (activeFilter === "closed") return trade.status === "CLOSED";
    if (activeFilter === "profit") return trade.pnl > 0;
    if (activeFilter === "loss") return trade.pnl < 0;
    return true;
  });

  return (
    <div
      style={{
        background: "var(--bg-deepspace)",
        minHeight: "100vh",
        width: "100%",
        position: "relative",
        overflowX: "hidden",
        overflowY: "auto"
      }}
    >
      <Particles
        id="tsparticles-trades"
        options={{
          background: { color: { value: "transparent" } },
          fpsLimit: 60,
          particles: {
            number: { value: 80, density: { enable: true } },
            color: { value: "#3b82f6" },
            shape: { type: "circle" },
            opacity: { value: 0.3 },
            size: { value: { min: 1, max: 3 } },
            links: {
              enable: true,
              distance: 150,
              color: "#3b82f6",
              opacity: 0.2,
              width: 1,
            },
            move: {
              enable: true,
              speed: 1,
              direction: "none",
              outModes: { default: "out" },
            },
          },
          interactivity: {
            events: {
              onHover: { enable: true, mode: "grab" },
              onClick: { enable: true, mode: "push" },
            },
            modes: {
              grab: { distance: 140, links: { opacity: 0.5 } },
              push: { quantity: 4 },
            },
          },
        }}
        className="fixed inset-0 pointer-events-none"
        style={{ zIndex: 0 }}
      />

      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          zIndex: 1,
          background:
            "radial-gradient(circle at 20% 50%, rgba(59, 130, 246, 0.15) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.15) 0%, transparent 50%), radial-gradient(circle at 50% 80%, rgba(16, 185, 129, 0.1) 0%, transparent 50%), var(--bg-deepspace)",
        }}
      />

      {/* Sidebar */}
      <div
        className="relative z-10"
        style={{
          width: "100%",
          paddingLeft: "240px", // Space for sidebar (exact sidebar width)
          minHeight: "calc(149vh - 0px)" // Full height minus any top offset
        }}
      >
        <div className="w-full px-12 py-8">

          {/* Page Header */}
          <div className="mb-8">
            <h1 className="text-[36px] font-bold mb-3 bg-gradient-to-r from-[var(--neon-blue)] to-[var(--neon-cyan)] bg-clip-text text-transparent">
              📊 Trading History
            </h1>
            <p className="text-[var(--text-tertiary)] text-base">
              View your trades, analyze performance, and track live positions
            </p>
          </div>

          {/* Stats Grid - Fixed Position */}
          <div className="grid grid-cols-4 gap-6 mb-8">
            <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1">
              <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
                Total Trades
              </div>
              <div className="text-2xl font-semibold mono mb-1">
                {stats.total_trades}
              </div>
              <div className="text-sm text-[var(--text-tertiary)]">Last 30 days</div>
            </div>

            <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1">
              <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
                Win Rate
              </div>
              <div className={`text-2xl font-semibold mono mb-1 ${stats.win_rate >= 50 ? 'positive' : 'negative'}`}>
                {stats.win_rate.toFixed(1)}%
              </div>
              <div className="text-sm text-[var(--text-tertiary)]">Winning percentage</div>
            </div>

            <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1">
              <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
                Total P&L
              </div>
              <div className={`text-2xl font-semibold mono mb-1 ${stats.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                {stats.total_pnl >= 0 ? '+' : ''}${stats.total_pnl.toFixed(2)}
              </div>
              <div className="text-sm text-[var(--text-tertiary)]">Profit & Loss</div>
            </div>

            <div className="glass-card !p-5 !mb-0 hover:scale-105 hover:-translate-y-1">
              <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
                Open Positions
              </div>
              <div className="text-2xl font-semibold neutral mono mb-1">
                {stats.open_positions}
              </div>
              <div className="text-sm text-[var(--text-tertiary)]">
                {stats.open_positions === 0 ? 'No active trades' : `${stats.open_positions} active trade${stats.open_positions > 1 ? 's' : ''}`}
              </div>
            </div>
          </div>

          {/* Chart Section */}
          <div className="glass-card mb-8">
            <div className="mb-5">
              <ChartToolbar
                title={<span className="text-xl font-semibold">📈 XAUUSD {activeTimeframe} Chart</span>}
                activeTimeframe={activeTimeframe}
                onTimeframeChange={changeTimeframe}
                selectedYear={selectedYear}
                onYearChange={handleYearChange}
                selectedMonth={selectedMonth}
                onMonthChange={handleMonthChange}
                availableYears={availableYears}
                availableMonths={availableMonths}
                chartTimezone={chartTimezone}
                onTimezoneChange={handleTimezoneChange}
                showStructure={showStructure}
                onToggleStructure={() => setShowStructure((prev) => !prev)}
                showSessions={showSessions}
                onToggleSessions={() => setShowSessions((prev) => !prev)}
                showEMA200={showEMA200}
                onToggleEMA200={() => setShowEMA200((prev) => !prev)}
                showTrades={showTrades}
                onToggleTrades={() => setShowTrades((prev) => !prev)}
                structureLines={structureLines}
                sessionZonesData={sessionZonesData}
                backtestTradesData={backtestTradesData}
                isFullHistoryLoaded={!!fullHistoryLoadedRef.current[activeTimeframe]}
                dataMode={dataMode}
                candlesCount={candlesCount}
                onRefresh={() => loadChartData(true, dataMode as "recent" | "full")}
                onLoadFullHistory={loadFullHistory}
                onZoomIn={handleZoomIn}
                onZoomOut={handleZoomOut}
                onResetZoom={handleResetZoom}
                isJumping={isJumping}
              />
            </div>
            <div
              ref={chartContainerRef}
              id="chart-container"
              className="w-full rounded-xl overflow-hidden relative bg-slate-950/20"
              style={{ height: "700px" }}
            >
              <div
                id="structure-labels-overlay"
                className="absolute inset-0 pointer-events-none overflow-hidden"
                style={{ zIndex: 10 }}
              />
              <div
                id="trades-labels-overlay"
                className="absolute inset-0 pointer-events-none overflow-hidden"
                style={{ zIndex: 11 }}
              />
            </div>
          </div>

          {/* Tab Switcher for Bottom Section */}
          <div className="flex gap-4 mb-4">
            <button
              onClick={() => setActiveBottomTab('recent-trades')}
              className={`px-5 py-3 rounded-xl font-semibold text-sm transition-all flex items-center gap-2 cursor-pointer ${activeBottomTab === 'recent-trades'
                ? "bg-[var(--neon-blue)] text-white shadow-[0_0_20px_rgba(59,130,246,0.35)]"
                : "bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-slate-800"
                }`}
            >
              <span>💼</span> Recent Trades
            </button>
            <button
              onClick={() => setActiveBottomTab('monthly-summary')}
              className={`px-5 py-3 rounded-xl font-semibold text-sm transition-all flex items-center gap-2 cursor-pointer ${activeBottomTab === 'monthly-summary'
                ? "bg-[var(--neon-blue)] text-white shadow-[0_0_20px_rgba(59,130,246,0.35)]"
                : "bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-slate-800"
                }`}
            >
              <span>📋</span> Monthly Summary
            </button>
          </div>

          {activeBottomTab === 'recent-trades' ? (
            <div className="glass-card">
              <div className="flex justify-between items-center mb-6">
                <span className="text-xl font-semibold">💼 Recent Trades</span>

                {/* Filter Tabs */}
                <div className="flex gap-2">
                  {["all", "open", "closed", "profit", "loss"].map((filter) => (
                    <button
                      key={filter}
                      onClick={() => filterTrades(filter)}
                      className={`px-4 py-2 rounded-lg text-sm transition-all capitalize ${activeFilter === filter
                        ? "bg-[var(--neon-blue)] text-white shadow-[0_0_15px_rgba(59,130,246,0.4)]"
                        : "bg-[var(--glass-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                        }`}
                    >
                      {filter}
                    </button>
                  ))}
                </div>
              </div>

              {/* Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[rgba(100,116,139,0.2)]">
                      <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-[var(--text-tertiary)]">
                        Trade ID
                      </th>
                      <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-[var(--text-tertiary)]">
                        Symbol
                      </th>
                      <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-[var(--text-tertiary)]">
                        Type
                      </th>
                      <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-[var(--text-tertiary)]">
                        Entry
                      </th>
                      <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-[var(--text-tertiary)]">
                        Exit
                      </th>
                      <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-[var(--text-tertiary)]">
                        Lot Size
                      </th>
                      <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-[var(--text-tertiary)]">
                        P&L
                      </th>
                      <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-[var(--text-tertiary)]">
                        Status
                      </th>
                      <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-[var(--text-tertiary)]">
                        Time
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTrades.length === 0 ? (
                      <tr>
                        <td
                          colSpan={9}
                          className="text-center py-12 text-[var(--text-tertiary)]"
                        >
                          No trades found
                        </td>
                      </tr>
                    ) : (
                      filteredTrades.map((trade) => (
                        <tr
                          key={trade.trade_id}
                          className="border-b border-[rgba(100,116,139,0.1)] hover:bg-[var(--bg-elevated)] transition-colors"
                        >
                          <td className="py-3 px-4 mono text-xs">
                            {trade.trade_id.substring(0, 8)}...
                          </td>
                          <td className="py-3 px-4 font-medium">
                            {trade.symbol}
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`inline-block px-2 py-1 rounded text-xs font-semibold ${trade.type === "BUY"
                                ? "bg-[rgba(16,185,129,0.2)] text-[var(--neon-emerald)]"
                                : "bg-[rgba(239,68,68,0.2)] text-[var(--neon-ruby)]"
                                }`}
                            >
                              {trade.type}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right mono">
                            {trade.entry_price.toFixed(2)}
                          </td>
                          <td className="py-3 px-4 text-right mono">
                            {trade.exit_price ? trade.exit_price.toFixed(2) : "-"}
                          </td>
                          <td className="py-3 px-4 text-right mono">
                            {trade.lot_size.toFixed(2)}
                          </td>
                          <td className="py-3 px-4 text-right mono">
                            <span
                              className={`font-semibold ${trade.pnl >= 0 ? "positive" : "negative"
                                }`}
                            >
                              {trade.pnl >= 0 ? "+" : ""}${trade.pnl.toFixed(2)}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span
                              className={`inline-block px-2 py-1 rounded text-xs font-semibold ${trade.status === "OPEN"
                                ? "bg-[rgba(251,191,36,0.2)] text-[var(--neon-amber)]"
                                : trade.pnl >= 0
                                  ? "bg-[rgba(16,185,129,0.2)] text-[var(--neon-emerald)]"
                                  : "bg-[rgba(239,68,68,0.2)] text-[var(--neon-ruby)]"
                                }`}
                            >
                              {trade.status}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-sm text-[var(--text-tertiary)]">
                            {new Date(trade.open_time).toLocaleString()}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="glass-card">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <h2 className="text-xl font-semibold">📋 Monthly Performance Summary</h2>

                {/* Filter Controls (Year Dropdown & Profit/Loss Tabs mixed with glassmorphism) */}
                <div className="flex flex-wrap items-center gap-3">
                  {/* Year Select Dropdown (Custom Glassmorphism) */}
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
                        {/* Invisible backdrop click handler to close dropdown */}
                        <div
                          className="fixed inset-0 z-40"
                          onClick={() => setIsYearDropdownOpen(false)}
                        />
                        <div className="absolute right-0 mt-1.5 w-24 bg-slate-900/90 border border-slate-800 rounded-lg shadow-2xl backdrop-blur-xl z-50 overflow-hidden py-1 animate-in fade-in slide-in-from-top-1 duration-150">
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
                    {(['all', 'profit', 'loss'] as const).map((perfFilter) => (
                      <button
                        key={perfFilter}
                        onClick={() => setMonthlySummaryPerformanceFilter(perfFilter)}
                        className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${monthlySummaryPerformanceFilter === perfFilter
                          ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)]"
                          : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/40"
                          }`}
                      >
                        {perfFilter === 'all' ? 'Semua' : perfFilter === 'profit' ? 'Profit Only' : 'Loss Only'}
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
                          <td className="px-4 py-3.5 whitespace-nowrap font-medium text-slate-200">{month.month_label || `${month.month ?? 'N/A'}-${month.year ?? ''}`}</td>
                          <td className="px-4 py-3.5 whitespace-nowrap mono">{month.executed_trades ?? month.trades ?? 0}</td>
                          <td className={`px-4 py-3.5 whitespace-nowrap font-semibold ${
                            (month.win_rate ?? 0) > 50
                              ? "positive"
                              : (month.win_rate ?? 0) === 50
                              ? "text-white"
                              : "negative"
                          }`}>
                            {(month.win_rate ?? 0).toFixed(1)}%
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap mono font-semibold positive">{(month.profit ?? 0).toFixed(2)}</td>
                          <td className="px-4 py-3.5 whitespace-nowrap mono font-semibold negative">{(month.loss ?? 0).toFixed(2)}</td>
                          <td className={`px-4 py-3.5 whitespace-nowrap mono font-semibold ${(month.net_profit ?? 0) >= 0 ? "positive" : "negative"}`}>
                            {(month.net_profit ?? 0) >= 0 ? "+" : ""}{(month.net_profit ?? 0).toFixed(2)}
                          </td>
                          <td className={`px-4 py-3.5 whitespace-nowrap mono font-semibold ${((month.net_profit ?? 0) / 1000 * 100) >= 0 ? "positive" : "negative"}`}>
                            {((month.net_profit ?? 0) / 1000 * 100).toFixed(2)}%
                          </td>
                        </tr>
                      ));
                    })()}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Progress popup for Load Full History */}
        {loadProgress.visible && (
          <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center z-50 animate-in fade-in duration-300">
            <div 
              className="bg-slate-900/90 border border-purple-500/25 rounded-2xl p-6 w-96 shadow-[inset_0_1px_0_rgba(255,255,255,0.1),_0_25px_60px_rgba(0,0,0,0.8),_0_0_45px_rgba(168,85,247,0.18)] transform perspective-1000 rotate-x-6 animate-in zoom-in-90 duration-350 ease-out"
              style={{ transformStyle: "preserve-3d" }}
            >
              <div className="flex flex-col items-center justify-center text-center mb-5">
                <div className="relative flex items-center justify-center w-12 h-12 mb-3 bg-purple-500/10 rounded-full border border-purple-500/25 shadow-[0_0_15px_rgba(168,85,247,0.2)]">
                  <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
                </div>
                <div className="text-purple-300 font-semibold text-xs tracking-wider uppercase mb-1">
                  Loading Full History
                </div>
                <div className="text-3xl font-mono font-bold text-white mb-1 shadow-sm">
                  {loadProgress.percent}%
                </div>
                <div className="text-[10px] font-medium text-slate-400 max-w-[240px] truncate mb-0.5">{loadProgress.step}</div>
                <div className="text-[9px] font-mono text-slate-500">
                  {loadProgress.total.toLocaleString()} total rows
                </div>
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

        {/* Progress popup for Drawing Lines */}
        {drawLineProgress.visible && (
          <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center z-50 animate-in fade-in duration-300">
            <div 
              className="bg-slate-900/90 border border-cyan-500/25 rounded-2xl p-6 w-96 shadow-[inset_0_1px_0_rgba(255,255,255,0.1),_0_25px_60px_rgba(0,0,0,0.8),_0_0_45px_rgba(6,182,212,0.18)] transform perspective-1000 rotate-x-6 animate-in zoom-in-90 duration-350 ease-out"
              style={{ transformStyle: "preserve-3d" }}
            >
              <div className="flex flex-col items-center justify-center text-center mb-5">
                <div className="relative flex items-center justify-center w-12 h-12 mb-3 bg-cyan-500/10 rounded-full border border-cyan-500/25 shadow-[0_0_15px_rgba(6,182,212,0.2)]">
                  <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
                </div>
                <div className="text-cyan-300 font-semibold text-xs tracking-wider uppercase mb-1">
                  Drawing Structure Lines
                </div>
                <div className="text-3xl font-mono font-bold text-white mb-1 shadow-sm">
                  {drawLineProgress.percent}%
                </div>
                <div className="text-[10px] font-medium text-slate-400 max-w-[240px] truncate">
                  Drawing line {drawLineProgress.current} of {drawLineProgress.total}
                </div>
              </div>
              <div className="w-full h-3 bg-slate-950/80 border border-slate-800/40 rounded-full shadow-[inset_0_2px_4px_rgba(0,0,0,0.8)] relative overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-500 rounded-full transition-all duration-150 shadow-[0_0_12px_rgba(6,182,212,0.5)] relative overflow-hidden"
                  style={{ width: `${drawLineProgress.percent}%` }}
                >
                  {/* cylindrical light reflection gloss overlay */}
                  <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.15),transparent)]" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Monthly Trades Detail Modal */}
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
                        <span className="text-2xl font-bold text-slate-200 mono">{selectedMonthTrades.length}</span>
                      </div>
                      <div className="bg-slate-950/30 border border-slate-800/60 rounded-xl p-4 flex flex-col">
                        <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">Win Rate</span>
                        <span className="text-2xl font-bold text-cyan-400 mono">
                          {(() => {
                            const wins = selectedMonthTrades.filter(t => t.net_profit > 0).length;
                            return ((wins / selectedMonthTrades.length) * 100).toFixed(1);
                          })()}%
                        </span>
                      </div>
                      <div className="bg-slate-950/30 border border-slate-800/60 rounded-xl p-4 flex flex-col">
                        <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">Net P&L</span>
                        <span className={`text-2xl font-bold mono ${selectedMonthTrades.reduce((sum, t) => sum + t.net_profit, 0) >= 0 ? "text-emerald-400" : "text-rose-500"
                          }`}>
                          {selectedMonthTrades.reduce((sum, t) => sum + t.net_profit, 0) >= 0 ? "+" : ""}
                          ${selectedMonthTrades.reduce((sum, t) => sum + t.net_profit, 0).toFixed(2)}
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
                                const isWin = trade.net_profit >= 0;
                                return (
                                  <tr key={trade.ticket} className="hover:bg-slate-800/30 transition-colors">
                                    <td className="py-3 px-4 mono text-xs text-slate-400">#{trade.ticket}</td>
                                    <td className="py-3 px-4">
                                      <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${trade.type === "BUY"
                                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                        : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                                        }`}>
                                        {trade.type}
                                      </span>
                                    </td>
                                    <td className="py-3 px-4 text-right mono">{(getActualLotSize(trade)).toFixed(2)}</td>
                                    <td className="py-3 px-4 text-right mono">${trade.entry_price.toFixed(2)}</td>
                                    <td className="py-3 px-4 text-right mono">${trade.exit_price.toFixed(2)}</td>
                                    <td className={`py-3 px-4 text-right mono font-semibold ${isWin ? "text-emerald-400" : "text-rose-500"
                                      }`}>
                                      {isWin ? "+" : ""}${trade.net_profit.toFixed(2)}
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

        {/* Footer - Sticky to bottom */}
        <div>
          <MT5Footer />
        </div>
      </div>
    </div>
  );
}

