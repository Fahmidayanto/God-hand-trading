export interface ReplayCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema200: number | null;
  spread?: number | null;
}

export interface StructureEvent {
  type: string;
  direction: string;
  price: number;
  time: number;
  timeframe: string;
  status: string;
  previous_price: number | null;
  previous_time: number | null;
}

export interface ReplayTrade {
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
  spread_cost?: number | null;
  commission?: number | null;
  swap?: number | null;
}

export interface ReplayData {
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

export interface EntryFilterParams {
  entry_choch: boolean;
  entry_bos: boolean;
  entry_bos_cycle_2_plus: boolean;
  max_bos_cycle: number;
  h1_ema200_filter: boolean;
  h4_ema_filter: boolean;
  ema_slope_filter: boolean;
  body_ratio_filter: boolean;
  session_filter: boolean;
  ema_stretch_filter: boolean;
  bos_cycle_filter: boolean;
}

export const DEFAULT_ENTRY_FILTER_PARAMS: EntryFilterParams = {
  entry_choch: true,
  entry_bos: true,
  entry_bos_cycle_2_plus: true,
  max_bos_cycle: 2,
  h1_ema200_filter: true,
  h4_ema_filter: true,
  ema_slope_filter: true,
  body_ratio_filter: false,
  session_filter: false,
  ema_stretch_filter: true,
  bos_cycle_filter: true,
};

export interface StrategyParams {
  trailing_distance: number;
  tp_trigger: number;
  tp_ekspansi: number;
  max_ekspansi: number;
  enable_breakeven: boolean;
  breakeven_trigger: number;
  breakeven_buffer: number;
  lot_override: number;
  initial_tp_dist: number;
  sl_safety_buffer: number;
  min_sl_dist: number;
  max_sl_dist: number;
  force_24h_close: boolean;
  enable_profit_target_exit: boolean;
  profit_target_exit_usd: number;
  initial_balance: number;
  use_atr_sltp: boolean;
  atr_period: number;
  atr_sl_multiplier: number;
  atr_tp_multiplier: number;
  show_supply_demand: boolean;
  show_liquidity_pools: boolean;
  use_price_ratio_scaling: boolean;
  base_reference_price: number;
  risk_pct?: number;
}

export const DEFAULT_STRATEGY_PARAMS: StrategyParams = {
  trailing_distance: 30,
  tp_trigger: 10,
  tp_ekspansi: 20,
  max_ekspansi: 0,
  enable_breakeven: false,
  breakeven_trigger: 15,
  breakeven_buffer: 1,
  lot_override: 0.05,
  initial_tp_dist: 30,
  sl_safety_buffer: 10,
  min_sl_dist: 15,
  max_sl_dist: 30,
  force_24h_close: true,
  enable_profit_target_exit: false,
  profit_target_exit_usd: 300,
  initial_balance: 1000,
  use_atr_sltp: false,
  atr_period: 14,
  atr_sl_multiplier: 1.5,
  atr_tp_multiplier: 2,
  show_supply_demand: false,
  show_liquidity_pools: false,
  use_price_ratio_scaling: true,
  base_reference_price: 2000,
};

export function getActualLotSize(trade: ReplayTrade): number {
  const entryPrice = trade.entry_price ?? 0;
  const exitPrice = trade.exit_price ?? 0;
  const netProfit = trade.net_profit ?? 0;
  const priceDifference = Math.abs(exitPrice - entryPrice);
  if (priceDifference > 0.01) {
    const roundedLot = Math.round((Math.abs(netProfit) / (priceDifference * 100)) * 100) / 100;
    if (roundedLot >= 0.01 && roundedLot <= 50) return roundedLot;
  }
  return trade.lot_size ?? 0.05;
}

export function calculateATR(candles: ReplayCandle[], upToTime: number, period = 14): number | null {
  if (candles.length <= period) return null;
  let low = 0;
  let high = candles.length - 1;
  let targetIndex = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (candles[middle].time <= upToTime) {
      targetIndex = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  if (targetIndex < period) return null;
  let trueRangeTotal = 0;
  for (let index = targetIndex; index > targetIndex - period; index -= 1) {
    const candle = candles[index];
    const previousClose = candles[index - 1].close;
    trueRangeTotal += Math.max(
      candle.high - candle.low,
      Math.abs(candle.high - previousClose),
      Math.abs(candle.low - previousClose),
    );
  }
  return trueRangeTotal / period;
}

export function calculateTradeSwap(entryTime: number, exitTime: number, lotSize: number, isBuy: boolean): number {
  if (!entryTime || !exitTime || exitTime <= entryTime) return 0;
  const dailyRate = isBuy ? -12.5 : -4.5;
  const startDay = Math.floor(entryTime / 86400) * 86400;
  const endDay = Math.floor(exitTime / 86400) * 86400;
  let totalDays = 0;
  for (let time = startDay + 86400; time <= endDay; time += 86400) {
    const day = new Date(time * 1000).getUTCDay();
    if (day === 4) totalDays += 3;
    else if (day === 1 || day === 2 || day === 3 || day === 5) totalDays += 1;
  }
  return Number((totalDays * dailyRate * lotSize).toFixed(2));
}

function getLastStructurePrice(entryTime: number, structures: StructureEvent[], type: "LL" | "HH") {
  let price: number | null = null;
  for (const event of structures) {
    if (event.time > entryTime) break;
    if (event.type?.toUpperCase() === type) price = event.price;
  }
  return price;
}

export function simulateTrailingSLTP(
  trade: ReplayTrade,
  candles: ReplayCandle[],
  currentCandleTime: number,
  structures: StructureEvent[],
  params: StrategyParams = DEFAULT_STRATEGY_PARAMS,
) {
  const entryPrice = trade.entry_price ?? 0;
  const type = trade.type.toLowerCase();
  const ratio = params.use_price_ratio_scaling && params.base_reference_price > 0 && entryPrice > 0
    ? entryPrice / params.base_reference_price
    : 1;
  const baseLot = params.lot_override > 0 ? params.lot_override : getActualLotSize(trade);
  const lotSize = params.use_price_ratio_scaling ? Math.max(0.01, Number((baseLot / ratio).toFixed(2))) : baseLot;
  const trailingDistance = params.trailing_distance * ratio;
  const tpTrigger = params.tp_trigger * ratio;
  const tpExpansion = params.tp_ekspansi * ratio;
  const breakevenTrigger = params.breakeven_trigger * ratio;
  const breakevenBuffer = params.breakeven_buffer * ratio;
  const initialTpDistance = params.initial_tp_dist * ratio;
  const slSafetyBuffer = params.sl_safety_buffer * ratio;
  const minSlDistance = params.min_sl_dist * ratio;
  const maxSlDistance = params.max_sl_dist * ratio;

  let initialSL: number;
  let initialTP: number | null;
  if (params.use_atr_sltp) {
    const atr = calculateATR(candles, trade.entry_time ?? 0, params.atr_period);
    if (atr != null && atr > 0) {
      initialSL = type === "buy" ? entryPrice - atr * params.atr_sl_multiplier : entryPrice + atr * params.atr_sl_multiplier;
      initialTP = type === "buy" ? entryPrice + atr * params.atr_tp_multiplier : entryPrice - atr * params.atr_tp_multiplier;
    } else {
      const distance = Math.max(minSlDistance, Math.min(maxSlDistance, trailingDistance));
      initialSL = type === "buy" ? entryPrice - distance : entryPrice + distance;
      initialTP = type === "buy" ? entryPrice + (initialTpDistance || 30 * ratio) : entryPrice - (initialTpDistance || 30 * ratio);
    }
  } else {
    const structuralSL = (type === "buy"
      ? getLastStructurePrice(trade.entry_time ?? 0, structures, "LL")
      : getLastStructurePrice(trade.entry_time ?? 0, structures, "HH"))
      ?? (type === "buy" ? trade.sl ?? entryPrice - trailingDistance : trade.sl ?? entryPrice + trailingDistance);
    const bufferedSL = type === "buy" ? structuralSL - slSafetyBuffer : structuralSL + slSafetyBuffer;
    const distance = Math.max(minSlDistance, Math.min(maxSlDistance, Math.abs(entryPrice - bufferedSL)));
    initialSL = type === "buy" ? entryPrice - distance : entryPrice + distance;
    initialTP = initialTpDistance > 0
      ? type === "buy" ? entryPrice + initialTpDistance : entryPrice - initialTpDistance
      : trade.tp ?? (type === "buy" ? entryPrice + 30 * ratio : entryPrice - 30 * ratio);
  }

  let currentSL = initialSL;
  let currentTP = initialTP;
  const slHistory = [initialSL];
  const tpHistory = initialTP !== null ? [initialTP] : [];
  const startIndex = Math.max(0, candles.findIndex((candle) => candle.time >= (trade.entry_time ?? 0)));
  let endIndex = candles.length - 1;
  for (let index = startIndex; index < candles.length; index += 1) {
    if (candles[index].time > currentCandleTime) {
      endIndex = index - 1;
      break;
    }
  }

  let expansionCount = 0;
  let breakevenTriggered = false;
  let isClosed = false;
  let exitPrice: number | null = null;
  let exitTime: number | null = null;
  let closeReason: "TP" | "SL" | "24H_FORCE" | "PROFIT_TARGET" | null = null;
  let maxFavorablePoints = 0;
  let maxAdversePoints = 0;
  let protectionActivatedTime: number | null = null;

  for (let index = startIndex; index <= endIndex; index += 1) {
    const candle = candles[index];
    const price = candle.close;
    const favorable = type === "buy" ? Math.max(0, (candle.high - entryPrice) * 100) : Math.max(0, (entryPrice - candle.low) * 100);
    const adverse = type === "buy" ? Math.max(0, (entryPrice - candle.low) * 100) : Math.max(0, (candle.high - entryPrice) * 100);
    maxFavorablePoints = Math.max(maxFavorablePoints, Math.round(favorable));
    maxAdversePoints = Math.max(maxAdversePoints, Math.round(adverse));

    if (params.force_24h_close && candle.time - (trade.entry_time ?? 0) >= 86400) {
      isClosed = true;
      exitPrice = candle.open;
      exitTime = candle.time;
      closeReason = "24H_FORCE";
      break;
    }

    const canExpand = params.max_ekspansi === 0 || expansionCount < params.max_ekspansi;
    if (type === "buy" && canExpand && currentTP !== null && currentTP - candle.open <= tpTrigger) {
      const expandedTP = candle.open + tpExpansion;
      if (expandedTP > currentTP) {
        currentTP = expandedTP;
        expansionCount += 1;
        tpHistory.push(expandedTP);
      }
    } else if (type === "sell" && canExpand && currentTP !== null && candle.open - currentTP <= tpTrigger) {
      const expandedTP = candle.open - tpExpansion;
      if (expandedTP < currentTP) {
        currentTP = expandedTP;
        expansionCount += 1;
        tpHistory.push(expandedTP);
      }
    }

    if (params.enable_profit_target_exit && params.profit_target_exit_usd > 0) {
      const floating = type === "buy" ? (candle.high - entryPrice) * lotSize * 100 : (entryPrice - candle.low) * lotSize * 100;
      if (floating >= params.profit_target_exit_usd) {
        isClosed = true;
        exitPrice = Number((type === "buy"
          ? entryPrice + params.profit_target_exit_usd / (lotSize * 100)
          : entryPrice - params.profit_target_exit_usd / (lotSize * 100)).toFixed(2));
        exitTime = candle.time;
        closeReason = "PROFIT_TARGET";
        break;
      }
    }

    if (type === "buy") {
      if (candle.low <= currentSL || (currentTP !== null && candle.high >= currentTP)) {
        isClosed = true;
        const hitSL = candle.low <= currentSL;
        exitPrice = hitSL ? currentSL : currentTP;
        exitTime = candle.time;
        closeReason = hitSL ? "SL" : "TP";
        break;
      }
      if (params.enable_breakeven && candle.high - entryPrice >= breakevenTrigger) {
        breakevenTriggered = true;
        protectionActivatedTime ??= candle.time;
      }
      let nextSL = Math.max(entryPrice - trailingDistance, Math.min(price - 1.5, price - trailingDistance));
      if (breakevenTriggered) nextSL = Math.max(nextSL, entryPrice + breakevenBuffer);
      nextSL = Math.max(currentSL, nextSL);
      if (Math.abs(nextSL - currentSL) >= 0.1) {
        currentSL = nextSL;
        if (Math.abs(nextSL - slHistory.at(-1)!) >= 2) slHistory.push(nextSL);
      }
    } else {
      const spread = candle.spread != null && candle.spread > 0 ? candle.spread * 0.01 : 0.04;
      const normalSpread = Math.min(spread, 0.6);
      const askHigh = Math.max(candle.open + spread, candle.high + normalSpread);
      const askLow = candle.low + normalSpread;
      if (askHigh >= currentSL || (currentTP !== null && askLow <= currentTP)) {
        isClosed = true;
        const hitSL = askHigh >= currentSL;
        exitPrice = hitSL ? currentSL : currentTP;
        exitTime = candle.time;
        closeReason = hitSL ? "SL" : "TP";
        break;
      }
      if (params.enable_breakeven && entryPrice - candle.low >= breakevenTrigger) {
        breakevenTriggered = true;
        protectionActivatedTime ??= candle.time;
      }
      let nextSL = Math.max(price + 1.5, Math.min(entryPrice + trailingDistance, price + trailingDistance));
      if (breakevenTriggered) nextSL = Math.min(nextSL, entryPrice - breakevenBuffer);
      nextSL = Math.min(currentSL, nextSL);
      if (Math.abs(nextSL - currentSL) >= 0.1) {
        currentSL = nextSL;
        if (Math.abs(nextSL - slHistory.at(-1)!) >= 2) slHistory.push(nextSL);
      }
    }
  }

  if (Math.abs(currentSL - slHistory.at(-1)!) > 0.01) slHistory.push(currentSL);
  if (currentTP !== null && tpHistory.length > 0 && Math.abs(currentTP - tpHistory.at(-1)!) > 0.01) tpHistory.push(currentTP);
  return {
    initialSL,
    initialTP,
    sl: currentSL,
    tp: currentTP,
    slHistory,
    tpHistory,
    closeReason,
    beTriggered: breakevenTriggered,
    isClosedSimulated: isClosed,
    exitPriceSimulated: exitPrice,
    exitTimeSimulated: exitTime,
    protectionActivatedTime,
    expansionCount,
    maxFavorablePoints,
    maxAdversePoints,
  };
}

export function simulateReplayTradeOutcome(
  trade: ReplayTrade,
  candles: ReplayCandle[],
  structures: StructureEvent[],
  params: StrategyParams = DEFAULT_STRATEGY_PARAMS,
  currentCandleTime = candles.at(-1)?.time ?? 0,
) {
  const levels = simulateTrailingSLTP(trade, candles, currentCandleTime, structures, params);
  const entryPrice = trade.entry_price ?? 0;
  const exitPrice = levels.exitPriceSimulated ?? entryPrice;
  const exitTime = levels.exitTimeSimulated;
  const ratio = params.use_price_ratio_scaling && params.base_reference_price > 0 && entryPrice > 0
    ? entryPrice / params.base_reference_price
    : 1;
  const baseLot = params.lot_override > 0 ? params.lot_override : getActualLotSize(trade);
  const lotSize = params.use_price_ratio_scaling ? Math.max(0.01, Number((baseLot / ratio).toFixed(2))) : baseLot;
  const entryCandle = candles.find((candle) => candle.time === trade.entry_time) ?? candles.find((candle) => candle.time === (trade.entry_time ?? 0) - 900);
  const spreadPoints = entryCandle?.spread != null && entryCandle.spread > 0 ? entryCandle.spread : 4;
  const spreadCost = trade.spread_cost != null && trade.spread_cost > 0 ? trade.spread_cost : spreadPoints * 0.01 * lotSize * 100;
  const commission = trade.commission ?? 0;
  const swap = trade.swap != null && trade.swap !== 0
    ? trade.swap
    : calculateTradeSwap(trade.entry_time ?? 0, exitTime ?? currentCandleTime, lotSize, trade.type.toLowerCase() === "buy");
  const grossProfit = trade.type.toLowerCase() === "buy"
    ? (exitPrice - entryPrice) * lotSize * 100
    : (entryPrice - exitPrice) * lotSize * 100;
  const netProfit = levels.isClosedSimulated ? Number((grossProfit - spreadCost - commission + swap).toFixed(2)) : null;
  return {
    ...levels,
    isClosed: levels.isClosedSimulated,
    exitPrice,
    exitTime,
    lotSize,
    spreadCost: Number(spreadCost.toFixed(2)),
    commission,
    swap,
    grossProfit: Number(grossProfit.toFixed(2)),
    netProfit,
  };
}

export function getTimestampSeconds(timeValue: unknown): number {
  if (timeValue === null || timeValue === undefined) return 0;
  if (typeof timeValue === "number") return timeValue;
  if (typeof timeValue === "string") {
    const numericValue = Number(timeValue);
    if (!Number.isNaN(numericValue)) return numericValue;
    const parsedValue = Date.parse(timeValue);
    if (!Number.isNaN(parsedValue)) return Math.floor(parsedValue / 1000);
  }
  return 0;
}

export function getEntryStructureInfo(entryTime: number, structures: StructureEvent[], direction?: string) {
  let latestType = "";
  let latestTypeBuy = "";
  let latestTypeSell = "";
  let bosCycleBuy = 0;
  let bosCycleSell = 0;

  for (const event of structures) {
    if (event.time > entryTime) break;
    if (event.timeframe && event.timeframe.toUpperCase() !== "M15") continue;

    const type = event.type?.toUpperCase() ?? "";
    const eventDirection = (event.direction ?? "").toUpperCase();
    const isBull = eventDirection.includes("BULL") || type.includes("BULL");
    const isBear = eventDirection.includes("BEAR") || type.includes("BEAR");

    if (type.includes("CHOCH")) {
      latestType = "CHOCH";
      if (isBull) {
        latestTypeBuy = "CHOCH";
        bosCycleBuy = 0;
      }
      if (isBear) {
        latestTypeSell = "CHOCH";
        bosCycleSell = 0;
      }
      if (!isBull && !isBear) {
        latestTypeBuy = "CHOCH";
        latestTypeSell = "CHOCH";
        bosCycleBuy = 0;
        bosCycleSell = 0;
      }
    } else if (type.includes("BOS")) {
      latestType = "BOS";
      if (isBull) {
        latestTypeBuy = "BOS";
        bosCycleBuy += 1;
      }
      if (isBear) {
        latestTypeSell = "BOS";
        bosCycleSell += 1;
      }
      if (!isBull && !isBear) {
        latestTypeBuy = "BOS";
        latestTypeSell = "BOS";
        bosCycleBuy += 1;
        bosCycleSell += 1;
      }
    }
  }

  const upperDirection = (direction ?? "").toUpperCase();
  const isSell = upperDirection.includes("SELL") || upperDirection.includes("BEAR");
  const isBuy = upperDirection.includes("BUY") || upperDirection.includes("BULL");
  const effectiveLatestType = isSell ? latestTypeSell || latestType : isBuy ? latestTypeBuy || latestType : latestType;
  const bosCycle = isSell ? bosCycleSell : bosCycleBuy;

  return { latestType: effectiveLatestType, bosCycle, bosCycleBuy, bosCycleSell };
}

export function getCandleAtOrBefore(candles: ReplayCandle[], time: number) {
  for (let index = candles.length - 1; index >= 0; index -= 1) {
    if (candles[index].time <= time) return candles[index];
  }
  return null;
}

export function getCandleIndexAtOrBefore(candles: ReplayCandle[], time: number) {
  for (let index = candles.length - 1; index >= 0; index -= 1) {
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
  const m15Candle = m15Index > 0 ? m15Candles[m15Index - 1] : null;
  const currentPrice = trade.entry_price != null && trade.entry_price > 0
    ? trade.entry_price
    : m15Index >= 0
      ? m15Candles[m15Index].open || m15Candles[m15Index].close
      : m15Candle?.close ?? 0;
  const h1Candle = getCandleAtOrBefore(h1Candles, entryTime);
  const h4Index = getCandleIndexAtOrBefore(h4Candles, entryTime);
  const h4Candle = h4Index >= 0 ? h4Candles[h4Index] : null;

  if (params.h1_ema200_filter && h1Candles.length > 0 && h1Candle?.ema200 != null && h1Candle.ema200 > 0 && currentPrice > 0) {
    if (isBuy ? currentPrice <= h1Candle.ema200 : currentPrice >= h1Candle.ema200) return false;
  }

  if (params.h4_ema_filter && h4Candles.length > 0 && h4Candle?.ema200 != null && h4Candle.ema200 > 0 && currentPrice > 0) {
    const gapThreshold = Math.max(h4Candle.ema200 * 0.0025, 5);
    if (isBuy ? currentPrice <= h4Candle.ema200 + gapThreshold : currentPrice >= h4Candle.ema200 - gapThreshold) return false;
  }

  if (params.ema_slope_filter) {
    const previousCandle = m15Index > 1 ? m15Candles[m15Index - 2] : null;
    if (m15Candle?.ema200 == null || previousCandle?.ema200 == null) return false;
    if (isBuy ? m15Candle.ema200 <= previousCandle.ema200 : m15Candle.ema200 >= previousCandle.ema200) return false;
  }

  if (params.body_ratio_filter) {
    if (!m15Candle) return false;
    const range = m15Candle.high - m15Candle.low;
    if (range > 0) {
      const bodyRatio = Math.abs(m15Candle.close - m15Candle.open) / range;
      let effectiveMinBodyRatio = 0.4;
      const h4MomentumCandle = h4Index >= 4 ? h4Candles[h4Index - 4] : null;
      if (h4Candle?.ema200 != null && h4MomentumCandle) {
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

  const { latestType, bosCycle } = getEntryStructureInfo(entryTime, structures, trade.type);
  if (latestType === "CHOCH" && !params.entry_choch) return "CHoCH Filter (Disabled)";
  if (latestType === "BOS") {
    if (bosCycle === 1 && !params.entry_bos) return "BOS 1 Filter (Disabled)";
    if (bosCycle >= 2 && !params.entry_bos_cycle_2_plus) return "BOS 2+ Filter (Disabled)";
    if (params.max_bos_cycle > 0 && bosCycle > params.max_bos_cycle) return `Max BOS Cycle Limit (${params.max_bos_cycle})`;
  }

  const isBuy = trade.type.toUpperCase() === "BUY";
  const m15Index = getCandleIndexAtOrBefore(m15Candles, entryTime);
  const m15Candle = m15Index > 0 ? m15Candles[m15Index - 1] : null;
  const currentPrice = trade.entry_price != null && trade.entry_price > 0
    ? trade.entry_price
    : m15Index >= 0
      ? m15Candles[m15Index].open || m15Candles[m15Index].close
      : m15Candle?.close ?? 0;
  const h1Candle = getCandleAtOrBefore(h1Candles, entryTime);
  const h4Candle = getCandleAtOrBefore(h4Candles, entryTime);

  if (params.session_filter && new Date(entryTime * 1000).getUTCHours() === 1) return "Session Filter (01:00 UTC)";
  if (params.h1_ema200_filter && h1Candles.length > 0 && h1Candle?.ema200 != null && h1Candle.ema200 > 0 && currentPrice > 0 && (isBuy ? currentPrice <= h1Candle.ema200 : currentPrice >= h1Candle.ema200)) return "H1 EMA200 Filter";
  if (params.h4_ema_filter && h4Candles.length > 0 && h4Candle?.ema200 != null && h4Candle.ema200 > 0 && currentPrice > 0) {
    const gapThreshold = Math.max(h4Candle.ema200 * 0.0025, 5);
    if (isBuy ? currentPrice <= h4Candle.ema200 + gapThreshold : currentPrice >= h4Candle.ema200 - gapThreshold) return "H4 EMA Filter";
  }
  if (params.ema_slope_filter) {
    const previousCandle = m15Index > 1 ? m15Candles[m15Index - 2] : null;
    if (m15Candle?.ema200 == null || previousCandle?.ema200 == null || (isBuy ? m15Candle.ema200 <= previousCandle.ema200 : m15Candle.ema200 >= previousCandle.ema200)) return "EMA Slope Filter";
  }
  if (params.body_ratio_filter && !passesEAEntryFilters(trade, m15Candles, h1Candles, h4Candles, { ...params, h1_ema200_filter: false, h4_ema_filter: false, ema_slope_filter: false, session_filter: false })) return "Body Ratio Filter";
  if (trade.reject_reason && trade.reject_reason !== "N/A") return trade.reject_reason;
  return "Filter Rejection";
}

function createLocalStructureCandidateTrades(
  data: ReplayData,
  m15Candles: ReplayCandle[],
  h1Candles: ReplayCandle[],
  h4Candles: ReplayCandle[],
  params: EntryFilterParams,
): ReplayTrade[] {
  const candleByTime = new Map(data.candles.map((candle) => [candle.time, candle]));
  const seenEventTimes = new Set<number>();

  return data.structures.flatMap((event) => {
    const typeUpper = event.type?.toUpperCase() ?? "";
    const isChoch = typeUpper.includes("CHOCH");
    const isBos = typeUpper.includes("BOS");
    if (!isChoch && !isBos) return [];

    const eventSeconds = getTimestampSeconds(event.time);
    if (eventSeconds === 0 || seenEventTimes.has(eventSeconds)) return [];
    seenEventTimes.add(eventSeconds);

    const candle = candleByTime.get(eventSeconds);
    const direction = event.direction?.toUpperCase() ?? "";
    if (candle?.close === undefined || (!direction.includes("BULL") && !direction.includes("BEAR"))) return [];

    const isBuy = direction.includes("BULL");
    const spreadPoints = candle.spread != null && candle.spread > 0 ? candle.spread : 3;
    const candidate: ReplayTrade = {
      ticket: 0,
      type: isBuy ? "BUY" : "SELL",
      status: "EXECUTED",
      reject_reason: null,
      entry_price: isBuy ? Number((candle.close + spreadPoints * 0.01).toFixed(2)) : candle.close,
      exit_price: null,
      sl: null,
      tp: null,
      net_profit: null,
      session: isChoch ? "CHOCH" : "BOS",
      entry_time: eventSeconds + 900,
      exit_time: null,
      lot_size: 0.01,
    };

    const { latestType, bosCycle } = getEntryStructureInfo(eventSeconds, data.structures, candidate.type);
    const matchesStructureFilter = latestType === "CHOCH"
      ? params.entry_choch
      : latestType === "BOS"
        && (bosCycle === 1
          ? params.entry_bos
          : bosCycle >= 2 && params.entry_bos_cycle_2_plus && (params.max_bos_cycle === 0 || bosCycle <= params.max_bos_cycle));
    const passesFilters = matchesStructureFilter && passesEAEntryFilters(candidate, m15Candles, h1Candles, h4Candles, params);

    return [{
      ...candidate,
      status: passesFilters ? "EXECUTED" : "REJECTED",
      reject_reason: passesFilters ? null : getReplayFilterRejectReason(candidate, data.structures, m15Candles, h1Candles, h4Candles, params),
    }];
  });
}

export function getProcessedReplayTrades(
  data: ReplayData,
  structures: StructureEvent[],
  params: EntryFilterParams,
  m15Candles: ReplayCandle[],
  h1Candles: ReplayCandle[],
  h4Candles: ReplayCandle[],
  isLLMActive = false,
): { executedTrades: ReplayTrade[]; rejectedTrades: ReplayTrade[] } {
  if (isLLMActive) return { executedTrades: [], rejectedTrades: [] };

  const rawCandidates = createLocalStructureCandidateTrades(data, m15Candles, h1Candles, h4Candles, params);
  const seenBuckets = new Set<string>();
  const allCandidates: ReplayTrade[] = [];

  for (const trade of rawCandidates) {
    if (trade.entry_time == null) continue;
    const entryTime = getTimestampSeconds(trade.entry_time);
    const candleBucket = Math.round(entryTime / 900) * 900;
    const bucketKey = `${trade.type}_${candleBucket}`;
    if (seenBuckets.has(bucketKey)) continue;
    seenBuckets.add(bucketKey);
    allCandidates.push({ ...trade, entry_time: entryTime });
  }

  allCandidates.sort((left, right) => (left.entry_time ?? 0) - (right.entry_time ?? 0));
  allCandidates.forEach((trade, index) => {
    trade.ticket = index + 1;
  });

  const executedTrades: ReplayTrade[] = [];
  const rejectedTrades: ReplayTrade[] = [];
  for (const trade of allCandidates) {
    if (trade.entry_time === null) continue;
    const { latestType, bosCycle } = getEntryStructureInfo(trade.entry_time, structures, trade.type);
    const matchesStructureFilter = latestType === "CHOCH"
      ? params.entry_choch
      : latestType === "BOS"
        && (bosCycle === 1
          ? params.entry_bos
          : bosCycle >= 2 && params.entry_bos_cycle_2_plus && (params.max_bos_cycle === 0 || bosCycle <= params.max_bos_cycle));
    const passesFilters = matchesStructureFilter && passesEAEntryFilters(trade, m15Candles, h1Candles, h4Candles, params);

    if (passesFilters) {
      executedTrades.push({ ...trade, status: "EXECUTED", reject_reason: null });
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