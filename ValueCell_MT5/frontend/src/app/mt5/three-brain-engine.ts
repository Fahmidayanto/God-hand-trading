import { evaluateContinuationStrength } from "./continuation-strength.ts";
import { evaluateExitTargetObserver } from "./exit-target-observer.ts";
import {
  DEFAULT_STRATEGY_PARAMS,
  calculateATR,
  calculateTradeSwap,
  getActualLotSize,
  simulateTrailingSLTP,
  type ReplayCandle,
  type ReplayTrade,
  type StrategyParams,
  type StructureEvent,
} from "./replay-engine.ts";

function getStructureAlignment(
  direction: string,
  candleTime: number,
  structures: StructureEvent[],
): boolean {
  const latestStructure = [...structures]
    .reverse()
    .find((event) => event.time <= candleTime && (!event.timeframe || event.timeframe.toUpperCase() === "M15"));
  const structureDirection = `${latestStructure?.direction ?? ""} ${latestStructure?.type ?? ""}`.toUpperCase();
  return direction.includes("BUY")
    ? structureDirection.includes("BULL") || structureDirection.includes("BUY")
    : structureDirection.includes("BEAR") || structureDirection.includes("SELL");
}

function getEffectiveLotSize(trade: ReplayTrade, params: StrategyParams): number {
  const entryPrice = trade.entry_price ?? 0;
  const ratio = params.use_price_ratio_scaling && params.base_reference_price > 0 && entryPrice > 0
    ? entryPrice / params.base_reference_price
    : 1;
  const baseLot = params.lot_override > 0 ? params.lot_override : getActualLotSize(trade);
  return params.use_price_ratio_scaling
    ? Math.max(0.01, Number((baseLot / ratio).toFixed(2)))
    : baseLot;
}

