import { evaluateContinuationStrength } from "../ValueCell_MT5/frontend/src/app/mt5/continuation-strength.ts";
import {
  DEFAULT_ENTRY_FILTER_PARAMS,
  DEFAULT_STRATEGY_PARAMS,
  calculateATR,
  getProcessedReplayTrades,
  simulateReplayTradeOutcome,
} from "../ValueCell_MT5/frontend/src/app/mt5/replay-engine.ts";

const API_URL = "http://127.0.0.1:8000/api/v1/trading/replay";
const PERIOD = 14;
const query = new URLSearchParams({
  year_from: process.argv[2] ?? "2026",
  month_from: process.argv[3] ?? "1",
  year_to: process.argv[4] ?? process.argv[2] ?? "2026",
  month_to: process.argv[5] ?? process.argv[3] ?? "1",
});

async function fetchReplay(timeframe) {
  const response = await fetch(`${API_URL}?${query}&timeframe=${timeframe}`);
  if (!response.ok) {
    throw new Error(`${timeframe} Replay API ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

const [m15Data, h1Data, h4Data] = await Promise.all([
  fetchReplay("M15"),
  fetchReplay("H1"),
  fetchReplay("H4"),
]);
const candles = m15Data.candles;
const structures = m15Data.structures;
const processed = getProcessedReplayTrades(
  m15Data,
  structures,
  DEFAULT_ENTRY_FILTER_PARAMS,
  m15Data.candles,
  h1Data.candles,
  h4Data.candles,
);
const finalCandleTime = candles.at(-1)?.time ?? 0;
const executedTrades = processed.executedTrades.map((trade) => ({
  ...trade,
  outcome: simulateReplayTradeOutcome(
    trade,
    candles,
    structures,
    DEFAULT_STRATEGY_PARAMS,
    finalCandleTime,
  ),
}));

function isStructureAligned(trade, candleTime) {
  const latest = structures
    .filter((event) => event.time <= candleTime && (!event.timeframe || event.timeframe.toUpperCase() === "M15"))
    .at(-1);
  const direction = `${latest?.direction ?? ""} ${latest?.type ?? ""}`.toUpperCase();
  return trade.type.toUpperCase().includes("BUY")
    ? direction.includes("BULL") || direction.includes("BUY")
    : direction.includes("BEAR") || direction.includes("SELL");
}

const statusCounts = { STRONG: 0, NEUTRAL: 0, WEAK: 0 };
const tradeRows = [];

for (const trade of executedTrades) {
  if (!trade.outcome.isClosed || trade.outcome.exitTime == null || trade.outcome.netProfit == null) continue;
  const samples = { STRONG: 0, NEUTRAL: 0, WEAK: 0 };
  let scoreTotal = 0;

  for (let index = 0; index < candles.length; index += 1) {
    const candle = candles[index];
    if (candle.time < trade.entry_time || candle.time > trade.outcome.exitTime) continue;

    const result = evaluateContinuationStrength({
      direction: trade.type,
      entryPrice: trade.entry_price,
      currentCandle: candle,
      previousCandles: candles.slice(Math.max(0, index - 6), Math.max(0, index - 1)),
      atr: calculateATR(candles, candle.time, PERIOD),
      structureAligned: isStructureAligned(trade, candle.time),
    });

    samples[result.status] += 1;
    statusCounts[result.status] += 1;
    scoreTotal += result.score;
  }

  const sampleCount = samples.STRONG + samples.NEUTRAL + samples.WEAK;
  const dominantStatus = Object.entries(samples).sort((left, right) => right[1] - left[1])[0][0];
  tradeRows.push({
    ticket: trade.ticket,
    type: trade.type,
    exitTime: trade.outcome.exitTime,
    exitPrice: trade.outcome.exitPrice,
    closeReason: trade.outcome.closeReason,
    netProfit: trade.outcome.netProfit,
    samples: sampleCount,
    averageScore: sampleCount > 0 ? scoreTotal / sampleCount : 0,
    dominantStatus,
  });
}

const totalSamples = Object.values(statusCounts).reduce((total, count) => total + count, 0);
const byDominantStatus = Object.fromEntries(
  ["STRONG", "NEUTRAL", "WEAK"].map((status) => {
    const rows = tradeRows.filter((row) => row.dominantStatus === status);
    const totalNetProfit = rows.reduce((total, row) => total + row.netProfit, 0);
    return [status, {
      trades: rows.length,
      wins: rows.filter((row) => row.netProfit > 0).length,
      totalNetProfit,
      averageNetProfit: rows.length > 0 ? totalNetProfit / rows.length : 0,
    }];
  }),
);

console.log(JSON.stringify({
  range: Object.fromEntries(query),
  candidates: processed.executedTrades.length + processed.rejectedTrades.length,
  executedTrades: processed.executedTrades.length,
  rejectedTrades: processed.rejectedTrades.length,
  analyzedClosedTrades: tradeRows.length,
  totalNetProfit: tradeRows.reduce((total, trade) => total + trade.netProfit, 0),
  totalSamples,
  statusCounts,
  statusPercentages: Object.fromEntries(
    Object.entries(statusCounts).map(([status, count]) => [status, totalSamples > 0 ? count / totalSamples * 100 : 0]),
  ),
  byDominantStatus,
  trades: tradeRows,
}, null, 2));