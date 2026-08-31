import assert from "node:assert/strict";
import test from "node:test";

import { DEFAULT_STRATEGY_PARAMS } from "../replay-engine.ts";
import {
  simulateThreeBrainReplayTradeOutcome,
  simulateThreeBrainTradeOutcome,
} from "../three-brain-engine.ts";

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

const params = {
  ...DEFAULT_STRATEGY_PARAMS,
  use_price_ratio_scaling: false,
  enable_breakeven: false,
  force_24h_close: true,
  min_sl_dist: 15,
  max_sl_dist: 15,
  initial_tp_dist: 10,
  tp_ekspansi: 10,
  max_ekspansi: 2,
};

const bullishStructure = {
  type: "BOS",
  direction: "BULLISH",
  price: 101,
  time: 1000,
  timeframe: "M15",
  status: "ACCEPTED",
  previous_price: null,
  previous_time: null,
};

const bearishStructure = {
  ...bullishStructure,
  direction: "BEARISH",
  time: 1900,
};

test("closes a buy when continuation is weak and structure turns adverse", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 101, low: 97, close: 98, volume: 80, ema200: 100, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    trade,
    candles,
    [bullishStructure, bearishStructure],
    params,
    1900,
  );

  assert.equal(result.isClosedSimulated, true);
  assert.equal(result.closeReason, "THREE_BRAIN_EXIT");
  assert.equal(result.exitPriceSimulated, 98);
});

test("protects meaningful profit by moving the stop beyond entry", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 112, low: 100, close: 111, volume: 80, ema200: 105, spread: 4 },
    { time: 2800, open: 111, high: 112, low: 108, close: 110.5, volume: 70, ema200: 106, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    trade,
    candles,
    [bullishStructure],
    { ...params, enable_breakeven: true, breakeven_trigger: 5, initial_tp_dist: 30, tp_ekspansi: 20 },
    2800,
  );

  assert.ok(result.sl > 100);
  assert.equal(result.beTriggered, true);
});

test("trails the protected stop with Otak 1 trailing distance", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 112, low: 100, close: 111, volume: 140, ema200: 100, spread: 4 },
    { time: 2800, open: 111, high: 120, low: 110, close: 119, volume: 130, ema200: 105, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    trade,
    candles,
    [bullishStructure],
    {
      ...params,
      enable_breakeven: true,
      trailing_distance: 5,
      initial_tp_dist: 40,
      tp_ekspansi: 20,
    },
    2800,
  );

  assert.equal(result.beTriggered, true);
  assert.equal(result.sl, 114);
  assert.ok(result.expansionCount >= 1);
  assert.equal(result.protectionActivatedTime, 2800);
});

test("uses the price-scaled effective lot for Three-Brain protection", () => {
  const scaledTrade = {
    ...trade,
    entry_price: 4405.54,
    lot_size: 0.05,
  };
  const candles = [
    { time: 1000, open: 4405.54, high: 4406, low: 4405, close: 4405.54, volume: 100, ema200: 4400, spread: 4 },
    { time: 1900, open: 4405.54, high: 4420, low: 4405, close: 4419.96, volume: 80, ema200: 4410, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    scaledTrade,
    candles,
    [bullishStructure],
    {
      ...params,
      use_price_ratio_scaling: true,
      base_reference_price: 2000,
      lot_override: 0.05,
      initial_tp_dist: 100,
    },
    1900,
  );

  assert.equal(result.beTriggered, false);
  assert.equal(result.sl, result.initialSL);
});

test("extends the target for strong aligned continuation", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 106, low: 100, close: 105, volume: 140, ema200: 100, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    trade,
    candles,
    [bullishStructure],
    params,
    1900,
  );

  assert.equal(result.isClosedSimulated, false);
  assert.ok(result.tp > 110);
  assert.equal(result.expansionCount, 1);
});

test("keeps the 24 hour safety exit", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 87400, open: 102, high: 103, low: 101, close: 102.5, volume: 100, ema200: 100, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    trade,
    candles,
    [bullishStructure],
    params,
    87400,
  );

  assert.equal(result.isClosedSimulated, true);
  assert.equal(result.closeReason, "THREE_BRAIN_FORCE_EXIT");
  assert.equal(result.exitTimeSimulated, 87400);
  assert.equal(result.exitPriceSimulated, 102);
});

test("calculates closed Three-Brain Net_Profit with replay costs", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 101, low: 97, close: 98, volume: 80, ema200: 100, spread: 4 },
  ];

  const result = simulateThreeBrainReplayTradeOutcome(
    { ...trade, commission: 1, swap: -0.5 },
    candles,
    [bullishStructure, bearishStructure],
    params,
    1900,
  );

  assert.equal(result.isClosed, true);
  assert.equal(result.grossProfit, -10);
  assert.equal(result.spreadCost, 0.2);
  assert.equal(result.netProfit, -11.7);
});