export function simulateThreeBrainTradeOutcome(
  trade: ReplayTrade,
  candles: ReplayCandle[],
  structures: StructureEvent[],
  params: StrategyParams = DEFAULT_STRATEGY_PARAMS,
  currentCandleTime = candles.at(-1)?.time ?? 0,
) {
  const safetyParams = {
    ...params,
    trailing_distance: 0,
    tp_trigger: 0,
    tp_ekspansi: 0,
    max_ekspansi: 0,
    enable_breakeven: false,
    force_24h_close: false,
    enable_profit_target_exit: false,
  };
  const initial = simulateTrailingSLTP(
    trade,
    candles.filter((candle) => candle.time <= (trade.entry_time ?? 0)),
    trade.entry_time ?? 0,
    structures,
    safetyParams,
  );
  const entryPrice = trade.entry_price ?? 0;
  const lotSize = getEffectiveLotSize(trade, params);
  const priceRatio = params.use_price_ratio_scaling && params.base_reference_price > 0 && entryPrice > 0
    ? entryPrice / params.base_reference_price
    : 1;
  const trailingDistance = params.trailing_distance * priceRatio;
  const breakevenTriggerPoints = params.breakeven_trigger * priceRatio * 100;
  const breakevenBuffer = params.breakeven_buffer * priceRatio;
  const direction = String(trade.type ?? "BUY").toUpperCase();
  const isBuy = direction.includes("BUY");
  const startIndex = Math.max(0, candles.findIndex((candle) => candle.time >= (trade.entry_time ?? 0)));
  let currentSL = initial.initialSL;
  let currentTP = initial.initialTP;
  const slHistory = [currentSL];
  const tpHistory = currentTP !== null ? [currentTP] : [];
  let expansionCount = 0;
  let breakevenTriggered = false;
  let maxFavorablePoints = 0;
  let maxAdversePoints = 0;
  let closeReason: "SL" | "TP" | "THREE_BRAIN_EXIT" | "THREE_BRAIN_FORCE_EXIT" | null = null;
  let exitPrice: number | null = null;
  let exitTime: number | null = null;
  let protectionActivatedTime: number | null = null;

  for (let index = startIndex; index < candles.length; index += 1) {
    const candle = candles[index];
    if (candle.time > currentCandleTime) break;

    const favorablePoints = isBuy
      ? Math.max(0, (candle.high - entryPrice) * 100)
      : Math.max(0, (entryPrice - candle.low) * 100);
    const adversePoints = isBuy
      ? Math.max(0, (entryPrice - candle.low) * 100)
      : Math.max(0, (candle.high - entryPrice) * 100);
    maxFavorablePoints = Math.max(maxFavorablePoints, Math.round(favorablePoints));
    maxAdversePoints = Math.max(maxAdversePoints, Math.round(adversePoints));

    if (isBuy ? candle.low <= currentSL : candle.high >= currentSL) {
      closeReason = "SL";
      exitPrice = currentSL;
      exitTime = candle.time;
      break;
    }
    if (currentTP !== null && (isBuy ? candle.high >= currentTP : candle.low <= currentTP)) {
      closeReason = "TP";
      exitPrice = currentTP;
      exitTime = candle.time;
      break;
    }

    const structureAligned = getStructureAlignment(direction, candle.time, structures);
    const continuation = evaluateContinuationStrength({
      direction,
      entryPrice,
      currentCandle: candle,
      previousCandles: candles.slice(Math.max(startIndex, index - 5), index),
      atr: calculateATR(candles, candle.time, params.atr_period),
      structureAligned,
    });
    const floatingNetProfit = (isBuy ? candle.close - entryPrice : entryPrice - candle.close)
      * lotSize
      * 100;
    const decision = evaluateExitTargetObserver({
      continuationStatus: continuation.status,
      continuationScore: continuation.score,
      floatingNetProfit,
      maxFavorablePoints,
      maxAdversePoints,
      protectEnabled: params.enable_breakeven,
      protectTriggerPoints: breakevenTriggerPoints,
      isBreakevenActive: breakevenTriggered,
      isTargetMaxed: params.max_ekspansi > 0 && expansionCount >= params.max_ekspansi,
      expansionCount,
      holdSeconds: Math.max(0, candle.time - (trade.entry_time ?? 0)),
      maxHoldSeconds: params.force_24h_close ? 86400 : 0,
      structureAligned,
    });

    if (decision.status === "FORCE_EXIT_ALERT" || decision.status === "EXIT_ALERT") {
      closeReason = decision.status === "FORCE_EXIT_ALERT" ? "THREE_BRAIN_FORCE_EXIT" : "THREE_BRAIN_EXIT";
      exitPrice = decision.status === "FORCE_EXIT_ALERT" ? candle.open : candle.close;
      exitTime = candle.time;
      break;
    }
    if (decision.status === "EXTEND" && currentTP !== null) {
      const canExpand = params.max_ekspansi === 0 || expansionCount < params.max_ekspansi;
      if (canExpand) {
        currentTP = isBuy ? currentTP + params.tp_ekspansi : currentTP - params.tp_ekspansi;
        expansionCount += 1;
        tpHistory.push(currentTP);
      }
    }
    if (decision.status === "PROTECT") {
      const protectedSL = isBuy
        ? entryPrice + breakevenBuffer
        : entryPrice - breakevenBuffer;
      const nextSL = isBuy ? Math.max(currentSL, protectedSL) : Math.min(currentSL, protectedSL);
      if (nextSL !== currentSL) {
        currentSL = nextSL;
        slHistory.push(currentSL);
      }
      breakevenTriggered = true;
      protectionActivatedTime = candle.time;
    }
    if (breakevenTriggered && params.enable_breakeven && trailingDistance > 0) {
      const trailingSL = isBuy
        ? candle.close - trailingDistance
        : candle.close + trailingDistance;
      const nextSL = isBuy ? Math.max(currentSL, trailingSL) : Math.min(currentSL, trailingSL);
      if (Math.abs(nextSL - currentSL) > 0.01) {
        currentSL = nextSL;
        slHistory.push(currentSL);
      }
    }
  }

  return {
    initialSL: initial.initialSL,
    initialTP: initial.initialTP,
    sl: currentSL,
    tp: currentTP,
    slHistory,
    tpHistory,
    closeReason,
    beTriggered: breakevenTriggered,
    isClosedSimulated: closeReason !== null,
    exitPriceSimulated: exitPrice,
    exitTimeSimulated: exitTime,
    protectionActivatedTime,
    expansionCount,
    maxFavorablePoints,
    maxAdversePoints,
  };
}

export function simulateThreeBrainReplayTradeOutcome(
  trade: ReplayTrade,
  candles: ReplayCandle[],
  structures: StructureEvent[],
  params: StrategyParams = DEFAULT_STRATEGY_PARAMS,
  currentCandleTime = candles.at(-1)?.time ?? 0,
) {
  const levels = simulateThreeBrainTradeOutcome(trade, candles, structures, params, currentCandleTime);
  const entryPrice = trade.entry_price ?? 0;
  const exitPrice = levels.exitPriceSimulated ?? entryPrice;
  const exitTime = levels.exitTimeSimulated;
  const lotSize = getEffectiveLotSize(trade, params);
  const entryCandle = candles.find((candle) => candle.time === trade.entry_time)
    ?? candles.find((candle) => candle.time === (trade.entry_time ?? 0) - 900);
  const spreadPoints = entryCandle?.spread != null && entryCandle.spread > 0 ? entryCandle.spread : 4;
  const spreadCost = trade.spread_cost != null && trade.spread_cost > 0
    ? trade.spread_cost
    : spreadPoints * 0.01 * lotSize * 100;
  const commission = trade.commission ?? 0;
  const swap = trade.swap != null && trade.swap !== 0
    ? trade.swap
    : calculateTradeSwap(trade.entry_time ?? 0, exitTime ?? currentCandleTime, lotSize, trade.type.toLowerCase() === "buy");
  const grossProfit = trade.type.toLowerCase() === "buy"
    ? (exitPrice - entryPrice) * lotSize * 100
    : (entryPrice - exitPrice) * lotSize * 100;
  const netProfit = levels.isClosedSimulated
    ? Number((grossProfit - spreadCost - commission + swap).toFixed(2))
    : null;

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