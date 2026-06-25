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
import { useMarketStructureLines, useSessionZones, useBacktestTrades, type BacktestTrade } from "@/api/mt5_agents";
import {
  SessionZonesPrimitive,
  type SessionZoneBox,
} from "@/components/valuecell/charts/session-zones-primitive";
import {
  TradesOverlayPrimitive,
  type TradeOverlayEntry,
} from "@/components/valuecell/charts/trades-overlay-primitive";
import MT5Sidebar from "./components/MT5Sidebar";
import MT5Footer from "./components/MT5Footer";

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
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema200SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const structureSeriesRef = useRef<ISeriesApi<"Line">[]>([]); // Line series for structure
  const sessionZonesPrimitiveRef = useRef<SessionZonesPrimitive | null>(null);
  const tradeSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const tradesPrimitiveRef = useRef<TradesOverlayPrimitive | null>(null);
  const overlayTradeGuardRef = useRef(false);
  
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
            rightOffset: 5,
            barSpacing: 8,
            minBarSpacing: 4,
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
        
        // Re-render structure labels with 50ms debounce when user pans/zooms
        // Prevents DOM churn at 60fps (innerHTML='' + createElement per label per frame)
        chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
          if (scrollLabelDebounceRef.current) clearTimeout(scrollLabelDebounceRef.current);
          scrollLabelDebounceRef.current = setTimeout(
            () => renderStructureLabelsOverlay(structureLabelsRef.current),
            50
          );
        });

        console.log('✅ Chart initialized successfully');
        console.log('chartRef.current:', !!chartRef.current);
        console.log('candlestickSeriesRef.current:', !!candlestickSeriesRef.current);
        
        loadChartData(false);
      } catch (error) {
        console.error('❌ Error creating chart:', error);
      }
    } else {
      console.log('⏭️ Skipping chart init: already initialized or container not ready');
    }

    const handleResize = () => {
      if (chartRef.current && chartContainerRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    loadTradeHistory();
    const interval = setInterval(loadTradeHistory, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Auto-refresh chart data every 30 seconds (increased from 5s for performance)
    // ONLY refresh in recent mode AND only if user hasn't jumped to specific date
    // Disable auto-refresh when exploring historical data to prevent unwanted scrolling
    const chartInterval = setInterval(() => {
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
        } else {
          console.log('⏸️ Skipping auto-refresh (user is viewing historical data)');
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
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      
      // Determine mode and from_date
      const mode = loadMode || dataMode;
      const fromDate = mode === 'full' ? '2020-01-01' : chartFromDate;
      const timeframe = timeframeOverride || activeTimeframe;

      const chartUrl = `${apiUrl}/trading/chart/backtest-data?symbol=XAUUSD&timeframe=${timeframe}&from_date=${fromDate}&mode=${mode}`;
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
          // Debug: Log first candle to check timestamp
          if (data.candles.length > 0) {
            const firstCandle = data.candles[0];
            const lastCandle = data.candles[data.candles.length - 1];
            
            console.log('📊 Data range:', {
              first: new Date(firstCandle.time * 1000).toISOString(),
              last: new Date(lastCandle.time * 1000).toISOString(),
              total: data.candles.length,
            });
            console.log('📊 Data range:', {
              first: new Date(firstCandle.time * 1000).toISOString(),
              last: new Date(lastCandle.time * 1000).toISOString(),
              total: data.candles.length,
            });
          }
          
          const processedCandles = processCandles(data.candles);
          
          console.log('✅ Processed candles:', processedCandles.length);
          
          // CRITICAL FIX: Preserve viewport position when updating data
          // Save current visible range before setData
          const timeScale = chartRef.current?.timeScale();
          const currentVisibleRange = timeScale?.getVisibleRange();
          
          updateLoadedCandles(processedCandles, data.candles_count || processedCandles.length);
          if (mode === 'full' && processedCandles.length > 0) {
            cacheFullHistory(timeframe, processedCandles);
          }
          
          // Restore viewport position after setData (prevents auto-scroll)
          if (currentVisibleRange && timeScale && !forceRefresh) {
            setTimeout(() => {
              timeScale.setVisibleRange(currentVisibleRange);
              console.log('🔒 Viewport position preserved');
            }, 0);
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
            overlayMarketStructure(processedCandles, forceRefresh);
          }
          
          return; // Exit if API data loaded successfully
        }
      }
    } catch (error) {
      console.error("API error:", error);
      console.warn("⚠️ Unable to load chart data");
      setDataMode('recent'); // Reset to recent on error
    }
  };
  
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
        if (showStructure && structureLines) {
          requestAnimationFrame(() => overlayMarketStructure(processedCandles, true));
        }
        fullDataDisplayedRef.current[cacheKey] = true;
      }
    } catch (error) {
      console.error('Stream error:', error);
      setDataMode('recent');
    } finally {
      latestProgressRef.current = { percent: 100, step: '', total: 0 };
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
              requestAnimationFrame(() => overlayMarketStructure(cachedData.candles, true));
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
            requestAnimationFrame(() => overlayMarketStructure(processedCandles, true));
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
  const handleYearChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newYear = e.target.value;
    setSelectedYear(newYear);
    setSelectedMonth("01"); // Reset to January when year changes
    jumpToDate(newYear, "01");
  };
  
  // Handle month change - jump to selected month of current year
  const handleMonthChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newMonth = e.target.value;
    setSelectedMonth(newMonth);
    jumpToDate(selectedYear, newMonth);
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
    if (overlayTradeGuardRef.current) return;
    overlayTradeGuardRef.current = true;
    tradeSeriesRef.current.forEach(series => {
      try { chartRef.current?.removeSeries(series); } catch (e) {}
    });
    tradeSeriesRef.current = [];
    if (tradesPrimitiveRef.current && candlestickSeriesRef.current) {
      try { candlestickSeriesRef.current.detachPrimitive(tradesPrimitiveRef.current); } catch (e) {}
    }
    tradesPrimitiveRef.current = null;
    const tradesEl = document.getElementById('trades-labels-overlay');
    if (tradesEl) tradesEl.innerHTML = '';

    if (!showTrades || !backtestTradesData || !chartRef.current || !candlestickSeriesRef.current) {
      overlayTradeGuardRef.current = false;
      return;
    }

    const trades = backtestTradesData.trades ?? [];
    if (trades.length === 0) {
      overlayTradeGuardRef.current = false;
      return;
    }

    const lastCandle = chartCandles.length > 0 ? chartCandles[chartCandles.length - 1]?.time : null;

    const createSeriesForTrade = (trade: BacktestTrade) => {
      const startTs = trade.entry_time_ts;
      const endTs = trade.exit_time_ts ?? lastCandle;
      if (!startTs || !endTs) return;
      const startTime = startTs as any;
      const endTime = endTs as any;

      const entrySeries = chartRef.current!.addSeries(LineSeries, {
        color: '#3b82f6', lineWidth: 2, lineStyle: LineStyle.Dashed,
        priceLineVisible: false, lastValueVisible: false,
      });
      entrySeries.setData([{ time: startTime, value: trade.entry_price }, { time: endTime, value: trade.entry_price }]);
      tradeSeriesRef.current.push(entrySeries);

      if (trade.tp !== null) {
        const tpSeries = chartRef.current!.addSeries(LineSeries, {
          color: '#22c55e', lineWidth: 1, lineStyle: LineStyle.Dashed,
          priceLineVisible: false, lastValueVisible: false,
        });
        tpSeries.setData([{ time: startTime, value: trade.tp }, { time: endTime, value: trade.tp }]);
        tradeSeriesRef.current.push(tpSeries);
      }

      if (trade.sl !== null) {
        const slSeries = chartRef.current!.addSeries(LineSeries, {
          color: '#ef4444', lineWidth: 1, lineStyle: LineStyle.Dashed,
          priceLineVisible: false, lastValueVisible: false,
        });
        slSeries.setData([{ time: startTime, value: trade.sl }, { time: endTime, value: trade.sl }]);
        tradeSeriesRef.current.push(slSeries);
      }
    };

    const finishOverlay = () => {
      const primitive = tradesPrimitiveRef.current ?? new TradesOverlayPrimitive();
      candlestickSeriesRef.current!.attachPrimitive(primitive);
      const entries: TradeOverlayEntry[] = trades.map(t => ({
        type: t.type, entry_price: t.entry_price, sl: t.sl, tp: t.tp,
        profit: t.profit, entry_time_ts: t.entry_time_ts, exit_time_ts: t.exit_time_ts,
      }));
      primitive.setTrades(entries);
      primitive.setLastCandleTime(lastCandle as number | null);
      tradesPrimitiveRef.current = primitive;
      renderTradesLabels(trades);
      overlayTradeGuardRef.current = false;
    };

    const BATCH = 30;
    let idx = 0;

    const nextBatch = () => {
      if (!chartRef.current || !showTrades) {
        tradeSeriesRef.current.forEach(s => { try { chartRef.current?.removeSeries(s); } catch (e) {} });
        tradeSeriesRef.current = [];
        overlayTradeGuardRef.current = false;
        return;
      }
      const end = Math.min(idx + BATCH, trades.length);
      for (; idx < end; idx++) createSeriesForTrade(trades[idx]);
      if (idx < trades.length) requestAnimationFrame(nextBatch);
      else finishOverlay();
    };

    requestAnimationFrame(nextBatch);
  };

  const overlayMarketStructure = (candles?: Array<{time: number, open: number, high: number, low: number, close: number}>, forceRefresh = false) => {
    if (!chartRef.current || !showStructure || !structureLines) return;
    
    // Prevent concurrent executions
    if (overlayGuardRef.current) {
      console.log('⏸️ overlayMarketStructure already running, skipping');
      return;
    }
    overlayGuardRef.current = true;

    // Use provided candles or fall back to state (for effect-triggered calls)
    const candlesToUse = candles ?? chartCandles;

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

    // Clear existing structure series
    structureSeriesRef.current.forEach(series => {
      try {
        chartRef.current?.removeSeries(series);
      } catch (e) {
        console.debug('Could not remove series:', e);
      }
    });
    structureSeriesRef.current = [];
    
    // Get actual visible candle range from time scale
    const timeScale = chartRef.current!.timeScale();
    const visibleLogicalRange = timeScale.getVisibleLogicalRange();
    
    console.log('📅 Chart visible logical range:', visibleLogicalRange);
    
    // Get first visible candle timestamp
    // We need to coordinate with the actual candle data loaded
    let firstVisibleCandleTime: number | null = null;
    try {
      if (visibleLogicalRange) {
        // Convert logical index to time coordinate
        const leftIndex = Math.floor(visibleLogicalRange.from);
        const timeAtIndex = timeScale.coordinateToTime(leftIndex);
        if (timeAtIndex) {
          firstVisibleCandleTime = typeof timeAtIndex === 'number' ? timeAtIndex : null;
          console.log('📅 First visible candle time:', firstVisibleCandleTime, new Date((firstVisibleCandleTime || 0) * 1000).toISOString());
        }
      }
    } catch (e) {
      console.warn('Could not get first visible candle time:', e);
    }

    // Helper function to create horizontal line from timestamp
    // lineType:
    //   'HH'  - Higher High: starts at formation, stops when candle.high > price
    //   'LL'  - Lower Low:   starts at formation, stops when candle.low < price
    //   'BOS_CHOCH' - BoS/CHoCH: starts at level formation time, ends at break event time
    //                  (line goes from LEFT → the break candle, not beyond)
    // Collect label info here; will be rendered as HTML overlay on candlestick series
    // (setMarkers does not exist in lightweight-charts v5)
    const structureLabels: Array<{
      time: number;
      price: number;
      color: string;
      text: string;
      isResistance: boolean;
    }> = [];

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
        
        const lineOptions = {
          color,
          lineWidth,
          lineStyle,
          priceLineVisible: false,
          lastValueVisible: false, // Remove right-side price badges to prevent overlap with candles
          // No title — label is placed in the middle of the line via marker instead
        };
        
        // Create line data from event time to end
        const lineData: Array<{ time: number; value: number }> = [
          { time: actualStartTime, value: price }, // Start point
        ];
        lineData.push({ time: endTimeSeconds, value: price }); // End point

        const lineSeries = chartRef.current!.addSeries(LineSeries, lineOptions);
        lineSeries.setData(lineData);

        // Collect label info for HTML overlay in the middle of the line
        // Use binary search to find nearest candle to midpoint — avoids O(n) scan
        if (label && candleTimeArray.length > 0) {
          const rawMidTime = Math.floor((actualStartTime + endTimeSeconds) / 2);
          const midIdx = lowerBound(rawMidTime);
          // Clamp to [actualStartTime, endTimeSeconds] range
          const candidates: number[] = [];
          if (midIdx > 0) candidates.push(candleTimeArray[midIdx - 1]);
          if (midIdx < candleTimeArray.length) candidates.push(candleTimeArray[midIdx]);
          if (midIdx + 1 < candleTimeArray.length) candidates.push(candleTimeArray[midIdx + 1]);
          let nearestCandleTime = actualStartTime;
          let nearestDist = Infinity;
          for (const t of candidates) {
            if (t < actualStartTime || t > endTimeSeconds) continue;
            const dist = Math.abs(t - rawMidTime);
            if (dist < nearestDist) {
              nearestDist = dist;
              nearestCandleTime = t;
            }
          }
          structureLabels.push({
            time: nearestCandleTime,
            price,
            color,
            text: label,
            isResistance: lineType !== 'LL',
          });
        }

        structureSeriesRef.current.push(lineSeries);
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
    const findLevelFormationTime = (
      levelPrice: number,
      direction: string, // 'BULLISH' or 'BEARISH'
    ): number | undefined => {
      // Bullish BoS/CHoCH forms an HH level, so look in HH points
      // Bearish BoS/CHoCH forms an LL level, so look in LL points
      const isBullish = direction === 'BULLISH';
      const levelPoints = isBullish
        ? (structureLines.hh_points ?? [])
        : (structureLines.ll_points ?? []);

      // Find the matching price level (allow small tolerance for floating point)
      const tolerance = 0.05;
      let matchTime: number | undefined;

      for (const point of levelPoints) {
        if (Math.abs(point.price - levelPrice) < tolerance) {
          const pointTimeSec = point.timestamp > 10000000000
            ? Math.floor(point.timestamp / 1000)
            : point.timestamp;
          // Keep the oldest (earliest) formation time
          if (matchTime === undefined || pointTimeSec < matchTime) {
            matchTime = pointTimeSec;
          }
        }
      }

      if (matchTime !== undefined) {
        console.log(`  🔍 Level ${levelPrice.toFixed(2)} formed at ${matchTime} (${new Date(matchTime * 1000).toISOString()}) [searched ${isBullish ? 'HH' : 'LL'} points]`);
      } else {
        console.log(`  ⚠️ Could not find formation time for level ${levelPrice.toFixed(2)} in ${isBullish ? 'HH' : 'LL'} points`);
      }

      return matchTime;
    };

    // Add BoS lines
    let bosAdded = 0;
    structureLines.bos_lines?.forEach((bos, index) => {
      console.log(`Adding BoS #${index + 1}:`, { price: bos.price, time: bos.time, timestamp: bos.timestamp, prevPrice: bos.previous_price });
      const color = bos.direction === 'BULLISH' ? '#10b981' : '#ef4444';
      // timestamp is already in milliseconds from backend
      const eventTime = bos.timestamp;
      // Find when this BoS's OWN level was first formed (line is drawn at bos.price,
      // so its start must be when bos.price first appeared as HH/LL)
      const formationTime = bos.price
        ? findLevelFormationTime(bos.price, bos.direction)
        : undefined;
      if (createHorizontalLine(
        bos.price,
        eventTime,
        color,
        2,
        LineStyle.Solid,
        `BoS ${bos.price.toFixed(2)}`,
        'BOS_CHOCH',
        formationTime
      )) {
        bosAdded++;
        console.log(`✅ BoS #${index + 1} added: formation→${formationTime ?? '?'} to break→${eventTime}`);
      }
    });

    // Add CHoCH lines
    let chochAdded = 0;
    structureLines.choch_lines?.forEach((choch, index) => {
      console.log(`Adding CHoCH #${index + 1}:`, { price: choch.price, time: choch.time, timestamp: choch.timestamp, prevPrice: choch.previous_price });
      const eventTime = choch.timestamp;
      const formationTime = choch.price
        ? findLevelFormationTime(choch.price, choch.direction)
        : undefined;
      const color = choch.direction === 'BULLISH' ? '#10b981' : '#ef4444';
      if (createHorizontalLine(
        choch.price,
        eventTime,
        color,
        2,
        LineStyle.Dashed,
        `CHoCH ${choch.price.toFixed(2)}`,
        'BOS_CHOCH',
        formationTime
      )) {
        chochAdded++;
        console.log(`✅ CHoCH #${index + 1} added: formation→${formationTime ?? '?'} to break→${eventTime}`);
      }
    });

    // Add HH lines (with H1 vs M15 differentiation)
    // Deduplication (Opsi A): hide HH/LL if their price matches any BoS/CHoCH price,
    // because the BoS/CHoCH line already represents that level (more recent event).
    const bosChochPrices = new Set<number>();
    const PRICE_TOLERANCE = 0.05;
    const allBos = structureLines.bos_lines ?? [];
    const allChoch = structureLines.choch_lines ?? [];
    [...allBos, ...allChoch].forEach((evt) => {
      if (evt.price != null) {
        bosChochPrices.add(Math.round(evt.price / PRICE_TOLERANCE));
      }
    });
    const priceMatchesBosChoch = (price: number): boolean => {
      if (bosChochPrices.size === 0) return false;
      const key = Math.round(price / PRICE_TOLERANCE);
      // Check exact bucket + neighbors to handle floating point near boundaries
      return bosChochPrices.has(key) ||
             bosChochPrices.has(key - 1) ||
             bosChochPrices.has(key + 1);
    };
    let hhSkippedByDup = 0;

    let hhAdded = 0;
    console.log('\n🔵 Processing HH points...');
    if (!structureLines.hh_points || structureLines.hh_points.length === 0) {
      console.warn('⚠️ No HH points available!');
    } else {
      structureLines.hh_points.forEach((hh, index) => {
        if (priceMatchesBosChoch(hh.price)) {
          hhSkippedByDup++;
          console.log(`  ⏭️ HH #${index + 1} (${hh.price}) skipped: matches a BoS/CHoCH price (dedup)`);
          return;
        }
        const isH1 = hh.timeframe === 'H1';
        const color = isH1 ? '#1e40af' : '#60a5fa'; // Dark blue for H1, Light blue for M15
        const lineWidth = isH1 ? 2 : 1.5;
        const lineStyle = isH1 ? LineStyle.Dashed : LineStyle.Dotted;
        const label = `HH [${hh.timeframe}] ${hh.price.toFixed(2)}`;
        
        console.log(`Adding HH #${index + 1}:`, { 
          price: hh.price, 
          time: hh.time, 
          timestamp: hh.timestamp,
          timeframe: hh.timeframe,
          color,
          lineWidth,
          lineStyle: isH1 ? 'dashed' : 'dotted'
        });
        
        const eventTime = hh.timestamp;
        if (createHorizontalLine(
          hh.price,
          eventTime,
          color,
          lineWidth,
          lineStyle,
          label,
          'HH' // HH line stops when high > price
        )) {
          hhAdded++;
          console.log(`✅ HH #${index + 1} [${hh.timeframe}] added at ${eventTime}ms (${hh.time})`);
        }
      });
    }

    // Add LL lines (with H1 vs M15 differentiation)
    let llSkippedByDup = 0;
    let llAdded = 0;
    console.log('\n🟠 Processing LL points...');
    if (!structureLines.ll_points || structureLines.ll_points.length === 0) {
      console.warn('⚠️ No LL points available!');
    } else {
      structureLines.ll_points.forEach((ll, index) => {
        if (priceMatchesBosChoch(ll.price)) {
          llSkippedByDup++;
          console.log(`  ⏭️ LL #${index + 1} (${ll.price}) skipped: matches a BoS/CHoCH price (dedup)`);
          return;
        }
        const isH1 = ll.timeframe === 'H1';
        const color = isH1 ? '#c2410c' : '#fb923c'; // Dark orange for H1, Light orange for M15
        const lineWidth = isH1 ? 2 : 1.5;
        const lineStyle = isH1 ? LineStyle.Dashed : LineStyle.Dotted;
        const label = `LL [${ll.timeframe}] ${ll.price.toFixed(2)}`;
        
        console.log(`Adding LL #${index + 1}:`, { 
          price: ll.price, 
          time: ll.time, 
          timestamp: ll.timestamp,
          timeframe: ll.timeframe,
          color,
          lineWidth,
          lineStyle: isH1 ? 'dashed' : 'dotted'
        });
        
        const eventTime = ll.timestamp;
        if (createHorizontalLine(
          ll.price,
          eventTime,
          color,
          lineWidth,
          lineStyle,
          label,
          'LL' // LL line stops when low < price
        )) {
          llAdded++;
          console.log(`✅ LL #${index + 1} [${ll.timeframe}] added at ${eventTime}ms (${ll.time})`);
        }
      });
    }

    // Render all collected labels as HTML overlay on the chart container
    renderStructureLabelsOverlay(structureLabels);

    console.log('\n✅ ===== OVERLAY COMPLETE =====');
    console.log('Lines added:', {
      bos: bosAdded,
      choch: chochAdded,
      hh: hhAdded,
      ll: llAdded,
      total: bosAdded + chochAdded + hhAdded + llAdded,
      skippedByDup: { hh: hhSkippedByDup, ll: llSkippedByDup },
    });
    console.log('Total line series:', structureSeriesRef.current.length);
    
    overlayGuardRef.current = false;
  };

  // Apply structure overlay when data changes or toggle state changes
  // Note: activeTimeframe changes are handled by loadChartData -> overlayMarketStructure(forceRefresh)
  useEffect(() => {
    // Handle toggle OFF state
    if (!showStructure) {
      structureSeriesRef.current.forEach(series => {
        try { chartRef.current?.removeSeries(series); } catch (e) {}
      });
      structureSeriesRef.current = [];
      structureLinesVersionRef.current = '';
      return;
    }

    // Only draw when structure data actually changed (hash comparison prevents
    // redundant redraws from 30s refetch cycles with identical data)
    if (showStructure && structureLines && chartRef.current && candlestickSeriesRef.current && chartCandles.length > 0) {
      const hash = `${structureLines.total_points}|${structureLines.bos_lines?.length}|${structureLines.choch_lines?.length}|${structureLines.hh_points?.length}|${structureLines.ll_points?.length}`;
      if (hash !== structureLinesVersionRef.current) {
        structureLinesVersionRef.current = hash;
        overlayMarketStructure(chartCandles);
      }
    }
  }, [showStructure, structureLines]);

  // Update session-zone shadows when data or toggle changes
  useEffect(() => {
    const primitive = sessionZonesPrimitiveRef.current;
    if (!primitive) {
      console.warn('⚠️ Session zones primitive not initialized');
      return;
    }

    console.log('🕒 [SESSION DEBUG] Updating session zones:', {
      showSessions,
      totalZones: sessionZonesData?.total_zones,
      zonesReceived: sessionZonesData?.zones?.length,
    });

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
    
    console.log('🕒 [SESSION DEBUG] Boxes prepared:', {
      totalBoxes: boxes.length,
      firstBox: boxes[0],
      lastBox: boxes[boxes.length - 1],
    });
    
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

  // Toggle trade entries overlay
  useEffect(() => {
    overlayTradeEntries();
  }, [showTrades, backtestTradesData]);

  // Sync progress ref → state at 60fps during loading (avoids React batching swallows)
  useEffect(() => {
    if (!loadProgress.visible) return;
    let rafId: number;
    const sync = () => {
      setLoadProgress(prev => {
        const l = latestProgressRef.current;
        return l.percent !== prev.percent || l.step !== prev.step
          ? { ...prev, ...l }
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
      console.log('Fetching trades from:', `${apiUrl}/trading/trades/history`);
      
      const response = await fetch(
        `${apiUrl}/trading/trades/history?days=30`
      );
      
      console.log('Trades API response status:', response.status, response.ok);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Trades API data received:', data.trades?.length, 'trades');
        
        if (data.trades) {
          setTrades(data.trades);
          setStats({
            total_trades: data.total_trades ?? 0,
            win_rate: data.win_rate ?? 0,
            total_pnl: data.total_pnl ?? 0,
            open_positions: data.open_positions ?? 0,
          });
          console.log('✅ Real trades data loaded from MT5');
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
        id="tsparticles"
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

      {/* Sidebar */}
      <div>
        <MT5Sidebar />
      </div>

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
          <div className="flex justify-between items-center mb-5">
            <span className="text-xl font-semibold">📈 XAUUSD {activeTimeframe} Chart</span>
            <div className="flex gap-2 items-center flex-wrap">
              {/* Market Structure Toggle */}
              <button
                onClick={() => setShowStructure(!showStructure)}
                className={`px-3 py-2 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-lg text-xs transition-all hover:bg-[var(--bg-elevated)] flex items-center gap-2 ${
                  showStructure
                    ? "!border-[var(--neon-purple)] !text-[var(--neon-purple)] shadow-[0_0_15px_rgba(168,85,247,0.3)]"
                    : ""
                }`}
                title="Toggle Market Structure Overlay"
              >
                <span>🏗️</span>
                <span>Structure</span>
                {structureLines && (
                  <span className="text-xs opacity-70">
                    ({structureLines.total_points})
                  </span>
                )}
              </button>

              {/* Session Zones Toggle */}
              <button
                onClick={() => setShowSessions(!showSessions)}
                className={`px-3 py-2 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-lg text-xs transition-all hover:bg-[var(--bg-elevated)] flex items-center gap-2 ${
                  showSessions
                    ? "!border-[var(--neon-cyan)] !text-[var(--neon-cyan)] shadow-[0_0_15px_rgba(34,211,238,0.3)]"
                    : ""
                }`}
                title="Toggle Session Zone Shadows"
              >
                <span>🕒</span>
                <span>Sessions</span>
                {sessionZonesData && (
                  <span className="text-xs opacity-70">
                    ({sessionZonesData.total_zones})
                  </span>
                )}
              </button>
              
              {/* EMA 200 Toggle */}
              <button
                onClick={() => setShowEMA200(!showEMA200)}
                className={`px-3 py-2 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-lg text-xs transition-all hover:bg-[var(--bg-elevated)] flex items-center gap-2 ${
                  showEMA200
                    ? "!border-[#f59e0b] !text-[#f59e0b] shadow-[0_0_15px_rgba(245,158,11,0.3)]"
                    : ""
                }`}
                title="Toggle EMA 200 Line"
              >
                <span>📈</span>
                <span>EMA 200</span>
              </button>

              {/* Trades Entry/SL/TP Toggle */}
              <button
                onClick={() => setShowTrades(!showTrades)}
                className={`px-3 py-2 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-lg text-xs transition-all hover:bg-[var(--bg-elevated)] flex items-center gap-2 ${
                  showTrades
                    ? "!border-[#3b82f6] !text-[#3b82f6] shadow-[0_0_15px_rgba(59,130,246,0.3)]"
                    : ""
                }`}
                title="Toggle Trade Entry/SL/TP Overlay"
              >
                <span>📊</span>
                <span>Trades</span>
                {backtestTradesData && (
                  <span className="text-xs opacity-70">
                    ({backtestTradesData.total_trades})
                  </span>
                )}
              </button>
              
              {/* Load Full History Button - show whenever full history not yet cached */}
              {!fullHistoryLoadedRef.current[activeTimeframe] && dataMode !== 'loading' && !loadProgress.visible && (
                <button
                  onClick={loadFullHistory}
                  disabled={isJumping}
                  className="px-3 py-2 bg-gradient-to-r from-purple-600/20 to-blue-600/20 border border-purple-500/30 rounded-lg text-xs transition-all hover:from-purple-600/30 hover:to-blue-600/30 hover:border-purple-400/50 flex items-center gap-2 text-purple-300 hover:text-purple-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Load full historical data from 2020 and cache for instant navigation"
                >
                  <span>📅</span>
                  <span>Load Full History</span>
                  <span className="text-[10px] opacity-70">(2020-2026 • Cache for instant jumps)</span>
                </button>
              )}
              
              {/* Data Mode Indicator */}
              {dataMode === 'loading' && (
                <div className="px-3 py-2 bg-blue-600/10 border border-blue-500/30 rounded-lg text-xs flex items-center gap-2 text-blue-300 animate-pulse">
                  <span className="animate-spin">⏳</span>
                  <span>Loading full history...</span>
                </div>
              )}
              
              {dataMode === 'full' && fullHistoryLoadedRef.current[activeTimeframe] && (
                <div className="px-3 py-2 bg-green-600/10 border border-green-500/30 rounded-lg text-xs flex items-center gap-2 text-green-300">
                  <span>✅</span>
                  <span>Full History Cached</span>
                  <span className="text-[10px] opacity-70">({candlesCount.toLocaleString()} candles • Instant jumps enabled)</span>
                </div>
              )}
              
              {dataMode === 'full' && !fullHistoryLoadedRef.current[activeTimeframe] && (
                <div className="px-3 py-2 bg-amber-600/10 border border-amber-500/30 rounded-lg text-xs flex items-center gap-2 text-amber-300">
                  <span>📌</span>
                  <span>Date Jump Mode</span>
                  <span className="text-[10px] opacity-70">({candlesCount.toLocaleString()} candles • Load Full History for instant cache)</span>
                </div>
              )}
              
              {dataMode === 'recent' && candlesCount > 0 && (
                <div className="px-3 py-2 bg-slate-600/10 border border-slate-500/20 rounded-lg text-xs flex items-center gap-2 text-slate-300">
                  <span>⚡</span>
                  <span>Quick Mode</span>
                  <span className="text-[10px] opacity-70">({candlesCount.toLocaleString()} candles)</span>
                </div>
              )}
              
              {/* Divider */}
              <div className="h-6 w-px bg-slate-700/50"></div>
              
              {/* Manual Refresh Button */}
              <button
                onClick={() => loadChartData(true, dataMode as 'recent' | 'full')}
                disabled={dataMode === 'loading'}
                className="px-3 py-2 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-lg text-xs transition-all hover:bg-[var(--bg-elevated)] flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                title="Manually refresh chart data"
              >
                <span>🔄</span>
                <span>Refresh</span>
              </button>

              {/* Reset Zoom Button */}
              <button
                onClick={() => {
                  if (chartRef.current) {
                    chartRef.current.timeScale().applyOptions({ barSpacing: 8 });
                    const centerDate = `${selectedYear}-${selectedMonth}-01`;
                    focusChartOnDate(centerDate, 0, chartCandles);
                  }
                }}
                className="px-3 py-2 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-lg text-xs transition-all hover:bg-[var(--bg-elevated)] flex items-center gap-2"
                title="Reset zoom to default level"
              >
                <span>🔍</span>
                <span>Reset Zoom</span>
              </button>
              
              {/* Year/Month Jump Navigation - Instant Jump */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Jump to:</span>
                
                <select
                  value={selectedYear}
                  onChange={handleYearChange}
                  disabled={isJumping}
                  className="px-2 py-1 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded text-xs hover:bg-[var(--bg-elevated)] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Select year - jumps to January of that year"
                >
                  {availableYears.map(year => (
                    <option key={year} value={year}>{year}</option>
                  ))}
                </select>
                
                <select
                  value={selectedMonth}
                  onChange={handleMonthChange}
                  disabled={isJumping}
                  className="px-2 py-1 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded text-xs hover:bg-[var(--bg-elevated)] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Select month - jumps to that month immediately"
                >
                  {availableMonths.map(month => (
                    <option key={month.value} value={month.value}>{month.label}</option>
                  ))}
                </select>
                
                {/* Loading indicator shown during jump */}
                {isJumping && (
                  <div className="px-2 py-1 bg-blue-600/10 border border-blue-500/30 rounded text-xs flex items-center gap-1 text-blue-300">
                    <span className="animate-spin">⏳</span>
                    <span className="text-[10px]">Jumping...</span>
                  </div>
                )}
              </div>
              
              {/* Timezone Selector */}
              <select
                value={chartTimezone.display_mode}
                onChange={(e) => {
                  const newMode = e.target.value as 'utc' | 'broker' | 'local';
                  console.log('🔄 TIMEZONE CHANGE TRIGGERED');
                  console.log('  Previous mode:', chartTimezone.display_mode);
                  console.log('  New mode:', newMode);
                  console.log('  Previous state:', chartTimezone);
                  
                  // Mark that user manually changed timezone
                  userChangedTimezone.current = true;
                  console.log('  🔒 User changed timezone flag set to TRUE');
                  
                  const newTimezone = {...chartTimezone, display_mode: newMode};
                  console.log('  New state to set:', newTimezone);
                  
                  setChartTimezone(newTimezone);
                  console.log('  ✅ setChartTimezone called');
                  
                  // Update chart localization in real-time
                  if (chartRef.current) {
                    console.log('  📊 Chart ref exists, updating options...');
                    
                    // Force immediate update by re-applying options
                    chartRef.current.applyOptions({
                      localization: {
                        locale: 'en-US',
                        timeFormatter: (time: number) => {
                          return formatChartTime(time, newMode, newTimezone.broker_offset_hours);
                        },
                      },
                    });
                    console.log('  ✅ applyOptions called with new formatter');
                    
                    // Trigger full time scale redraw
                    const timeScale = chartRef.current.timeScale();
                    
                    // Get current visible range
                    const visibleRange = timeScale.getVisibleRange();
                    console.log('  Current visible range:', visibleRange);
                    
                    // Force complete redraw by temporarily changing and restoring range
                    if (visibleRange) {
                      const tempRange = {
                        from: (visibleRange.from as number) - 0.0001,
                        to: (visibleRange.to as number) + 0.0001,
                      };
                      console.log('  Setting temp range:', tempRange);
                      timeScale.setVisibleRange(tempRange);
                      
                      // Restore original range after a tiny delay to force redraw
                      setTimeout(() => {
                        if (chartRef.current) {
                          console.log('  Restoring original range:', visibleRange);
                          chartRef.current.timeScale().setVisibleRange(visibleRange);
                          console.log('  ✅ Force redraw complete');
                        }
                      }, 10);
                    } else {
                      console.warn('  ⚠️ No visible range available');
                    }
                  } else {
                    console.warn('  ⚠️ Chart ref not available');
                  }
                  
                  console.log('🔄 TIMEZONE CHANGE HANDLER COMPLETE\n');
                }}
                className="px-3 py-2 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-lg text-xs transition-all hover:bg-[var(--bg-elevated)] hover:border-[var(--neon-blue)] text-[var(--text-primary)]"
                title="Chart Timezone Display"
              >
                <option value="utc">🌐 UTC</option>
                <option value="broker">🏦 Broker Time</option>
                <option value="local">🖥️ Local Time</option>
              </select>

              {/* DISABLED: year & month dropdown */}
              
              {/* Timeframe buttons */}
              {["M15", "M30", "H1", "H4", "D1"].map((tf) => (
                <button
                  key={tf}
                  onClick={() => changeTimeframe(tf)}
                  className={`px-3 py-2 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-lg text-xs transition-all hover:bg-[var(--bg-elevated)] hover:border-[var(--neon-blue)] hover:text-[var(--neon-blue)] ${
                    tf === activeTimeframe
                      ? "bg-[var(--neon-blue)] !text-white !border-[var(--neon-blue)] shadow-[0_0_20px_rgba(59,130,246,0.4)]"
                      : ""
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>
          <div 
            ref={chartContainerRef} 
            className="w-full rounded-xl overflow-hidden relative" 
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

        {/* Trades Table */}
        <div className="glass-card">
          <div className="flex justify-between items-center mb-6">
            <span className="text-xl font-semibold">💼 Recent Trades</span>
            
            {/* Filter Tabs */}
            <div className="flex gap-2">
              {["all", "open", "closed", "profit", "loss"].map((filter) => (
                <button
                  key={filter}
                  onClick={() => filterTrades(filter)}
                  className={`px-4 py-2 rounded-lg text-sm transition-all capitalize ${
                    activeFilter === filter
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
                          className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
                            trade.type === "BUY"
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
                          className={`font-semibold ${
                            trade.pnl >= 0 ? "positive" : "negative"
                          }`}
                        >
                          {trade.pnl >= 0 ? "+" : ""}${trade.pnl.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span
                          className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
                            trade.status === "OPEN"
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
                  className="h-full bg-gradient-to-r from-purple-500 to-blue-500 rounded-full transition-all duration-300"
                  style={{ width: `${loadProgress.percent}%` }}
                />
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
