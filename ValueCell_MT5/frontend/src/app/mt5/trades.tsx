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
  const [chartTimezone, setChartTimezone] = useState<{broker_offset_hours: number, display_mode: string, candle_times_are_utc: boolean}>({
    broker_offset_hours: 3,
    display_mode: 'broker', // Default to Broker Time instead of UTC
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
  
  // Load market structure lines (2 weeks lookback to include BoS/CHoCH)
  const { data: structureLines } = useMarketStructureLines(336); // 14 days = 336 hours

  // Load session zones (previous day's Asia open through the live session)
  const { data: sessionZonesData } = useSessionZones(2);

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
          width: chartContainerRef.current.clientWidth,
          height: 500,
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
            rightOffset: 0,
            barSpacing: 6,
            minBarSpacing: 3,
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
      console.log('Fetching chart data from:', `${apiUrl}/trading/chart/data`);
      
      // Calculate candle count based on timeframe to show approximately 10 days of data
      const candleCountMap: { [key: string]: number } = {
        M15: 960,  // 10 days × 24 hours × 4 candles/hour
        M30: 480,  // 10 days × 24 hours × 2 candles/hour
        H1: 240,   // 10 days × 24 hours
        H4: 60,    // 10 days × 6 candles/day
        D1: 30,    // 30 days
      };
      
      const count = candleCountMap[activeTimeframe] || 960;
      
      const response = await fetch(
        `${apiUrl}/trading/chart/data?symbol=XAUUSD&timeframe=${activeTimeframe}&count=${count}&ema=200`
      );
      
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
            
            // Store timezone info from API (only if user hasn't manually changed it)
            if (data.timezone && !userChangedTimezone.current) {
              setChartTimezone(data.timezone);
              console.log('🌍 Chart timezone config from API:', data.timezone);
            } else if (userChangedTimezone.current) {
              console.log('🚫 Skipping timezone update from API (user manually changed it)');
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
    // Creates line from event timestamp, or from first visible candle if event is older
    const createHorizontalLine = (
      price: number,
      timestamp: number,
      color: string,
      lineWidth: number,
      lineStyle: number,
      label: string,
      lineType?: 'HH' | 'LL' // HH = Higher High (stops when high > price), LL = Lower Low (stops when low < price)
    ) => {
      try {
        // Get visible time range from chart
        const timeScale = chartRef.current!.timeScale();
        const visibleRange = timeScale.getVisibleRange();
        
        // CRITICAL: Check if timestamp is in milliseconds or seconds
        const isMilliseconds = timestamp > 10000000000;
        const startTimeSeconds = isMilliseconds ? Math.floor(timestamp / 1000) : timestamp;
        
        // Use last visible candle time instead of "now" so line stops at last candle
        let endTimeSeconds = Math.floor(Date.now() / 1000);
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
          
          // SOLUTION: If event is before visible range, clip to first visible candle
          // This way the line still shows (starting from left edge of chart)
          if (startTimeSeconds < firstVisibleTime) {
            console.log(`  ⚠️ Event is before visible range, clipping to first visible candle`);
          } else if (startTimeSeconds >= firstVisibleTime && startTimeSeconds <= lastVisibleTime) {
            console.log(`  ✅ Event is WITHIN visible range - line will start from event time`);
          } else {
            console.log(`  ⚠️ Event is after visible range (future?) - using event time anyway`);
          }
        }
        
        // Find the breaking candle for HH/LL lines
        // HH: stops when a candle's high > HH price (bullish break)
        // LL: stops when a candle's low < LL price (bearish break)
        if (lineType === 'HH' || lineType === 'LL') {
          const candles = candlesToUse;
          for (const candle of candles) {
            if (candle.time > startTimeSeconds) {
              const breaks = lineType === 'HH' 
                ? candle.high > price 
                : candle.low < price;
              if (breaks) {
                endTimeSeconds = candle.time;
                console.log(`  🛑 ${lineType} broken at ${candle.time} (price: ${lineType === 'HH' ? candle.high : candle.low}), line stops here`);
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
          title: label,            // Label shown on left side only
        };
        
        // Create line data from event time (or clipped to first visible) to breaking candle or end of range
        const lineData = [
          { time: actualStartTime, value: price }, // Start point
          { time: endTimeSeconds, value: price },   // End point (breaking candle or last visible)
        ];

        const lineSeries = chartRef.current!.addSeries(LineSeries, lineOptions);
        lineSeries.setData(lineData);
        structureSeriesRef.current.push(lineSeries);
        
        console.log(`  ✅ Line created from ${actualStartTime} to ${endTimeSeconds}`);
        return true;
      } catch (e) {
        console.error('Error creating line:', e);
        return false;
      }
    };

    // Add BoS lines
    let bosAdded = 0;
    structureLines.bos_lines?.forEach((bos, index) => {
      console.log(`Adding BoS #${index + 1}:`, { price: bos.price, time: bos.time, timestamp: bos.timestamp });
      const color = bos.direction === 'BULLISH' ? '#10b981' : '#ef4444';
      // timestamp is already in milliseconds from backend
      const eventTime = bos.timestamp;
      if (createHorizontalLine(
        bos.price,
        eventTime,
        color,
        2,
        LineStyle.Solid,
        `BoS ${bos.price.toFixed(2)}`
      )) {
        bosAdded++;
        console.log(`✅ BoS #${index + 1} added at ${eventTime}ms (${bos.time})`);
      }
    });

    // Add CHoCH lines
    let chochAdded = 0;
    structureLines.choch_lines?.forEach((choch, index) => {
      console.log(`Adding CHoCH #${index + 1}:`, { price: choch.price, time: choch.time, timestamp: choch.timestamp });
      const eventTime = choch.timestamp;
      if (createHorizontalLine(
        choch.price,
        eventTime,
        '#a855f7',
        2,
        LineStyle.Dashed,
        `CHoCH ${choch.price.toFixed(2)}`
      )) {
        chochAdded++;
        console.log(`✅ CHoCH #${index + 1} added at ${eventTime}ms (${choch.time})`);
      }
    });

    // Add HH lines (with H1 vs M15 differentiation)
    let hhAdded = 0;
    console.log('\n🔵 Processing HH points...');
    if (!structureLines.hh_points || structureLines.hh_points.length === 0) {
      console.warn('⚠️ No HH points available!');
    } else {
      structureLines.hh_points.forEach((hh, index) => {
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
    let llAdded = 0;
    console.log('\n🟠 Processing LL points...');
    if (!structureLines.ll_points || structureLines.ll_points.length === 0) {
      console.warn('⚠️ No LL points available!');
    } else {
      structureLines.ll_points.forEach((ll, index) => {
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

    console.log('\n✅ ===== OVERLAY COMPLETE =====');
    console.log('Lines added:', {
      bos: bosAdded,
      choch: chochAdded,
      hh: hhAdded,
      ll: llAdded,
      total: bosAdded + chochAdded + hhAdded + llAdded,
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
            className="w-full rounded-xl overflow-hidden" 
            style={{ height: "500px" }}
          />
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
