import { writeFile } from "node:fs/promises";

import {
  DEFAULT_THREE_BRAIN_CONFIG,
  simulateThreeBrainReplayTradeOutcome,
  type ThreeBrainAction,
  type ThreeBrainConfig,
  type ThreeBrainDiagnostics,
} from "../ValueCell_MT5/frontend/src/app/mt5/three-brain-engine.ts";
import type { ContinuationState } from "../ValueCell_MT5/frontend/src/app/mt5/continuation-strength.ts";
import {
  DEFAULT_STRATEGY_PARAMS,
  DEFAULT_ENTRY_FILTER_PARAMS,
  calculateTradeSwap,
  getActualLotSize,
  getProcessedReplayTrades,
  simulateReplayTradeOutcome,
  type ReplayData,
  type ReplayTrade,
} from "../ValueCell_MT5/frontend/src/app/mt5/replay-engine.ts";

const API_BASE = "http://localhost:8000/api/v1";
const TRAIN_YEARS = [2019, 2020, 2021, 2022, 2023, 2024];
const VALIDATION_YEAR = 2025;
const HOLDOUT_YEAR = 2026;
const budgetArg = process.argv.find((value) => value.startsWith("--budget="));
const BUDGET = Math.max(1, Number(budgetArg?.split("=")[1] ?? 2000));
const smokeMode = process.argv.includes("--smoke");
const refineMode = process.argv.includes("--refine");

interface YearData {
  year: number;
  data: ReplayData;
  executedTrades: ReplayTrade[];
  baseline: Metrics;
}

interface Metrics {
  netProfit: number;
  grossProfit: number;
  grossLoss: number;
  wins: number;
  losses: number;
  maxDrawdown: number;
  profitFactor: number;
  threeBrainExits: number;
  threeBrainLockExits: number;
  stateCounts: Record<ContinuationState, number>;
  actionCounts: Record<ThreeBrainAction, number>;
  profitGiveback: number;
}

interface CandidateResult {
  id: number;
  config: ThreeBrainConfig;
  train: Metrics;
  trainByYear: Record<number, Metrics>;
  trainDelta: number;
  positiveTrainYears: number;
  worstTrainYearDelta: number;
  score: number;
  eligible: boolean;
  validation?: Metrics;
  validationDelta?: number;
  holdout?: Metrics;
  holdoutDelta?: number;
  january2026?: Metrics;
  january2026Delta?: number;
}

function mulberry32(seed: number) {
  return () => {
    let value = seed += 0x6d2b79f5;
    value = Math.imul(value ^ value >>> 15, value | 1);
    value ^= value + Math.imul(value ^ value >>> 7, value | 61);
    return ((value ^ value >>> 14) >>> 0) / 4294967296;
  };
}

const random = mulberry32(20260901);
const pick = <T>(values: T[]): T => values[Math.floor(random() * values.length)];

