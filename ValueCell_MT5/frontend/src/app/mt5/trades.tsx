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
import { useMarketStructureLines, useSessionZones } from "@/api/mt5_agents";
import {
  SessionZonesPrimitive,
  type SessionZoneBox,
} from "@/components/valuecell/charts/session-zones-primitive";
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
  const [activeTimeframe, setActiveTimeframe] = useState("M15"); // Timeframe state
  const [chartCandles, setChartCandles] = useState<Array<{time: number, open: number, high: number, low: number, close: number}>>([]);
  // CHART TIMEZONE DEFAULT = UTC.
  // When the page first opens, UTC is always selected (per requirement).
  // The user can manually switch to 'broker' or 'local'; once switched, that
  // choice is preserved across data refreshes. UTC stays default until then.
  const [chartTimezone, setChartTimezone] = useState<{broker_offset_hours: number, display_mode: string, candle_times_are_utc: boolean}>({
    broker_offset_hours: 3,
    display_mode: 'utc', // Default to UTC on every page open
    candle_times_are_utc: true
  });

  // Track if user has manually changed timezone (don't override if true)
  const userChangedTimezone = useRef(false);
  
  // Helper function to format time based on timezone mode
  // This is separate so it can be called with fresh timezone values
  const formatChartTime = (time: number, displayMode: string, brokerOffset: number): string => {
    const date = new Date(time * 1000);
    let month: string, day: string, hours: string, minutes: string;
    
    console.log('🕐 formatChartTime called:', {
      time,
      displayMode,
      brokerOffset,
      utcTime: date.toUTCString(),
      localTime: date.toString()
    });
    
    if (displayMode === 'utc') {
      month = String(date.getUTCMonth() + 1).padStart(2, '0');
      day = String(date.getUTCDate()).padStart(2, '0');
      hours = String(date.getUTCHours()).padStart(2, '0');
      minutes = String(date.getUTCMinutes()).padStart(2, '0');
      console.log('  → UTC format:', `${month}/${day} ${hours}:${minutes}`);
    } else if (displayMode === 'broker') {
      const brokerTime = new Date((time + brokerOffset * 3600) * 1000);
      month = String(brokerTime.getUTCMonth() + 1).padStart(2, '0');
      day = String(brokerTime.getUTCDate()).padStart(2, '0');
      hours = String(brokerTime.getUTCHours()).padStart(2, '0');
      minutes = String(brokerTime.getUTCMinutes()).padStart(2, '0');
      console.log('  → Broker format:', `${month}/${day} ${hours}:${minutes}`, `(offset: +${brokerOffset}h)`);
    } else { // local
      month = String(date.getMonth() + 1).padStart(2, '0');
      day = String(date.getDate()).padStart(2, '0');
      hours = String(date.getHours()).padStart(2, '0');
      minutes = String(date.getMinutes()).padStart(2, '0');
      console.log('  → Local format:', `${month}/${day} ${hours}:${minutes}`);
    }
    
    return `${month}/${day} ${hours}:${minutes}`;
  };
  

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema200SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const structureSeriesRef = useRef<ISeriesApi<"Line">[]>([]); // Line series for structure
  const sessionZonesPrimitiveRef = useRef<SessionZonesPrimitive | null>(null);
  
  // Ref to always get the latest timezone state in formatter
  const chartTimezoneRef = useRef(chartTimezone);
  
  // Update ref whenever chartTimezone changes
  useEffect(() => {
    console.log('📍 chartTimezone state changed:', {
      oldState: chartTimezoneRef.current,
      newState: chartTimezone
    });
    chartTimezoneRef.current = chartTimezone;
  }, [chartTimezone]);
  
  // Load market structure lines (180 days lookback to cover Jan-Jun 2026 chart range)
  const { data: structureLines } = useMarketStructureLines(4320); // 180 days = 4320 hours

  // Load session zones (180 days lookback, aligned with chart range)
  const { data: sessionZonesData } = useSessionZones(180);

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
            shiftVisibleRangeOnNewBar: true,
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
        
        // Re-render structure labels whenever the user pans/zooms the chart
        chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
          renderStructureLabelsOverlay(structureLabelsRef.current);
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
    // Auto-refresh chart data every 5 seconds
    const chartInterval = setInterval(() => {
      if (chartRef.current && candlestickSeriesRef.current) {
        loadChartData(false);
      }
    }, 5000);
    return () => clearInterval(chartInterval);
  }, [activeTimeframe]); // Re-run when timeframe changes

  const loadChartData = async (forceRefresh = false) => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

      // ponytail: chart reads CSV from Backtest_result (Jan 2026+), full 6 months
      const chartUrl = `${apiUrl}/trading/chart/backtest-data?symbol=XAUUSD&timeframe=${activeTimeframe}&from_date=2026-01-01`;
      console.log('Fetching chart data from:', chartUrl);

      const response = await fetch(chartUrl);
      
      console.log('Chart API response status:', response.status, response.ok);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('📉 [EMA DEBUG] API returned error:', response.status, errorText);
      }
      
      if (response.ok) {
        const data = await response.json();
        console.log('Chart API data received:', data.candles?.length, 'candles');
        console.log('📉 [EMA DEBUG] ema_periods from API:', data.ema_periods);
        
        if (data.candles && candlestickSeriesRef.current) {
          // Debug: Log first candle to check timestamp
          if (data.candles.length > 0) {
            const firstCandle = data.candles[0];
            const lastCandle = data.candles[data.candles.length - 1];
            
            console.log('📊 First candle timestamp:', firstCandle.time);
            console.log('📊 First candle as Date:', new Date(firstCandle.time * 1000).toISOString());
            console.log('📊 First candle as UTC:', new Date(firstCandle.time * 1000).toUTCString());
            console.log('📊 First candle as Local:', new Date(firstCandle.time * 1000).toString());
            
            console.log('📊 Last candle timestamp:', lastCandle.time);
            console.log('📊 Last candle as Date:', new Date(lastCandle.time * 1000).toISOString());
            console.log('📊 Last candle as UTC:', new Date(lastCandle.time * 1000).toUTCString());

            // EMA 200 detailed debug
            const ema200Values = data.candles.filter((c: any) => c.ema200 != null);
            const ema200Nulls = data.candles.filter((c: any) => c.ema200 == null);
            console.log('📉 [EMA DEBUG] Candles with ema200:', ema200Values.length);
            console.log('📉 [EMA DEBUG] Candles without ema200:', ema200Nulls.length);
            if (ema200Values.length > 0) {
              console.log('📉 [EMA DEBUG] First ema200 value:', {
                time: ema200Values[0].time,
                ema200: ema200Values[0].ema200,
                date: new Date(ema200Values[0].time * 1000).toISOString(),
              });
              console.log('📉 [EMA DEBUG] Last ema200 value:', {
                time: ema200Values[ema200Values.length - 1].time,
                ema200: ema200Values[ema200Values.length - 1].ema200,
                date: new Date(ema200Values[ema200Values.length - 1].time * 1000).toISOString(),
              });
            } else {
              console.warn('📉 [EMA DEBUG] ⚠️ NO candles have ema200 field!');
              console.log('📉 [EMA DEBUG] Sample candle keys:', Object.keys(data.candles[0]));
              console.log('📉 [EMA DEBUG] Sample candle:', data.candles[0]);
            }
          }
          
          // CRITICAL FIX: Use ISO 8601 format that lightweight-charts expects
          // Format must be: "yyyy-mm-ddThh:mm:ss" or just use Unix timestamp
          // Let's go back to Unix timestamp but with proper timezone handling
          const processedCandles = data.candles.map((candle: any) => ({
            time: candle.time as number, // Use Unix timestamp (seconds) as-is
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
          }));
          
           console.log('✅ Processed candles with Unix timestamp');
           console.log('Sample candle:', processedCandles[0]);
           
            candlestickSeriesRef.current.setData(processedCandles);
            setChartCandles(processedCandles);
            
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
          // Provide candle times so session bands snap to real bars (gold has a
          // midnight market gap, so some session boundaries have no candle).
          sessionZonesPrimitiveRef.current?.setCandleTimes(
            processedCandles.map((c: { time: number }) => c.time),
          );

          // Update EMA 200 line series from candle data
          if (ema200SeriesRef.current) {
            const ema200Data = data.candles
              .filter((candle: any) => candle.ema200 != null)
              .map((candle: any) => ({
                time: candle.time as number,
                value: candle.ema200 as number,
              }));
            console.log('📉 [EMA DEBUG] EMA 200 series ref exists:', !!ema200SeriesRef.current);
            console.log('📉 [EMA DEBUG] EMA 200 data points to set:', ema200Data.length);
            if (ema200Data.length > 0) {
              console.log('📉 [EMA DEBUG] First EMA 200 point:', ema200Data[0]);
              console.log('📉 [EMA DEBUG] Last EMA 200 point:', ema200Data[ema200Data.length - 1]);
              ema200SeriesRef.current.setData(ema200Data as any);
              console.log(`✅ EMA 200 setData called: ${ema200Data.length} points rendered`);
            } else {
              console.warn('📉 [EMA DEBUG] ⚠️ No EMA 200 data points to set! Check backend response.');
            }
          } else {
            console.warn('📉 [EMA DEBUG] ⚠️ ema200SeriesRef.current is NULL! Series not created.');
          }

          console.log('✅ Real chart data loaded from MT5');
          
          // Trigger structure overlay with fresh candle data
          if (showStructure && structureLines) {
            console.log('🔄 Triggering structure overlay after chart data load', forceRefresh ? '(force refresh)' : '');
            overlayMarketStructure(processedCandles, forceRefresh);
          }
          
          return; // Exit if API data loaded successfully
        }
      }
    } catch (error) {
      console.error("API error:", error);
      console.warn("⚠️ Unable to load chart data from MT5");
    }
  };

  // Guard to prevent concurrent executions
  const overlayGuardRef = useRef(false);

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

    console.log('📊 ===== MARKET STRUCTURE OVERLAY DEBUG =====');
    
    // Clear existing structure series
    console.log('🧹 Clearing previous structure lines:', structureSeriesRef.current.length);
    structureSeriesRef.current.forEach(series => {
      try {
        chartRef.current?.removeSeries(series);
      } catch (e) {
        console.debug('Could not remove series:', e);
      }
    });
    structureSeriesRef.current = [];
    
    console.log('Total points:', structureLines.total_points);
    console.log('Structure data:', {
      bos_count: structureLines.bos_lines?.length || 0,
      choch_count: structureLines.choch_lines?.length || 0,
      hh_count: structureLines.hh_points?.length || 0,
      ll_count: structureLines.ll_points?.length || 0,
    });
    
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
        
        if (lineType === 'BOS_CHOCH') {
          // BoS/CHoCH: line from level formation → break event
          // startTime = when the level was first formed (from HH/LL data)
          // endTime = the break event time
          startTimeSeconds = levelFormationTime ?? eventTimeSeconds;
          endTimeSeconds = eventTimeSeconds;
          
          console.log(`📏 BoS/CHoCH line at ${price}: formation=${startTimeSeconds}, break=${endTimeSeconds}`);
          console.log(`  Formation date: ${new Date(startTimeSeconds * 1000).toISOString()}`);
          console.log(`  Break date:     ${new Date(endTimeSeconds * 1000).toISOString()}`);
        } else {
          // HH/LL or generic line: starts at event time, extends right
          startTimeSeconds = eventTimeSeconds;
          // Use last visible candle time instead of "now" so line stops at last candle
          endTimeSeconds = Math.floor(Date.now() / 1000);
        }
        
        // For HH/LL/generic: use visible range for end time clipping
        if (lineType !== 'BOS_CHOCH') {
          let firstVisibleTime = startTimeSeconds;
          if (visibleRange) {
            firstVisibleTime = typeof visibleRange.from === 'number' 
              ? visibleRange.from 
              : visibleRange.from as number;
            
            const lastVisibleTime = typeof visibleRange.to === 'number'
              ? visibleRange.to
              : visibleRange.to as number;
            
            endTimeSeconds = lastVisibleTime;
            
            console.log(`Line at ${price}: Event=${startTimeSeconds}, Visible=[${firstVisibleTime}, ${lastVisibleTime}]`);
            console.log(`  Event date: ${new Date(startTimeSeconds * 1000).toISOString()}`);
            console.log(`  First visible: ${new Date(firstVisibleTime * 1000).toISOString()}`);
            console.log(`  Last visible: ${new Date(lastVisibleTime * 1000).toISOString()}`);
            
            // If event is before visible range, clip to first visible candle
            if (startTimeSeconds < firstVisibleTime) {
              console.log(`  ⚠️ Event is before visible range, clipping to first visible candle`);
            } else if (startTimeSeconds >= firstVisibleTime && startTimeSeconds <= lastVisibleTime) {
              console.log(`  ✅ Event is WITHIN visible range - line will start from event time`);
            } else {
              console.log(`  ⚠️ Event is after visible range (future?) - using event time anyway`);
            }
          }
        }
        
        // Find the breaking candle for HH/LL lines
        // HH: stops when a candle's high > HH price (bullish break)
        // LL: stops when a candle's low < LL price (bearish break)
        // If NOT broken, limit line to 15 candles after formation (short tail)
        if (lineType === 'HH' || lineType === 'LL') {
          const candles = candlesToUse;
          let candlesAfterStart = 0;
          for (const candle of candles) {
            if (candle.time > startTimeSeconds) {
              candlesAfterStart++;
              const breaks = lineType === 'HH' 
                ? candle.high > price 
                : candle.low < price;
              if (breaks) {
                endTimeSeconds = candle.time;
                console.log(`  🛑 ${lineType} broken at ${candle.time} (price: ${lineType === 'HH' ? candle.high : candle.low}), line stops here`);
                break;
              }
              // Not broken yet — cap at 15 candles after formation
              if (candlesAfterStart >= 20) {
                endTimeSeconds = candle.time;
                console.log(`  📏 ${lineType} not broken, capping line at 20 candles (${endTimeSeconds})`);
                break;
              }
            }
          }
        }
        
        // Always start line from the actual candle OPEN time (not close time)
        // CSV timestamp is candle CLOSE time, so we need to subtract 1 period
        // M15 = 15 min = 900 seconds, H1 = 3600 seconds, H4 = 14400 seconds
        const timeframePeriods: {[key: string]: number} = {
          'M15': 900,   // 15 minutes
          'M30': 1800,  // 30 minutes
          'H1': 3600,   // 1 hour
          'H4': 14400,  // 4 hours
          'D1': 86400,  // 1 day
        };
        
        console.log(`\n🔍 Finding start time for ${lineType || 'line'} at price ${price}`);
        console.log(`  CSV timestamp: ${startTimeSeconds} (${new Date(startTimeSeconds * 1000).toISOString()})`);
        console.log(`  Available candles count: ${candlesToUse.length}`);
        
        if (candlesToUse.length > 0) {
          console.log(`  First candle: ${candlesToUse[0].time} (${new Date(candlesToUse[0].time * 1000).toISOString()})`);
          console.log(`  Last candle: ${candlesToUse[candlesToUse.length - 1].time} (${new Date(candlesToUse[candlesToUse.length - 1].time * 1000).toISOString()})`);
        }
        
        // Find which candle formed this HH/LL by looking at candlesToUse
        let candleOpenTime = startTimeSeconds;
        const matchingCandle = candlesToUse.find(c => c.time === startTimeSeconds);
        
        if (matchingCandle) {
          // Found exact candle - this is the candle open time (good!)
          candleOpenTime = startTimeSeconds;
          console.log(`  ✅ Found EXACT matching candle at ${candleOpenTime}`);
        } else {
          console.log(`  ⚠️ No exact match for timestamp ${startTimeSeconds}`);
          
          // CSV timestamp might be candle close - try to find closest candle
          // Look for candles around this timestamp (within 1 hour tolerance)
          const tolerance = 3600; // 1 hour in seconds
          const nearbyCandles = candlesToUse.filter(c => 
            Math.abs(c.time - startTimeSeconds) < tolerance
          );
          
          console.log(`  Found ${nearbyCandles.length} candles within 1 hour of event`);
          
          if (nearbyCandles.length > 0) {
            // Find the closest candle BEFORE or AT the event time
            const candlesBeforeOrAt = nearbyCandles
              .filter(c => c.time <= startTimeSeconds)
              .sort((a, b) => b.time - a.time); // Sort descending (most recent first)
            
            if (candlesBeforeOrAt.length > 0) {
              candleOpenTime = candlesBeforeOrAt[0].time;
              console.log(`  ✅ Using closest candle BEFORE event: ${candleOpenTime} (${new Date(candleOpenTime * 1000).toISOString()})`);
              console.log(`     Time difference: ${startTimeSeconds - candleOpenTime} seconds (${Math.round((startTimeSeconds - candleOpenTime) / 60)} minutes)`);
            } else {
              // No candle before, use the first candle after
              const candlesAfter = nearbyCandles
                .filter(c => c.time > startTimeSeconds)
                .sort((a, b) => a.time - b.time); // Sort ascending (earliest first)
              
              if (candlesAfter.length > 0) {
                candleOpenTime = candlesAfter[0].time;
                console.log(`  ⚠️ No candle before event, using first candle AFTER: ${candleOpenTime} (${new Date(candleOpenTime * 1000).toISOString()})`);
              }
            }
          } else {
            // No nearby candles - this shouldn't happen
            console.error(`  ❌ No candles found near event timestamp!`);
            candleOpenTime = startTimeSeconds;
          }
        }
        
        const actualStartTime = candleOpenTime;
        console.log(`  📍 FINAL start time: ${actualStartTime} (${new Date(actualStartTime * 1000).toISOString()})\n`);
        
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
        // setMarkers does not exist in lightweight-charts v5, so we render
        // labels as absolutely-positioned HTML spans on the chart container.
        if (label && candlesToUse.length > 0) {
          const rawMidTime = Math.floor((actualStartTime + endTimeSeconds) / 2);
          // Find the candle closest to the midpoint (clamped between start/end)
          let nearestCandleTime = actualStartTime;
          let nearestDist = Infinity;
          for (const candle of candlesToUse) {
            if (candle.time < actualStartTime || candle.time > endTimeSeconds) continue;
            const dist = Math.abs(candle.time - rawMidTime);
            if (dist < nearestDist) {
              nearestDist = dist;
              nearestCandleTime = candle.time;
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
        
        console.log(`  ✅ Line created from ${actualStartTime} to ${endTimeSeconds}`);
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
    console.log('🔄 Structure overlay effect triggered');
    console.log('showStructure:', showStructure);
    console.log('structureLines available:', !!structureLines);
    console.log('chartRef available:', !!chartRef.current);
    console.log('candlestickSeriesRef available:', !!candlestickSeriesRef.current);
    console.log('chartCandles length:', chartCandles.length);
    console.log('activeTimeframe (from closure):', activeTimeframe);
    
    if (structureLines) {
      console.log('📦 Structure data received:', {
        total_points: structureLines.total_points,
        bos: structureLines.bos_lines?.length || 0,
        choch: structureLines.choch_lines?.length || 0,
        hh: structureLines.hh_points?.length || 0,
        ll: structureLines.ll_points?.length || 0,
        time_range_hours: structureLines.time_range_hours,
        last_updated: structureLines.last_updated,
      });
    }
    
    // CRITICAL FIX: Handle toggle OFF state
    if (!showStructure) {
      // When toggle is OFF, remove all structure lines
      console.log('🚫 Toggle is OFF - Removing all structure lines');
      structureSeriesRef.current.forEach(series => {
        try {
          chartRef.current?.removeSeries(series);
          console.log('  ✅ Removed series');
        } catch (e) {
          console.debug('  ⚠️ Could not remove series:', e);
        }
      });
      structureSeriesRef.current = [];
      console.log('  ✅ All structure lines removed');
      return; // Exit early, don't draw lines
    }
    
    // Toggle is ON - draw structure lines
    // Use chartCandles state (may be stale on initial mount, but loadChartData will forceRefresh after)
    if (showStructure && structureLines && chartRef.current && candlestickSeriesRef.current) {
      console.log('✅ Toggle is ON - Drawing structure lines');
      overlayMarketStructure(chartCandles.length > 0 ? chartCandles : undefined);
    } else {
      console.log('⏸️ Overlay skipped:', {
        showStructure,
        hasStructureLines: !!structureLines,
        hasChart: !!chartRef.current,
        hasCandlestickSeries: !!candlestickSeriesRef.current,
        candlesCount: chartCandles.length,
      });
      
      // If chart is ready but no candles yet, trigger data load
      if (showStructure && structureLines && chartRef.current && candlestickSeriesRef.current && chartCandles.length === 0) {
        console.log('📊��� Chart ready but no candles - triggering data load');
        loadChartData(true);
      }
    }
  }, [showStructure, structureLines, chartCandles.length]);

  // Update session-zone shadows when data or toggle changes
  useEffect(() => {
    const primitive = sessionZonesPrimitiveRef.current;
    if (!primitive) return;

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
    setActiveTimeframe(tf);
    // Chart will reload automatically via useEffect
    if (chartRef.current && candlestickSeriesRef.current) {
      loadChartData(true); // forceRefresh on timeframe change
    }
  };

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
                <span>📉</span>
                <span>EMA 200</span>
              </button>
              
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

        {/* Footer - Sticky to bottom */}
        <div>
          <MT5Footer />
        </div>
      </div>
    </div>
  );
}
