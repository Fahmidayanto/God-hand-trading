import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_ENTRY_FILTER_PARAMS,
  DEFAULT_STRATEGY_PARAMS,
  getProcessedReplayTrades,
  simulateReplayTradeOutcome,
} from "../replay-engine.ts";

const candles = [
  { time: 100, open: 100, high: 102, low: 99, close: 101, volume: 1, ema200: 98, spread: 3 },
  { time: 1000, open: 101, high: 104, low: 100, close: 103, volume: 1, ema200: 99, spread: 3 },
  { time: 1900, open: 103, high: 105, low: 102, close: 104, volume: 1, ema200: 100, spread: 3 },
];

const replayData = {
  candles,
  structures: [
    {
      type: "CHoCH",
      direction: "BULLISH",
      price: 101,
      time: 100,
      timeframe: "M15",
      status: "ACCEPTED",
      previous_price: null,
      previous_time: null,
    },
  ],
  trades: [],
  available_months: [],
  meta: {
    timeframe: "M15",
    date_from: "2026-01-01",
    date_to: "2026-01-01",
    total_candles: candles.length,
    total_structures: 1,
    total_trades: 0,
  },
};

test("builds replay candidates from structures instead of API trades", () => {
  const params = {
    ...DEFAULT_ENTRY_FILTER_PARAMS,
    h1_ema200_filter: false,
    h4_ema_filter: false,
    ema_slope_filter: false,
    ema_stretch_filter: false,
    bos_cycle_filter: false,
  };

  const result = getProcessedReplayTrades(
    replayData,
    replayData.structures,
    params,
    candles,
    [],
    [],
  );

  assert.equal(result.executedTrades.length, 1);
  assert.equal(result.rejectedTrades.length, 0);
  assert.equal(result.executedTrades[0].entry_time, 1000);
  assert.equal(result.executedTrades[0].entry_price, 101.03);
});

test("calculates closed trade Net_Profit inside the shared replay engine", () => {
  const trade = {
    ticket: 1,
    type: "BUY",
    status: "EXECUTED",
    reject_reason: null,
    entry_price: 100,
    exit_price: null,
    sl: null,
    tp: null,
    net_profit: null,
    session: "CHOCH",
    entry_time: 1000,
    exit_time: null,
    lot_size: 0.05,
  };
  const outcomeCandles = [
    { time: 1000, open: 100, high: 101, low: 84, close: 90, volume: 1, ema200: 98, spread: 4 },
  ];

  const outcome = simulateReplayTradeOutcome(
    trade,
    outcomeCandles,
    [],
    { ...DEFAULT_STRATEGY_PARAMS, use_price_ratio_scaling: false, max_sl_dist: 15 },
    1000,
  );

  assert.equal(outcome.isClosed, true);
  assert.equal(outcome.exitPrice, 85);
  assert.equal(outcome.exitTime, 1000);
  assert.equal(outcome.closeReason, "SL");
  assert.equal(outcome.netProfit, -75.2);
});