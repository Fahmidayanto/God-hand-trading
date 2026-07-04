import { useEffect, useRef, useState } from "react";
import { 
  createChart, 
  type IChartApi, 
  type ISeriesApi,
  CandlestickSeries,
  LineSeries,
  LineStyle,
} from "lightweight-charts";
import Particles from "@tsparticles/react";
import { loadSlim } from "@tsparticles/slim";
import type { Engine } from "@tsparticles/engine";
import { useRongsokanMarketStructureLines, useSessionZones, useRongsokanBacktestTrades, useRongsokanChartData, type BacktestTrade } from "@/api/mt5_agents";
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

export default function RongsokanPage() {
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
  const [dataMode, setDataMode] = useState<'recent' | 'full' | 'window'>('recent');
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
  const [chartTimezone, setChartTimezone] = useState<{broker_offset_hours: number, display_mode: string, candle_times_are_utc: boolean}>({
    broker_offset_hours: 3,
    display_mode: 'utc', // Default to UTC on every page open
    candle_times_are_utc: true
  });

  const [activeYear, setActiveYear] = useState<string>("2026");
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
  const fullHistoryLoadedRef = useRef<{[key: string]: boolean}>({});
  
  // Track if full cached data is currently DISPLAYED on chart (not just cached).
  // Prevents redundant setData + overlay rebuild on year/month jumps within same timeframe.
  const fullDataDisplayedRef = useRef<{[key: string]: boolean}>({});
  
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
  const { data: structureLines } = useRongsokanMarketStructureLines("2020-01-01");

  // Load session zones - sync with chart data mode
  const { data: sessionZonesData } = useSessionZones(chartFromDate);

  // Load backtest trades for Entry/SL/TP overlay
  const { data: backtestTradesData } = useRongsokanBacktestTrades();

  // Load chart data using Rongsokan hook
  const { data: chartData, refetch: refetchChartData } = useRongsokanChartData(
    "XAUUSD",
    activeTimeframe,
    chartFromDate,
    dataMode,
    dataMode === 'window' ? `${selectedYear}-${selectedMonth}-01` : undefined
  );

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

  const particlesInit = async (engine: Engine) => {
    await loadSlim(engine);
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
              console.log('🕐 Initial formatter called, using ref:', {
                displayMode: currentTimezone.display_mode,
                brokerOffset: currentTimezone.broker_offset_hours
              });
              return formatChartTime(time, currentTimezone.display_mode, currentTimezone.broker_offset_hours);
            },
          },
        });

        // Log timezone info
        const timezoneOffset = new Date().getTimezoneOffset();
        console.log('🕐 Browser timezone offset (minutes):', timezoneOffset);
        console.log('🕐 This means browser is:', timezoneOffset > 0 ? `GMT-${timezoneOffset/60}` : `GMT+${-timezoneOffset/60}`);

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

        // Hook returns the data once, but if it fetched before the chart series
        // existed the data effect would have skipped setData. Trigger a refetch
        // now that the series is ready so the candles render.
        chartDataLoadedRef.current = false;
        refetchChartData();
      } catch (error) {
        console.error('❌ Error creating chart:', error);
      }
    } else {
      console.log('⏭️ Skipping chart init: already initialized or container not ready');
    }

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0 && chartRef.current) {
          chartRef.current.applyOptions({ width, height });
        }
      }
    });

    if (chartContainerRef.current) resizeObserver.observe(chartContainerRef.current);

    const intersectionObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && chartRef.current && chartContainerRef.current) {
          chartRef.current.applyOptions({
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
          });
        }
      });
    });
    if (chartContainerRef.current) intersectionObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
    };
  }, []);

  // Listen for arrow key events to scroll the chart timescale left/right
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in an input/select/textarea
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "SELECT" ||
        document.activeElement?.tagName === "TEXTAREA" ||
        document.activeElement?.getAttribute("contenteditable") === "true"
      ) {
        return;
      }

      if (!chartRef.current) return;

      const timeScale = chartRef.current.timeScale();
      const currentScroll = timeScale.scrollPosition();

      // Calculate scroll speed to represent exactly 1 day (24 hours) based on current timeframe
      let SCROLL_SPEED = 96; // Default for M15 (24 hours * 4 candles/hour)
      if (activeTimeframe === "H1") {
        SCROLL_SPEED = 24; // 24 hours * 1 candle/hour
      } else if (activeTimeframe === "H4") {
        SCROLL_SPEED = 6;  // 24 hours / 4 hours/candle
      } else if (activeTimeframe === "D1" || activeTimeframe === "D") {
        SCROLL_SPEED = 1;  // 1 candle per day
      }

      if (e.key === "ArrowLeft") {
        e.preventDefault();
        timeScale.scrollToPosition(currentScroll - SCROLL_SPEED, false);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        timeScale.scrollToPosition(currentScroll + SCROLL_SPEED, false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [activeTimeframe]);

  // Load trade history - using Rongsokan trades
  useEffect(() => {
    if (backtestTradesData && backtestTradesData.trades) {
      const formattedTrades = backtestTradesData.trades.map((t, i) => ({
        trade_id: `#TRD-${String(i + 1).padStart(3, '0')}`,
        symbol: "XAUUSD",
        type: t.type,
        entry_price: t.entry_price,
        exit_price: t.exit_time_ts ? t.entry_price + (t.type === "BUY" ? 10 : -10) : null,
        lot_size: t.lot_size,
        pnl: t.profit,
        status: t.exit_time_ts ? "CLOSED" : "OPEN",
        open_time: t.entry_time,
      }));
      setTrades(formattedTrades);
      
      const totalPnl = formattedTrades.reduce((sum, t) => sum + t.pnl, 0);
      const winCount = formattedTrades.filter(t => t.pnl > 0).length;
      const totalTrades = formattedTrades.length;
      const winRate = totalTrades > 0 ? (winCount / totalTrades) * 100 : 0;
      
      setStats({
        total_trades: totalTrades,
        win_rate: Math.round(winRate * 10) / 10,
        total_pnl: Math.round(totalPnl * 100) / 100,
        open_positions: formattedTrades.filter(t => t.status === "OPEN").length,
      });
    }
  }, [backtestTradesData]);

  // Handle chart data from hook
  useEffect(() => {
    if (chartData && chartData.candles && candlestickSeriesRef.current) {
      console.log('✅ Chart data received from hook:', {
        mode: chartData.mode,
        from_date: chartData.from_date,
        candles: chartData.candles?.length,
        candlesCount: chartData.candles_count,
      });
      
      const processedCandles = processCandles(chartData.candles);
      
      const timeScale = chartRef.current?.timeScale();
      const currentVisibleRange = timeScale?.getVisibleRange();
      
      updateLoadedCandles(processedCandles, chartData.candles_count || processedCandles.length);
      if (chartData.mode === 'full' && processedCandles.length > 0) {
        cacheFullHistory(activeTimeframe, processedCandles);
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
        } else if (chartDataLoadedRef.current && currentVisibleRange) {
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
        }
      }
      
      chartDataLoadedRef.current = true;
      
      // Update mode state if loading was triggered
      setDataMode(chartData.mode as any);
          
      // Store timezone info from API.
      if (chartData.timezone) {
        if (userChangedTimezone.current) {
          // Keep user's manually chosen mode, just refresh broker offset
          setChartTimezone(prev => ({
            ...prev,
            broker_offset_hours: chartData.timezone.broker_offset_hours ?? prev.broker_offset_hours,
          }));
          console.log('🚫 Skipping display_mode override (user manually changed it); refreshed broker offset only');
        } else {
          // Default path: force UTC as the display mode, only adopt broker offset from API
          setChartTimezone(prev => ({
            ...prev,
            broker_offset_hours: chartData.timezone.broker_offset_hours ?? prev.broker_offset_hours,
            display_mode: 'utc',
          }));
          console.log('🌍 Defaulting chart display_mode to UTC (broker offset from API:', chartData.timezone.broker_offset_hours, ')');
        }
      }
      console.log(`✅ Chart data loaded successfully (${chartData.mode} mode)`);
      
      // Trigger structure overlay with fresh candle data
      if (showStructure && structureLines) {
        console.log('🔄 Triggering structure overlay');
        overlayMarketStructure(processedCandles, true);
      }
    }
  }, [chartData, activeTimeframe, dataMode, chartFromDate, showStructure, structureLines]);

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
          refetchChartData();
        } else {
          console.log('⏸️ Skipping auto-refresh (user is viewing historical data)');
        }
      }
    }, 30000); // 30 seconds instead of 5 seconds
    return () => clearInterval(chartInterval);
  }, [activeTimeframe, activeYear, dataMode, chartFromDate, isJumping, refetchChartData]);

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

  // Load full history function with caching
  const loadFullHistory = async () => {
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

    setDataMode('full');
    setChartFromDate('2020-01-01');

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const chartUrl = `${apiUrl}/trading/chart/rongsokan-data-stream?symbol=XAUUSD&timeframe=${activeTimeframe}&from_date=2020-01-01&mode=full`;

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
    setDataMode('full');
    
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const chartUrl = `${apiUrl}/trading/chart/rongsokan-data?symbol=XAUUSD&timeframe=${activeTimeframe}&center_date=${centerDate}`;
      
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
          from: ((visibleRange.from as number) - 0.0001) as any,
          to: ((visibleRange.to as number) + 0.0001) as any,
        };
        console.log("  Setting temp range:", tempRange);
        timeScale.setVisibleRange(tempRange);

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
    startTime: number;
    endTime: number;
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
      startTime: number;
      endTime: number;
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

    const timeScale = chartRef.current.timeScale();
    const visibleRange = timeScale.getVisibleRange();
    const visibleFrom = visibleRange ? Number(visibleRange.from) : null;
    const visibleTo = visibleRange ? Number(visibleRange.to) : null;

    for (const lbl of labels) {
      // Place the label at the geometric MIDDLE of its line (lbl.time is the
      // candle nearest the midpoint between startTime and endTime). Skip drawing
      // only when the line is fully outside the visible range (perf).
      if (visibleFrom !== null && visibleTo !== null) {
        if (lbl.endTime < visibleFrom || lbl.startTime > visibleTo) continue;
      }
      const labelTime = lbl.time;

      const x = timeScale.timeToCoordinate(labelTime as any);
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
      try { candlestickSeriesRef.current.detachPrimitive(tradesPrimitiveRef.current); } catch (e) {}
    }
    tradesPrimitiveRef.current = null;
    const tradesEl = document.getElementById('trades-labels-overlay');
    if (tradesEl) tradesEl.innerHTML = '';

    if (!showTrades || !backtestTradesData || !chartRef.current || !candlestickSeriesRef.current) {
      console.log('[overlayTradeEntries] SKIP:', { showTrades, hasData: !!backtestTradesData, hasChart: !!chartRef.current, hasSeries: !!candlestickSeriesRef.current });
      return;
    }

    const trades = backtestTradesData.trades ?? [];
    console.log('[overlayTradeEntries] Total trades from API:', trades.length);
    if (trades.length === 0) {
      return;
    }

    // Debug: Check trades distribution by year
    const tradesByYear = trades.reduce((acc, t) => {
      const year = new Date(t.entry_time_ts * 1000).getFullYear();
      acc[year] = (acc[year] || 0) + 1;
      return acc;
    }, {} as Record<number, number>);
    console.log('[overlayTradeEntries] Trades by year:', tradesByYear);

    // Debug: Show sample 2026 trades
    const trades2026 = trades.filter(t => new Date(t.entry_time_ts * 1000).getFullYear() === 2026);
    console.log('[overlayTradeEntries] 2026 trades sample:', trades2026.slice(0, 3).map(t => ({
      type: t.type,
      entry_price: t.entry_price,
      entry_time: new Date(t.entry_time_ts * 1000).toISOString(),
      exit_time: t.exit_time_ts ? new Date(t.exit_time_ts * 1000).toISOString() : null,
      sl: t.sl,
      tp: t.tp,
    })));

    const lastCandle = chartCandles.length > 0 ? chartCandles[chartCandles.length - 1]?.time : null;
    console.log('[overlayTradeEntries] Last candle time:', lastCandle, lastCandle ? new Date(lastCandle * 1000).toISOString() : null);
    
    // Debug: Chart candles time range
    if (chartCandles.length > 0) {
      const firstCandle = chartCandles[0]?.time;
      console.log('[overlayTradeEntries] Chart candles range:', {
        first: new Date(firstCandle * 1000).toISOString(),
        last: new Date(lastCandle! * 1000).toISOString(),
        total: chartCandles.length,
      });
    }

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

  const overlayMarketStructure = async (candles?: Array<{time: number, open: number, high: number, low: number, close: number}>, forceRefresh = false) => {
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
    const fromTimestamp = Date.parse(chartFromDate) / 1000;
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
    const linesToPrimitive: StructureLineItem[] = [];

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
        // Get visible time range from chart
        const timeScale = chartRef.current!.timeScale();
        const visibleRange = timeScale.getVisibleRange();
        
        // CRITICAL: Check if timestamp is in milliseconds or seconds
        const isMilliseconds = timestamp > 10000000000;
        const eventTimeSeconds = isMilliseconds ? Math.floor(timestamp / 1000) : timestamp;
        
        // Determine start and end time based on line type
        let startTimeSeconds: number;
        let endTimeSeconds: number;
        
        // Period map used to size the BoS/CHoCH fallback segment when no
        // formation time is found in HH/LL data. Declared here so both
        // branches (BOS_CHOCH and HH/LL) can reference it.
        const timeframePeriods: {[key: string]: number} = {
          'M15': 900,   // 15 minutes
          'M30': 1800,  // 30 minutes
          'H1': 3600,   // 1 hour
          'H4': 14400,  // 4 hours
          'D1': 86400,  // 1 day
        };

        // Latest actual candle time in the loaded data. We use this (not
        // the right edge of the visible range) as the end time for HH/LL
        // lines so they never bleed into the empty area past the last bar.
        // `rightOffset: 5` on the chart means the visible range extends
        // ~5 bars past the last candle, which was the previous source of
        // the "line pokes through the last candle and keeps going" bug.
        const lastCandleTime: number | null = candlesToUse.length > 0
          ? candlesToUse[candlesToUse.length - 1].time
          : null;
        
        if (lineType === 'BOS_CHOCH') {
          // BoS/CHoCH: line from level formation → break event
          // startTime = when the level was first formed (from HH/LL data)
          // endTime = the break event time
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
          // HH/LL: line starts at the level's formation event and stops at
          // the LAST ACTUAL CANDLE (not `Date.now()` and not the right
          // edge of the visible range). This matches the comment intent of
          // "stops at last candle" and prevents the line from bleeding into
          // the empty area past the last bar.
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
        // CSV timestamp is candle CLOSE time, so we need to subtract 1 period
        // Find which candle formed this HH/LL — O(1) Map lookup
        let actualStartTime = startTimeSeconds;
        const matchingCandle = candleTimeMap.get(startTimeSeconds);
        
        if (!matchingCandle) {
          // No exact match — binary search for nearest candle before event
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
        
        // Add to our linesToPrimitive array instead of creating a series!
        linesToPrimitive.push({
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

    // Helper: find when a price level was first formed in HH/LL data.
    // IMPORTANT: We look up the BoS/CHoCH's OWN price (the level that the line is
    // drawn at), NOT PreviousPrice. The BoS line is drawn at `bos.price`, so its
    // formation time must be when that exact level first appeared in HH/LL data.
    // - BoS/CHoCH Bullish at price X → the level is an HH (higher high) → search HH points
    // - BoS/CHoCH Bearish at price X → the level is an LL (lower low)  → search LL points
    // We keep the OLDEST (earliest) occurrence (first time that level was formed).
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
    const linesToDraw: Array<{
      price: number;
      timestamp: number;
      color: string;
      lineWidth: number;
      lineStyle: number;
      label: string;
      lineType?: 'HH' | 'LL' | 'BOS_CHOCH';
      levelFormationTime?: number;
    }> = [];

    // Add BoS lines to queue
    filteredBosLines.forEach((bos) => {
      const color = bos.direction === 'BULLISH' ? '#10b981' : '#ef4444';
      const formationTime = bos.price
        ? findLevelFormationTime(bos.price, bos.direction)
        : undefined;
      linesToDraw.push({
        price: bos.price,
        timestamp: bos.timestamp,
        color,
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        label: `BoS ${bos.price.toFixed(2)}`,
        lineType: 'BOS_CHOCH',
        levelFormationTime: formationTime,
      });
    });

    // Add CHoCH lines to queue
    filteredChochLines.forEach((choch) => {
      const color = choch.direction === 'BULLISH' ? '#10b981' : '#ef4444';
      const formationTime = choch.price
        ? findLevelFormationTime(choch.price, choch.direction)
        : undefined;
      linesToDraw.push({
        price: choch.price,
        timestamp: choch.timestamp,
        color,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        label: `CHoCH ${choch.price.toFixed(2)}`,
        lineType: 'BOS_CHOCH',
        levelFormationTime: formationTime,
      });
    });

    // Dedup (Opsi A, TIME-SCOPED)
    const PRICE_TOLERANCE = 0.05;
    const DEDUP_TIME_WINDOW_SEC = 7 * 24 * 3600; // 7 hari
    const toSec = (t: number) => (t > 1e10 ? Math.floor(t / 1000) : t);
    const bosChochByBucket = new Map<number, number[]>();
    [...filteredBosLines, ...filteredChochLines].forEach((evt) => {
      if (evt.price == null || evt.timestamp == null) return;
      const key = Math.round(evt.price / PRICE_TOLERANCE);
      const arr = bosChochByBucket.get(key);
      if (arr) arr.push(toSec(evt.timestamp));
      else bosChochByBucket.set(key, [toSec(evt.timestamp)]);
    });
    const priceMatchesBosChoch = (price: number, levelTime: number): boolean => {
      if (bosChochByBucket.size === 0) return false;
      const key = Math.round(price / PRICE_TOLERANCE);
      const lt = toSec(levelTime);
      for (const k of [key - 1, key, key + 1]) {
        const arr = bosChochByBucket.get(k);
        if (!arr) continue;
        for (const ts of arr) {
          if (ts >= lt && ts - lt <= DEDUP_TIME_WINDOW_SEC) return true;
        }
      }
      return false;
    };

    const dedupKeepOldest = <T extends { price: number; timestamp: number }>(points: T[]): T[] => {
      const byPrice = new Map<number, T>();
      for (const p of points) {
        const key = Math.round(p.price / PRICE_TOLERANCE);
        const existing = byPrice.get(key);
        if (!existing || p.timestamp < existing.timestamp) byPrice.set(key, p);
      }
      return [...byPrice.values()];
    };
    const dedupedHhPoints = dedupKeepOldest(filteredHhPoints);
    const dedupedLlPoints = dedupKeepOldest(filteredLlPoints);

    // Add HH lines (skip those overlapping a BoS/CHoCH level)
    dedupedHhPoints.forEach((hh) => {
      if (priceMatchesBosChoch(hh.price, hh.timestamp)) return;
      const isH1 = hh.timeframe === 'H1';
      linesToDraw.push({
        price: hh.price,
        timestamp: hh.timestamp,
        color: isH1 ? '#1e40af' : '#60a5fa',
        lineWidth: isH1 ? 2 : 1.5,
        lineStyle: isH1 ? LineStyle.Dashed : LineStyle.Dotted,
        label: `HH [${hh.timeframe}] ${hh.price.toFixed(2)}`,
        lineType: 'HH',
      });
    });

    // Add LL lines (skip those overlapping a BoS/CHoCH level)
    dedupedLlPoints.forEach((ll) => {
      if (priceMatchesBosChoch(ll.price, ll.timestamp)) return;
      const isH1 = ll.timeframe === 'H1';
      linesToDraw.push({
        price: ll.price,
        timestamp: ll.timestamp,
        color: isH1 ? '#c2410c' : '#fb923c',
        lineWidth: isH1 ? 2 : 1.5,
        lineStyle: isH1 ? LineStyle.Dashed : LineStyle.Dotted,
        label: `LL [${ll.timeframe}] ${ll.price.toFixed(2)}`,
        lineType: 'LL',
      });
    });

    const totalLines = linesToDraw.length;
    let bosAdded = 0;
    let chochAdded = 0;
    let hhAdded = 0;
    let llAdded = 0;

    // Show drawing progress popup
    setDrawLineProgress({ visible: true, percent: 0, current: 0, total: totalLines });

    // Draw in chunks of 20 lines to keep progress animation smooth
    const chunkSize = 20;
    for (let startIdx = 0; startIdx < totalLines; startIdx += chunkSize) {
      const endIdx = Math.min(startIdx + chunkSize, totalLines);
      
      for (let j = startIdx; j < endIdx; j++) {
        const line = linesToDraw[j];
        const success = createHorizontalLine(
          line.price,
          line.timestamp,
          line.color,
          line.lineWidth,
          line.lineStyle,
          line.label,
          line.lineType,
          line.levelFormationTime,
        );
        if (success) {
          if (line.lineType === 'BOS_CHOCH') {
            if (line.label.startsWith('BoS')) bosAdded++;
            else chochAdded++;
          } else if (line.lineType === 'HH') {
            hhAdded++;
          } else if (line.lineType === 'LL') {
            llAdded++;
          }
        }
      }

      // Update progress state
      const percent = Math.round((endIdx / totalLines) * 100);
      setDrawLineProgress({ visible: true, percent, current: endIdx, total: totalLines });

      // Yield control (10ms)
      await new Promise((resolve) => setTimeout(resolve, 10));
    }

    // Hide progress popup
    setDrawLineProgress({ visible: false, percent: 100, current: totalLines, total: totalLines });

    // Set lines to primitive at the end
    structurePrimitiveRef.current?.setLines(linesToPrimitive);

    console.log('\n✅ ===== OVERLAY COMPLETE =====');
    console.log('Total structure lines parsed:', totalLines);
    
    overlayGuardRef.current = false;
  };

  // Sync overlays when data/state changes
  useEffect(() => {
    if (showStructure && structureLines) {
      console.log('🔄 useEffect: Triggering structure overlay');
      overlayMarketStructure(chartCandles);
    } else {
      // Clean up overlay lines
      structureSeriesRef.current.forEach(series => {
        try { chartRef.current?.removeSeries(series); } catch (e) {}
      });
      structureSeriesRef.current = [];
      
      // Clean up overlay HTML labels
      const overlayEl = document.getElementById('structure-labels-overlay');
      if (overlayEl) {
        overlayEl.innerHTML = '';
      }
    }
  }, [chartCandles, structureLines, activeTimeframe, showStructure]);

  useEffect(() => {
    if (showSessions && sessionZonesData && sessionZonesPrimitiveRef.current) {
      const boxes: SessionZoneBox[] = sessionZonesData.zones
        .filter(z => z.end_time > z.start_time)
        .map(zone => ({
          start: zone.start_time,
          end: zone.end_time,
          session: zone.session,
          open: zone.status === "OPEN",
        }));
      sessionZonesPrimitiveRef.current.setBoxes(boxes);
    } else if (sessionZonesPrimitiveRef.current) {
      sessionZonesPrimitiveRef.current.setBoxes([]);
    }
  }, [sessionZonesData, showSessions, chartCandles]);

  useEffect(() => {
    if (showTrades) {
      overlayTradeEntries();
    }
    return () => {
      if (tradesPrimitiveRef.current && candlestickSeriesRef.current) {
        try { candlestickSeriesRef.current.detachPrimitive(tradesPrimitiveRef.current); } catch (e) {}
      }
      const tradesEl = document.getElementById('trades-labels-overlay');
      if (tradesEl) tradesEl.innerHTML = '';
    };
  }, [showTrades, backtestTradesData, chartCandles, activeTimeframe]);

  useEffect(() => {
    if (ema200SeriesRef.current) {
      ema200SeriesRef.current.applyOptions({ visible: showEMA200 });
    }
  }, [showEMA200]);

  // Progress indicator effect
  useEffect(() => {
    if (loadProgress.visible && latestProgressRef.current.percent > 0) {
      setLoadProgress(prev => ({
        ...prev,
        percent: latestProgressRef.current.percent,
        step: latestProgressRef.current.step,
        total: latestProgressRef.current.total,
      }));
    }
  }, [loadProgress.visible, latestProgressRef.current.percent]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (scrollLabelDebounceRef.current) {
        clearTimeout(scrollLabelDebounceRef.current);
      }
    };
  }, []);

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
        id="tsparticles-rongsokan"
        init={particlesInit}
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

      <div
        className="relative z-10"
        style={{
          width: "100%",
          paddingLeft: "240px",
          minHeight: "calc(149vh - 0px)"
        }}
      >
        <div className="w-full px-12 py-8">
          {/* Page Header */}
          <div className="mb-8">
            <h1 className="text-[36px] font-bold mb-3 bg-gradient-to-r from-[var(--neon-blue)] to-[var(--neon-cyan)] bg-clip-text text-transparent">
              🔋 Rongsokan
            </h1>
            <p className="text-[var(--text-tertiary)] text-base">
              Market structure, sessions, and backtest trade overlay
            </p>
          </div>

          {/* Stats Grid */}
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
                title={<span className="text-xl font-semibold">🔋 XAUUSD {activeTimeframe} Chart</span>}
                activeTimeframe={activeTimeframe}
                onTimeframeChange={handleTimeframeChange}
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
                onRefresh={() => refetchChartData()}
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
              style={{ width: "100%", height: "700px" }}
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

          {/* Footer */}
          <div>
            <MT5Footer />
          </div>
        </div>
      </div>

      {/* Progress popup for Load Full History */}
      {loadProgress.visible && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-purple-500/30 rounded-xl p-6 shadow-2xl w-96">
            <div className="text-center mb-4">
              <div className="text-purple-300 font-semibold text-sm mb-2">
                📅 Loading Full History
              </div>
              <div className="text-3xl font-bold text-white mb-1">
                {loadProgress.percent}%
              </div>
              <div className="text-xs text-gray-400">{loadProgress.step}</div>
              <div className="text-[10px] text-gray-500 mt-1">
                {loadProgress.total.toLocaleString()} total rows
              </div>
            </div>
            <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-500 to-blue-500 rounded-full"
                style={{ width: `${loadProgress.percent}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Progress popup for Drawing Lines */}
      {drawLineProgress.visible && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-cyan-500/30 rounded-xl p-6 shadow-2xl w-96">
            <div className="text-center mb-4">
              <div className="text-cyan-300 font-semibold text-sm mb-2">
                ✍️ Drawing Structure Lines
              </div>
              <div className="text-3xl font-bold text-white mb-1">
                {drawLineProgress.percent}%
              </div>
              <div className="text-xs text-gray-400">
                Drawing line {drawLineProgress.current} of {drawLineProgress.total}
              </div>
            </div>
            <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full"
                style={{ width: `${drawLineProgress.percent}%` }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}