function createCandidate(): ThreeBrainConfig {
  return {
    weakScoreThreshold: pick(refineMode ? [25, 30, 35, 40] : [20, 25, 30, 35, 40, 45, 50]),
    adverseConfirmationCandles: pick(refineMode ? [2, 3, 4, 5] : [1, 2, 3, 4, 5, 6]),
    minimumExitNetProfit: pick(refineMode ? [75, 100, 120, 150] : [0, 25, 50, 75, 100, 120, 150, 200]),
    requireAdverseStructure: pick([false, true]),
    minimumConfidence: pick([0, 20, 40, 60, 80]),
    profitGivebackTrigger: pick([0.1, 0.2, 0.3, 0.4, 0.5]),
    tightenLockRatio: pick([0.2, 0.3, 0.4, 0.5, 0.6]),
    profitLockRatio: pick([0.5, 0.6, 0.7, 0.8, 0.9]),
    protectionCooldownCandles: pick([0, 1, 2, 3, 4, 6]),
    stateActions: {
      MOMENTUM_EXHAUSTION: pick(["HOLD", "TIGHTEN_SL", "LOCK_PROFIT"]),
      REVERSAL_CONFIRMED: pick(["TIGHTEN_SL", "LOCK_PROFIT", "FULL_EXIT"]),
    },
    otak2AtrPeriod: pick([7, 10, 14, 20, 28]),
    continuationConfig: {
      bosFollowThroughAtr: pick([0.25, 0.5, 0.75, 1, 1.5]),
      maximumStructureAgeCandles: pick([null, 2, 4, 6, 8, 12]),
      momentumLookback: pick([1, 2, 3, 4, 6, 8, 12, 20]),
      directionalMode: pick(["single", "average", "majority", "strict", "smoothed"]),
      directionalLookback: pick([1, 2, 3, 4, 6]),
      directionalBodyThreshold: pick([0.5, 0.6, 0.7, 0.8]),
      directionalCloseThreshold: pick([0.65, 0.75, 0.8, 0.9]),
      directionalRangeAtrThreshold: pick([0.5, 0.75, 1, 1.5]),
      directionalWeight: pick([5, 10, 15, 20]),
      emaSlopeLookback: pick([1, 2, 3, 4, 6, 8, 12, 20]),
      emaSlopeMethod: pick(["endpoint", "average", "confirmation", "atr-normalized"]),
      emaMinimumDistanceAtr: pick([0, 0.1, 0.25, 0.5]),
      emaWeight: pick([5, 10, 15]),
      volumeLookback: pick([5, 10, 14, 20, 30, 50]),
      volumeMethod: pick(["average", "median", "ema", "trimmed-mean"]),
      volumeLowThreshold: pick([0.5, 0.7, 0.8, 0.9]),
      volumeStrongThreshold: pick([1.1, 1.2, 1.3, 1.5]),
      volumeImpulseThreshold: pick([1.4, 1.6, 1.8, 2]),
      volumeMode: pick(["independent", "directional", "penalty", "confirmation"]),
      volumeWeight: pick([5, 10, 15, 20]),
    },
    managementOverrides: {},
  };
}

async function fetchYear(year: number): Promise<YearData> {
  const endMonth = year === 2026 ? 9 : 12;
  const fetchTimeframe = async (timeframe: string) => {
    const url = `${API_BASE}/trading/replay?year_from=${year}&month_from=1&year_to=${year}&month_to=${endMonth}&timeframe=${timeframe}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${url}: ${await response.text()}`);
    return response.json() as Promise<ReplayData>;
  };
  const [data, h1Data, h4Data] = await Promise.all([fetchTimeframe("M15"), fetchTimeframe("H1"), fetchTimeframe("H4")]);
  const executedTrades = getProcessedReplayTrades(
    data,
    data.structures,
    DEFAULT_ENTRY_FILTER_PARAMS,
    data.candles,
    h1Data.candles,
    h4Data.candles,
  ).executedTrades;
  const baseline = evaluateTrades(data, executedTrades, null);
  return { year, data, executedTrades, baseline };
}

function createStateCounts(): Record<ContinuationState, number> {
  return {
    STRONG_CONTINUATION: 0,
    HEALTHY_PULLBACK: 0,
    MOMENTUM_EXHAUSTION: 0,
    REVERSAL_CONFIRMED: 0,
    UNCERTAIN: 0,
  };
}

function createActionCounts(): Record<ThreeBrainAction, number> {
  return { HOLD: 0, EXTEND_TP: 0, TIGHTEN_SL: 0, LOCK_PROFIT: 0, FULL_EXIT: 0 };
}

function addDiagnostics(
  stateCounts: Record<ContinuationState, number>,
  actionCounts: Record<ThreeBrainAction, number>,
  diagnostics: ThreeBrainDiagnostics | undefined,
) {
  if (!diagnostics) return;
  for (const state of Object.keys(stateCounts) as ContinuationState[]) stateCounts[state] += diagnostics.stateCounts[state];
  for (const action of Object.keys(actionCounts) as ThreeBrainAction[]) actionCounts[action] += diagnostics.actionCounts[action];
}

