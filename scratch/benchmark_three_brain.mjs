import { writeFile } from "node:fs/promises";

import {
  DEFAULT_ENTRY_FILTER_PARAMS,
  DEFAULT_STRATEGY_PARAMS,
  calculateATR,
  calculateTradeSwap,
  getProcessedReplayTrades,
  getActualLotSize,
  simulateReplayTradeOutcome,
} from "../ValueCell_MT5/frontend/src/app/mt5/replay-engine.ts";
import { evaluateContinuationStrength } from "../ValueCell_MT5/frontend/src/app/mt5/continuation-strength.ts";
import { simulateThreeBrainReplayTradeOutcome } from "../ValueCell_MT5/frontend/src/app/mt5/three-brain-engine.ts";

const API_BASE_URL = "http://localhost:8000/api/v1/trading/replay?year_from=2026&month_from=1&year_to=2026&month_to=8";
async function fetchReplayData(timeframe) {
  const response = await fetch(`${API_BASE_URL}&timeframe=${timeframe}`);
  if (!response.ok) throw new Error(`Replay API ${response.status}: ${await response.text()}`);
  return response.json();
}

const [replayData, h1Data, h4Data] = await Promise.all([
  fetchReplayData("M15"),
  fetchReplayData("H1"),
  fetchReplayData("H4"),
]);

const { executedTrades } = getProcessedReplayTrades(
  replayData,
  replayData.structures,
  DEFAULT_ENTRY_FILTER_PARAMS,
  replayData.candles,
  h1Data.candles,
  h4Data.candles,
);
const lastCandleTime = replayData.candles.at(-1)?.time ?? 0;

function aggregate(outcomes) {
  const closed = outcomes.filter((outcome) => outcome.isClosed);
  const netProfit = closed.reduce((total, outcome) => total + (outcome.netProfit ?? 0), 0);
  const wins = closed.filter((outcome) => (outcome.netProfit ?? 0) > 0).length;
  const losses = closed.filter((outcome) => (outcome.netProfit ?? 0) < 0).length;
  return {
    netProfit: Number(netProfit.toFixed(2)),
    wins,
    losses,
    winRate: wins + losses ? Number(((wins / (wins + losses)) * 100).toFixed(1)) : 0,
    closed: closed.length,
    brainExitCount: closed.filter((outcome) => outcome.closeReason === "THREE_BRAIN_EXIT").length,
  };
}

function runBaseline(params) {
  return aggregate(executedTrades.map((trade) => simulateReplayTradeOutcome(
    trade,
    replayData.candles,
    replayData.structures,
    params,
    lastCandleTime,
  )));
}

function runThreeBrain(params) {
  return aggregate(executedTrades.map((trade) => simulateThreeBrainReplayTradeOutcome(
    trade,
    replayData.candles,
    replayData.structures,
    params,
    lastCandleTime,
  )));
}

function getStructureAlignment(direction, candleTime) {
  const latestStructure = [...replayData.structures]
    .reverse()
    .find((event) => event.time <= candleTime && (!event.timeframe || event.timeframe.toUpperCase() === "M15"));
  const structureDirection = `${latestStructure?.direction ?? ""} ${latestStructure?.type ?? ""}`.toUpperCase();
  return direction.includes("BUY")
    ? structureDirection.includes("BULL") || structureDirection.includes("BUY")
    : structureDirection.includes("BEAR") || structureDirection.includes("SELL");
}

function getEffectiveLotSize(trade, params) {
  const entryPrice = trade.entry_price ?? 0;
  const ratio = params.use_price_ratio_scaling && params.base_reference_price > 0 && entryPrice > 0
    ? entryPrice / params.base_reference_price
    : 1;
  const baseLot = params.lot_override > 0 ? params.lot_override : getActualLotSize(trade);
  return params.use_price_ratio_scaling ? Math.max(0.01, Number((baseLot / ratio).toFixed(2))) : baseLot;
}

function calculateNetProfit(trade, exitPrice, exitTime, params) {
  const entryPrice = trade.entry_price ?? 0;
  const lotSize = getEffectiveLotSize(trade, params);
  const entryCandle = replayData.candles.find((candle) => candle.time === trade.entry_time)
    ?? replayData.candles.find((candle) => candle.time === (trade.entry_time ?? 0) - 900);
  const spreadPoints = entryCandle?.spread != null && entryCandle.spread > 0 ? entryCandle.spread : 4;
  const spreadCost = trade.spread_cost != null && trade.spread_cost > 0
    ? trade.spread_cost
    : spreadPoints * 0.01 * lotSize * 100;
  const commission = trade.commission ?? 0;
  const swap = trade.swap != null && trade.swap !== 0
    ? trade.swap
    : calculateTradeSwap(trade.entry_time ?? 0, exitTime, lotSize, trade.type.toLowerCase() === "buy");
  const grossProfit = trade.type.toLowerCase() === "buy"
    ? (exitPrice - entryPrice) * lotSize * 100
    : (entryPrice - exitPrice) * lotSize * 100;
  return Number((grossProfit - spreadCost - commission + swap).toFixed(2));
}

