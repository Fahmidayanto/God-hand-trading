import {
  DEFAULT_CONTINUATION_STRENGTH_CONFIG,
  evaluateContinuationStrength,
  type ContinuationState,
  type ContinuationStrengthConfig,
} from "./continuation-strength.ts";
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

export interface ThreeBrainConfig {
  weakScoreThreshold: number;
  adverseConfirmationCandles: number;
  minimumExitNetProfit: number;
  requireAdverseStructure: boolean;
  minimumConfidence?: number;
  stateActions?: Partial<Record<ContinuationState, ThreeBrainAction>>;
  profitGivebackTrigger?: number;
  tightenLockRatio?: number;
  profitLockRatio?: number;
  protectionCooldownCandles?: number;
  continuationConfig?: Partial<ContinuationStrengthConfig>;
  otak2AtrPeriod?: number;
  managementOverrides: Partial<Pick<StrategyParams,
    | "trailing_distance"
    | "tp_trigger"
    | "tp_ekspansi"
    | "max_ekspansi"
    | "enable_breakeven"
    | "breakeven_trigger"
    | "breakeven_buffer"
    | "initial_tp_dist"
    | "sl_safety_buffer"
    | "min_sl_dist"
    | "max_sl_dist"
    | "force_24h_close"
    | "enable_profit_target_exit"
    | "profit_target_exit_usd"
    | "use_atr_sltp"
    | "atr_period"
    | "atr_sl_multiplier"
    | "atr_tp_multiplier"
  >>;
}

export const DEFAULT_THREE_BRAIN_CONFIG: ThreeBrainConfig = {
  weakScoreThreshold: 35,
  adverseConfirmationCandles: 3,
  minimumExitNetProfit: 120,
  requireAdverseStructure: true,
  minimumConfidence: 0,
  stateActions: {},
  profitGivebackTrigger: 0.3,
  tightenLockRatio: 0.4,
  profitLockRatio: 0.7,
  protectionCooldownCandles: 2,
  continuationConfig: {},
  otak2AtrPeriod: DEFAULT_STRATEGY_PARAMS.atr_period,
  managementOverrides: {},
};

export type ThreeBrainAction = "HOLD" | "EXTEND_TP" | "TIGHTEN_SL" | "LOCK_PROFIT" | "FULL_EXIT";

export function shouldUseThreeBrainExecution(
  mode: "original" | "three-brain",
  continuationObserverEnabled: boolean,
  exitTargetObserverEnabled: boolean,
): boolean {
  return mode === "three-brain" && continuationObserverEnabled && exitTargetObserverEnabled;
}

export interface ThreeBrainDiagnostics {
  stateCounts: Record<ContinuationState, number>;
  actionCounts: Record<ThreeBrainAction, number>;
  maxFloatingNetProfit: number;
  profitGiveback: number;
}

function createThreeBrainDiagnostics(): ThreeBrainDiagnostics {
  return {
    stateCounts: {
      STRONG_CONTINUATION: 0,
      HEALTHY_PULLBACK: 0,
      MOMENTUM_EXHAUSTION: 0,
      REVERSAL_CONFIRMED: 0,
      UNCERTAIN: 0,
    },
    actionCounts: {
      HOLD: 0,
      EXTEND_TP: 0,
      TIGHTEN_SL: 0,
      LOCK_PROFIT: 0,
      FULL_EXIT: 0,
    },
    maxFloatingNetProfit: 0,
    profitGiveback: 0,
  };
}

export function decideThreeBrainAction({
  state,
  confidence = 100,
  minimumConfidence = 0,
  protectedPosition,
  floatingNetProfit,
  profitGivebackRatio,
  profitGivebackTrigger = 0.3,
  minimumExitNetProfit,
  stateActions = {},
}: {
  state: ContinuationState;
  confidence?: number;
  minimumConfidence?: number;
  protectedPosition: boolean;
  floatingNetProfit: number;
  profitGivebackRatio: number;
  profitGivebackTrigger?: number;
  minimumExitNetProfit: number;
  stateActions?: Partial<Record<ContinuationState, ThreeBrainAction>>;
}): ThreeBrainAction {
  if (confidence < minimumConfidence) return "HOLD";
  const configuredAction = stateActions[state];
  if (configuredAction) {
    if (!protectedPosition && configuredAction !== "HOLD" && configuredAction !== "EXTEND_TP") return "HOLD";
    if (configuredAction === "FULL_EXIT" && floatingNetProfit < minimumExitNetProfit) return "HOLD";
    return configuredAction;
  }
  if (state === "STRONG_CONTINUATION") return "EXTEND_TP";
  if (state === "HEALTHY_PULLBACK" || state === "UNCERTAIN" || !protectedPosition) return "HOLD";
  if (state === "REVERSAL_CONFIRMED" && floatingNetProfit >= minimumExitNetProfit) return "FULL_EXIT";
  if (state === "MOMENTUM_EXHAUSTION" && profitGivebackRatio >= profitGivebackTrigger) return "LOCK_PROFIT";
  if (state === "MOMENTUM_EXHAUSTION") return "TIGHTEN_SL";
  return "HOLD";
}