function calculateMetrics(
  profits: number[],
  threeBrainExits: number,
  threeBrainLockExits = 0,
  stateCounts = createStateCounts(),
  actionCounts = createActionCounts(),
  profitGiveback = 0,
): Metrics {
  let equity = 0;
  let peak = 0;
  let maxDrawdown = 0;
  let grossProfit = 0;
  let grossLoss = 0;
  for (const profit of profits) {
    equity += profit;
    peak = Math.max(peak, equity);
    maxDrawdown = Math.max(maxDrawdown, peak - equity);
    if (profit > 0) grossProfit += profit;
    if (profit < 0) grossLoss += Math.abs(profit);
  }
  return {
    netProfit: Number(equity.toFixed(2)),
    grossProfit: Number(grossProfit.toFixed(2)),
    grossLoss: Number(grossLoss.toFixed(2)),
    wins: profits.filter((profit) => profit > 0).length,
    losses: profits.filter((profit) => profit < 0).length,
    maxDrawdown: Number(maxDrawdown.toFixed(2)),
    profitFactor: grossLoss > 0 ? Number((grossProfit / grossLoss).toFixed(3)) : grossProfit > 0 ? 999 : 0,
    threeBrainExits,
    threeBrainLockExits,
    stateCounts,
    actionCounts,
    profitGiveback: Number(profitGiveback.toFixed(2)),
  };
}

function evaluateTrades(data: ReplayData, trades: ReplayTrade[], config: ThreeBrainConfig | null): Metrics {
  const lastTime = data.candles.at(-1)?.time ?? 0;
  const lastCandle = data.candles.at(-1);
  const profits: number[] = [];
  let threeBrainExits = 0;
  let threeBrainLockExits = 0;
  let profitGiveback = 0;
  const stateCounts = createStateCounts();
  const actionCounts = createActionCounts();
  for (const trade of trades) {
    const outcome = config
      ? simulateThreeBrainReplayTradeOutcome(trade, data.candles, data.structures, DEFAULT_STRATEGY_PARAMS, lastTime, config)
      : simulateReplayTradeOutcome(trade, data.candles, data.structures, DEFAULT_STRATEGY_PARAMS, lastTime);
    if (outcome.netProfit !== null) {
      profits.push(outcome.netProfit);
    } else if (lastCandle && trade.entry_price !== null) {
      const ratio = DEFAULT_STRATEGY_PARAMS.use_price_ratio_scaling && DEFAULT_STRATEGY_PARAMS.base_reference_price > 0
        ? trade.entry_price / DEFAULT_STRATEGY_PARAMS.base_reference_price
        : 1;
      const baseLot = DEFAULT_STRATEGY_PARAMS.lot_override > 0
        ? DEFAULT_STRATEGY_PARAMS.lot_override
        : getActualLotSize(trade);
      const lotSize = DEFAULT_STRATEGY_PARAMS.use_price_ratio_scaling
        ? Math.max(0.01, Number((baseLot / ratio).toFixed(2)))
        : baseLot;
      const entryCandle = data.candles.find((candle) => candle.time === trade.entry_time)
        ?? data.candles.find((candle) => candle.time === (trade.entry_time ?? 0) - 900);
      const spreadPoints = entryCandle?.spread != null && entryCandle.spread > 0 ? entryCandle.spread : 4;
      const spreadCost = trade.spread_cost != null && trade.spread_cost > 0
        ? trade.spread_cost
        : spreadPoints * 0.01 * lotSize * 100;
      const swap = trade.swap != null && trade.swap !== 0
        ? trade.swap
        : calculateTradeSwap(trade.entry_time ?? 0, lastTime, lotSize, trade.type.toLowerCase() === "buy");
      const grossProfit = trade.type.toLowerCase() === "buy"
        ? (lastCandle.close - trade.entry_price) * lotSize * 100
        : (trade.entry_price - lastCandle.close) * lotSize * 100;
      profits.push(Number((grossProfit - spreadCost + swap).toFixed(2)));
    }
    if (outcome.closeReason === "THREE_BRAIN_EXIT") threeBrainExits += 1;
    if (outcome.closeReason === "THREE_BRAIN_LOCK_EXIT") threeBrainLockExits += 1;
    if ("threeBrainDiagnostics" in outcome) {
      addDiagnostics(stateCounts, actionCounts, outcome.threeBrainDiagnostics);
      profitGiveback += outcome.threeBrainDiagnostics?.profitGiveback ?? 0;
    }
  }
  return calculateMetrics(profits, threeBrainExits, threeBrainLockExits, stateCounts, actionCounts, profitGiveback);
}