function runGuardedExitPolicy(params, confirmationsRequired, minimumProfit) {
  const outcomes = executedTrades.map((trade) => {
    const baselineOutcome = simulateReplayTradeOutcome(
      trade,
      replayData.candles,
      replayData.structures,
      params,
      lastCandleTime,
    );
    if (!baselineOutcome.isClosed || baselineOutcome.exitTime == null) return baselineOutcome;

    const entryTime = trade.entry_time ?? 0;
    const entryPrice = trade.entry_price ?? 0;
    const direction = String(trade.type ?? "BUY").toUpperCase();
    const isBuy = direction.includes("BUY");
    const ratio = params.use_price_ratio_scaling && params.base_reference_price > 0 && entryPrice > 0
      ? entryPrice / params.base_reference_price
      : 1;
    const breakevenTrigger = params.breakeven_trigger * ratio;
    const lotSize = getEffectiveLotSize(trade, params);
    const startIndex = replayData.candles.findIndex((candle) => candle.time >= entryTime);
    let adverseConfirmations = 0;
    let protectionReached = false;

    for (let index = Math.max(0, startIndex); index < replayData.candles.length; index += 1) {
      const candle = replayData.candles[index];
      if (candle.time >= baselineOutcome.exitTime) break;

      const favorableMovement = isBuy ? candle.high - entryPrice : entryPrice - candle.low;
      protectionReached ||= params.enable_breakeven && favorableMovement >= breakevenTrigger;
      const structureAligned = getStructureAlignment(direction, candle.time);
      const continuation = evaluateContinuationStrength({
        direction,
        entryPrice,
        currentCandle: candle,
        previousCandles: replayData.candles.slice(Math.max(0, index - 5), index),
        atr: calculateATR(replayData.candles, candle.time, params.atr_period),
        structureAligned,
      });
      adverseConfirmations = continuation.status === "WEAK" && !structureAligned
        ? adverseConfirmations + 1
        : 0;
      const floatingNetProfit = (isBuy ? candle.close - entryPrice : entryPrice - candle.close) * lotSize * 100;
      if (protectionReached && adverseConfirmations >= confirmationsRequired && floatingNetProfit >= minimumProfit) {
        return {
          ...baselineOutcome,
          closeReason: "THREE_BRAIN_EXIT",
          exitPrice: candle.close,
          exitTime: candle.time,
          netProfit: calculateNetProfit(trade, candle.close, candle.time, params),
        };
      }
    }
    return baselineOutcome;
  });
  return aggregate(outcomes);
}

const baseParams = { ...DEFAULT_STRATEGY_PARAMS };
const baseline = runBaseline(baseParams);
const scenarios = [];

for (const enableBreakeven of [false, true]) {
  for (const trailingDistance of [15, 20, 30, 40]) {
    for (const tpTrigger of [5, 10, 15]) {
      for (const tpEkspansi of [10, 20, 30]) {
        const params = {
          ...baseParams,
          enable_breakeven: enableBreakeven,
          trailing_distance: trailingDistance,
          tp_trigger: tpTrigger,
          tp_ekspansi: tpEkspansi,
        };
        const result = runThreeBrain(params);
        const scenarioBaseline = runBaseline(params);
        scenarios.push({
          name: `3B BE:${enableBreakeven ? "on" : "off"} trail:${trailingDistance} tpTrigger:${tpTrigger} tpExpand:${tpEkspansi}`,
          params: { enableBreakeven, trailingDistance, tpTrigger, tpEkspansi },
          baselineNetProfit: scenarioBaseline.netProfit,
          ...result,
          deltaNetProfit: Number((result.netProfit - scenarioBaseline.netProfit).toFixed(2)),
        });
      }
    }
  }
}

for (const trailingDistance of [15, 20, 30, 40]) {
  for (const tpTrigger of [5, 10, 15]) {
    for (const confirmationsRequired of [2, 3, 4]) {
      for (const minimumProfit of [0, 10, 25]) {
        const params = {
          ...baseParams,
          enable_breakeven: true,
          trailing_distance: trailingDistance,
          tp_trigger: tpTrigger,
        };
        const result = runGuardedExitPolicy(params, confirmationsRequired, minimumProfit);
        const scenarioBaseline = runBaseline(params);
        scenarios.push({
          name: `Guarded exit BE:on trail:${trailingDistance} tpTrigger:${tpTrigger} confirm:${confirmationsRequired} minProfit:${minimumProfit}`,
          params: { trailingDistance, tpTrigger, confirmationsRequired, minimumProfit },
          baselineNetProfit: scenarioBaseline.netProfit,
          ...result,
          deltaNetProfit: Number((result.netProfit - scenarioBaseline.netProfit).toFixed(2)),
        });
      }
    }
  }
}

scenarios.sort((left, right) => right.netProfit - left.netProfit);
const report = {
  generatedAt: new Date().toISOString(),
  replayRange: replayData.meta?.date_from && replayData.meta?.date_to
    ? `${replayData.meta.date_from} to ${replayData.meta.date_to}`
    : "2026-01 to 2026-08",
  candles: replayData.candles.length,
  executedTrades: executedTrades.length,
  baseline,
  totalScenarios: scenarios.length,
  profitableVsBaseline: scenarios.filter((scenario) => scenario.deltaNetProfit > 0).length,
  topScenarios: scenarios.slice(0, 20),
  bottomScenarios: scenarios.slice(-10).reverse(),
};

await writeFile(new URL("./three_brain_benchmark_2026-01_to_08.json", import.meta.url), `${JSON.stringify(report, null, 2)}\n`);

console.log(JSON.stringify({
  baseline,
  totalScenarios: report.totalScenarios,
  profitableVsBaseline: report.profitableVsBaseline,
  topScenarios: report.topScenarios.slice(0, 5),
}, null, 2));