export function getThreeBrainConfigFromSearch(search: string): ThreeBrainConfig {
  const params = new URLSearchParams(search);
  const readNumber = (key: string, fallback: number) => {
    const rawValue = params.get(key);
    if (rawValue === null || rawValue.trim() === "") return fallback;
    const value = Number(rawValue);
    return Number.isFinite(value) ? value : fallback;
  };

  return {
    weakScoreThreshold: readNumber("tbWeak", DEFAULT_THREE_BRAIN_CONFIG.weakScoreThreshold),
    adverseConfirmationCandles: Math.max(1, Math.round(readNumber("tbConfirm", DEFAULT_THREE_BRAIN_CONFIG.adverseConfirmationCandles))),
    minimumExitNetProfit: Math.max(0, readNumber("tbProfit", DEFAULT_THREE_BRAIN_CONFIG.minimumExitNetProfit)),
    requireAdverseStructure: params.get("tbAdverseStructure") === null
      ? DEFAULT_THREE_BRAIN_CONFIG.requireAdverseStructure
      : params.get("tbAdverseStructure") !== "0",
    managementOverrides: DEFAULT_THREE_BRAIN_CONFIG.managementOverrides,
  };
}

function getLatestStructure(
  candleTime: number,
  structures: StructureEvent[],
): StructureEvent | null {
  return [...structures]
    .reverse()
    .find((event) => event.time <= candleTime && (!event.timeframe || event.timeframe.toUpperCase() === "M15")) ?? null;
}