function combineMetrics(metrics: Metrics[]): Metrics {
  const grossProfit = metrics.reduce((sum, value) => sum + value.grossProfit, 0);
  const grossLoss = metrics.reduce((sum, value) => sum + value.grossLoss, 0);
  return {
    netProfit: Number(metrics.reduce((sum, value) => sum + value.netProfit, 0).toFixed(2)),
    grossProfit: Number(grossProfit.toFixed(2)),
    grossLoss: Number(grossLoss.toFixed(2)),
    wins: metrics.reduce((sum, value) => sum + value.wins, 0),
    losses: metrics.reduce((sum, value) => sum + value.losses, 0),
    maxDrawdown: Math.max(...metrics.map((value) => value.maxDrawdown)),
    profitFactor: grossLoss > 0 ? Number((grossProfit / grossLoss).toFixed(3)) : grossProfit > 0 ? 999 : 0,
    threeBrainExits: metrics.reduce((sum, value) => sum + value.threeBrainExits, 0),
    threeBrainLockExits: metrics.reduce((sum, value) => sum + value.threeBrainLockExits, 0),
    stateCounts: Object.fromEntries((Object.keys(createStateCounts()) as ContinuationState[]).map((state) => [
      state,
      metrics.reduce((sum, value) => sum + value.stateCounts[state], 0),
    ])) as Record<ContinuationState, number>,
    actionCounts: Object.fromEntries((Object.keys(createActionCounts()) as ThreeBrainAction[]).map((action) => [
      action,
      metrics.reduce((sum, value) => sum + value.actionCounts[action], 0),
    ])) as Record<ThreeBrainAction, number>,
    profitGiveback: Number(metrics.reduce((sum, value) => sum + value.profitGiveback, 0).toFixed(2)),
  };
}

function evaluateCandidate(id: number, config: ThreeBrainConfig, years: YearData[]): CandidateResult {
  const trainByYear = Object.fromEntries(years.map((year) => [year.year, evaluateTrades(year.data, year.executedTrades, config)]));
  const train = combineMetrics(Object.values(trainByYear));
  const deltas = years.map((year) => trainByYear[year.year].netProfit - year.baseline.netProfit);
  const trainDelta = Number(deltas.reduce((sum, value) => sum + value, 0).toFixed(2));
  const positiveTrainYears = deltas.filter((value) => value > 0).length;
  const worstTrainYearDelta = Number(Math.min(...deltas).toFixed(2));
  const eligible = trainDelta > 0
    && positiveTrainYears >= 4
    && worstTrainYearDelta >= -500
    && train.maxDrawdown <= DEFAULT_STRATEGY_PARAMS.initial_balance * 1.5;
  const score = eligible
    ? Number((trainDelta + positiveTrainYears * 250 + worstTrainYearDelta * 1.5 - train.maxDrawdown * 0.25).toFixed(2))
    : Number.NEGATIVE_INFINITY;
  return { id, config, train, trainByYear, trainDelta, positiveTrainYears, worstTrainYearDelta, score, eligible };
}