function getStructureAlignment(direction: string, latestStructure: StructureEvent | null): boolean {
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

export function getThreeBrainPreviousCandles<T>(candles: T[], evaluationIndex: number, lookback = 20): T[] {
  return candles.slice(Math.max(0, evaluationIndex - Math.max(1, Math.round(lookback))), evaluationIndex);
}

export function simulateThreeBrainTradeOutcome(
  trade: ReplayTrade,
  candles: ReplayCandle[],
  structures: StructureEvent[],
  params: StrategyParams = DEFAULT_STRATEGY_PARAMS,
  currentCandleTime = candles.at(-1)?.time ?? 0,
  config: ThreeBrainConfig = DEFAULT_THREE_BRAIN_CONFIG,
) {
  const managementParams = { ...params, ...config.managementOverrides };
  const baseline = simulateTrailingSLTP(trade, candles, currentCandleTime, structures, managementParams);
  if (!baseline.isClosedSimulated || baseline.exitTimeSimulated == null) return baseline;

  const entryPrice = trade.entry_price ?? 0;
  const lotSize = getEffectiveLotSize(trade, params);
  const priceRatio = params.use_price_ratio_scaling && params.base_reference_price > 0 && entryPrice > 0
    ? entryPrice / params.base_reference_price
    : 1;
  const breakevenTrigger = managementParams.breakeven_trigger * priceRatio;
  const direction = String(trade.type ?? "BUY").toUpperCase();
  const isBuy = direction.includes("BUY");
  const startIndex = Math.max(0, candles.findIndex((candle) => candle.time >= (trade.entry_time ?? 0)));
  let adverseReversalConfirmations = 0;
  let adaptiveStop = baseline.initialSL;
  let lastProtectionActionIndex = -2;
  const diagnostics = createThreeBrainDiagnostics();
  const continuationConfig = config.continuationConfig ?? {};
  const historyLookback = Math.max(
    20,
    continuationConfig.momentumLookback ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.momentumLookback,
    continuationConfig.emaSlopeLookback ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.emaSlopeLookback,
    continuationConfig.volumeLookback ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.volumeLookback,
  );
  const otak2AtrPeriod = Math.max(1, Math.round(config.otak2AtrPeriod ?? managementParams.atr_period));

  for (let index = startIndex; index < candles.length; index += 1) {
    const candle = candles[index];
    if (candle.time >= baseline.exitTimeSimulated) break;

    const adaptiveStopHit = isBuy ? candle.low <= adaptiveStop : candle.high >= adaptiveStop;
    if (adaptiveStopHit && adaptiveStop !== baseline.initialSL) {
      return {
        ...baseline,
        sl: adaptiveStop,
        slHistory: [...baseline.slHistory, adaptiveStop],
        closeReason: "THREE_BRAIN_LOCK_EXIT",
        isClosedSimulated: true,
        exitPriceSimulated: adaptiveStop,
        exitTimeSimulated: candle.time,
        threeBrainDiagnostics: diagnostics,
      };
    }

    const latestStructure = getLatestStructure(candle.time, structures);
    const structureAligned = getStructureAlignment(direction, latestStructure);
    const continuation = evaluateContinuationStrength({
      direction,
      entryPrice,
      currentCandle: candle,
      previousCandles: getThreeBrainPreviousCandles(candles, index, historyLookback),
      atr: calculateATR(candles, candle.time, otak2AtrPeriod),
      structureAligned,
      structure: latestStructure,
    }, continuationConfig);
    const floatingNetProfit = (isBuy ? candle.close - entryPrice : entryPrice - candle.close)
      * lotSize
      * 100;
    diagnostics.maxFloatingNetProfit = Math.max(diagnostics.maxFloatingNetProfit, floatingNetProfit);
    diagnostics.profitGiveback = Math.max(0, diagnostics.maxFloatingNetProfit - floatingNetProfit);
    const profitGivebackRatio = diagnostics.maxFloatingNetProfit > 0
      ? diagnostics.profitGiveback / diagnostics.maxFloatingNetProfit
      : 0;
    const protectionReached = (isBuy ? candle.high - entryPrice : entryPrice - candle.low) >= breakevenTrigger;
    const isWeak = continuation.score < config.weakScoreThreshold;
    const reversalEvidence = continuation.state === "REVERSAL_CONFIRMED" || isWeak;
    const isAdverseReversal = reversalEvidence && (!config.requireAdverseStructure || !structureAligned);
    adverseReversalConfirmations = isAdverseReversal ? adverseReversalConfirmations + 1 : 0;
    const confirmedState = adverseReversalConfirmations >= config.adverseConfirmationCandles
      ? "REVERSAL_CONFIRMED"
      : continuation.state === "REVERSAL_CONFIRMED"
        ? "MOMENTUM_EXHAUSTION"
        : continuation.state;
    diagnostics.stateCounts[confirmedState] += 1;
    let action = decideThreeBrainAction({
      state: confirmedState,
      confidence: continuation.confidence,
      minimumConfidence: config.minimumConfidence ?? DEFAULT_THREE_BRAIN_CONFIG.minimumConfidence,
      protectedPosition: protectionReached,
      floatingNetProfit,
      profitGivebackRatio,
      profitGivebackTrigger: config.profitGivebackTrigger ?? DEFAULT_THREE_BRAIN_CONFIG.profitGivebackTrigger,
      minimumExitNetProfit: config.minimumExitNetProfit,
      stateActions: config.stateActions,
    });
    const protectionCooldownCandles = Math.max(0, Math.round(
      config.protectionCooldownCandles ?? DEFAULT_THREE_BRAIN_CONFIG.protectionCooldownCandles ?? 2,
    ));
    if ((action === "TIGHTEN_SL" || action === "LOCK_PROFIT")
      && index - lastProtectionActionIndex < protectionCooldownCandles) {
      action = "HOLD";
    }
    diagnostics.actionCounts[action] += 1;

    if (action === "TIGHTEN_SL" || action === "LOCK_PROFIT") {
      const lockedProfitRatio = action === "LOCK_PROFIT"
        ? config.profitLockRatio ?? DEFAULT_THREE_BRAIN_CONFIG.profitLockRatio ?? 0.7
        : config.tightenLockRatio ?? DEFAULT_THREE_BRAIN_CONFIG.tightenLockRatio ?? 0.4;
      const lockedProfitDistance = diagnostics.maxFloatingNetProfit * lockedProfitRatio / (lotSize * 100);
      const nextStop = isBuy ? entryPrice + lockedProfitDistance : entryPrice - lockedProfitDistance;
      adaptiveStop = isBuy ? Math.max(adaptiveStop, nextStop) : Math.min(adaptiveStop, nextStop);
      lastProtectionActionIndex = index;
    }

    if (action === "FULL_EXIT") {
      return {
        ...baseline,
        closeReason: "THREE_BRAIN_EXIT",
        isClosedSimulated: true,
        exitPriceSimulated: candle.close,
        exitTimeSimulated: candle.time,
        threeBrainDiagnostics: diagnostics,
      };
    }
  }

  return { ...baseline, threeBrainDiagnostics: diagnostics };
}

export function simulateThreeBrainReplayTradeOutcome(
  trade: ReplayTrade,
  candles: ReplayCandle[],
  structures: StructureEvent[],
  params: StrategyParams = DEFAULT_STRATEGY_PARAMS,
  currentCandleTime = candles.at(-1)?.time ?? 0,
  config: ThreeBrainConfig = DEFAULT_THREE_BRAIN_CONFIG,
) {
  const levels = simulateThreeBrainTradeOutcome(trade, candles, structures, params, currentCandleTime, config);
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