const years = await Promise.all([...TRAIN_YEARS, VALIDATION_YEAR, HOLDOUT_YEAR].map(fetchYear));
const fetchJanuaryTimeframe = async (timeframe: string) => {
  const response = await fetch(`${API_BASE}/trading/replay?year_from=2026&month_from=1&year_to=2026&month_to=1&timeframe=${timeframe}`);
  if (!response.ok) throw new Error(`January ${timeframe} parity request failed: ${response.status}`);
  return response.json() as Promise<ReplayData>;
};
const [january2026, januaryH1, januaryH4] = await Promise.all([
  fetchJanuaryTimeframe("M15"),
  fetchJanuaryTimeframe("H1"),
  fetchJanuaryTimeframe("H4"),
]);
const januaryTrades = getProcessedReplayTrades(
  january2026,
  january2026.structures,
  DEFAULT_ENTRY_FILTER_PARAMS,
  january2026.candles,
  januaryH1.candles,
  januaryH4.candles,
).executedTrades;
const januaryBaseline = evaluateTrades(
  january2026,
  januaryTrades,
  null,
);
if (januaryBaseline.netProfit !== 1303.22) {
  throw new Error(`January baseline parity failed: expected 1303.22, received ${januaryBaseline.netProfit}`);
}
const trainingData = years.filter((year) => TRAIN_YEARS.includes(year.year));
const validationData = years.find((year) => year.year === VALIDATION_YEAR)!;
const holdoutData = years.find((year) => year.year === HOLDOUT_YEAR)!;
const candidateMap = new Map<string, ThreeBrainConfig>();
candidateMap.set(JSON.stringify(DEFAULT_THREE_BRAIN_CONFIG), DEFAULT_THREE_BRAIN_CONFIG);
const requestedCandidateCount = smokeMode ? 5 : BUDGET;
let candidateAttempts = 0;
while (candidateMap.size < requestedCandidateCount && candidateAttempts < requestedCandidateCount * 20) {
  const candidate = createCandidate();
  candidateMap.set(JSON.stringify(candidate), candidate);
  candidateAttempts += 1;
}
const candidates = [...candidateMap.values()];
const results = candidates.map((config, index) => evaluateCandidate(index, config, trainingData));
results.sort((left, right) => right.score - left.score);

const finalists = results.filter((result) => result.eligible).slice(0, smokeMode ? 5 : 50);
for (const finalist of finalists) {
  finalist.validation = evaluateTrades(validationData.data, validationData.executedTrades, finalist.config);
  finalist.validationDelta = Number((finalist.validation.netProfit - validationData.baseline.netProfit).toFixed(2));
}

const validated = finalists
  .filter((result) => (result.validationDelta ?? Number.NEGATIVE_INFINITY) > 0
    && (result.validation?.maxDrawdown ?? Number.POSITIVE_INFINITY) <= DEFAULT_STRATEGY_PARAMS.initial_balance * 1.5)
  .sort((left, right) => (right.validationDelta ?? 0) - (left.validationDelta ?? 0) || right.score - left.score)
  .slice(0, smokeMode ? 5 : 10);

for (const finalist of validated) {
  finalist.holdout = evaluateTrades(holdoutData.data, holdoutData.executedTrades, finalist.config);
  finalist.holdoutDelta = Number((finalist.holdout.netProfit - holdoutData.baseline.netProfit).toFixed(2));
  finalist.january2026 = evaluateTrades(january2026, januaryTrades, finalist.config);
  finalist.january2026Delta = Number((finalist.january2026.netProfit - januaryBaseline.netProfit).toFixed(2));
}

const report = {
  generatedAt: new Date().toISOString(),
  seed: 20260901,
  budget: candidates.length,
  split: { train: TRAIN_YEARS, validation: VALIDATION_YEAR, holdout: HOLDOUT_YEAR },
  parity: { january2026Baseline: januaryBaseline.netProfit, expected: 1303.22 },
  baseline: Object.fromEntries(years.map((year) => [year.year, { trades: year.executedTrades.length, ...year.baseline }])),
  topTraining: results.slice(0, 20),
  validated,
  bestEvidenceBacked: validated.find((result) =>
    (result.holdoutDelta ?? Number.NEGATIVE_INFINITY) > 0
    && (result.january2026Delta ?? Number.NEGATIVE_INFINITY) > 0
    && (result.holdout?.maxDrawdown ?? Number.POSITIVE_INFINITY) <= DEFAULT_STRATEGY_PARAMS.initial_balance * 1.5
  ) ?? null,
};

const outputPath = new URL("./three-brain-optimization-results.json", import.meta.url);
await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify({
  budget: report.budget,
  baseline: report.baseline,
  validatedCount: validated.length,
  bestEvidenceBacked: report.bestEvidenceBacked,
  output: outputPath.pathname,
}, null, 2));