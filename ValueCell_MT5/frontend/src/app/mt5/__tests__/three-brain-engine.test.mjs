import assert from "node:assert/strict";
import test from "node:test";

import { DEFAULT_STRATEGY_PARAMS } from "../replay-engine.ts";
import {
  DEFAULT_THREE_BRAIN_CONFIG,
  decideThreeBrainAction,
  getThreeBrainConfigFromSearch,
  getThreeBrainPreviousCandles,
  shouldUseThreeBrainExecution,
  simulateThreeBrainReplayTradeOutcome,
  simulateThreeBrainTradeOutcome,
} from "../three-brain-engine.ts";

test("runs Three-Brain execution only when Otak 2 and Otak 3 are enabled", () => {
  assert.equal(shouldUseThreeBrainExecution("original", true, true), false);
  assert.equal(shouldUseThreeBrainExecution("three-brain", false, true), false);
  assert.equal(shouldUseThreeBrainExecution("three-brain", true, false), false);
  assert.equal(shouldUseThreeBrainExecution("three-brain", true, true), true);
});

test("uses twenty candles before evaluation including candles before entry", () => {
  const candles = Array.from({ length: 22 }, (_, index) => ({ time: index, close: index }));

  const previousCandles = getThreeBrainPreviousCandles(candles, 21);

  assert.equal(previousCandles.length, 20);
  assert.equal(previousCandles[0].time, 1);
  assert.equal(previousCandles.at(-1).time, 20);
});

test("maps Otak 2 states to graduated Otak 3 actions", () => {
  assert.equal(decideThreeBrainAction({
    state: "STRONG_CONTINUATION",
    protectedPosition: true,
    floatingNetProfit: 200,
    profitGivebackRatio: 0,
    minimumExitNetProfit: 120,
  }), "EXTEND_TP");
  assert.equal(decideThreeBrainAction({
    state: "HEALTHY_PULLBACK",
    protectedPosition: true,
    floatingNetProfit: 200,
    profitGivebackRatio: 0.1,
    minimumExitNetProfit: 120,
  }), "HOLD");
  assert.equal(decideThreeBrainAction({
    state: "MOMENTUM_EXHAUSTION",
    protectedPosition: true,
    floatingNetProfit: 200,
    profitGivebackRatio: 0.15,
    minimumExitNetProfit: 120,
  }), "TIGHTEN_SL");
  assert.equal(decideThreeBrainAction({
    state: "MOMENTUM_EXHAUSTION",
    protectedPosition: true,
    floatingNetProfit: 200,
    profitGivebackRatio: 0.35,
    minimumExitNetProfit: 120,
  }), "LOCK_PROFIT");
  assert.equal(decideThreeBrainAction({
    state: "REVERSAL_CONFIRMED",
    protectedPosition: true,
    floatingNetProfit: 200,
    profitGivebackRatio: 0.4,
    minimumExitNetProfit: 120,
  }), "FULL_EXIT");
});

test("supports confidence gates, custom state actions, and giveback thresholds", () => {
  assert.equal(decideThreeBrainAction({
    state: "REVERSAL_CONFIRMED",
    confidence: 39,
    minimumConfidence: 40,
    protectedPosition: true,
    floatingNetProfit: 200,
    profitGivebackRatio: 0.5,
    minimumExitNetProfit: 120,
  }), "HOLD");
  assert.equal(decideThreeBrainAction({
    state: "REVERSAL_CONFIRMED",
    confidence: 80,
    minimumConfidence: 40,
    protectedPosition: true,
    floatingNetProfit: 200,
    profitGivebackRatio: 0.5,
    minimumExitNetProfit: 120,
    stateActions: { REVERSAL_CONFIRMED: "LOCK_PROFIT" },
  }), "LOCK_PROFIT");
  assert.equal(decideThreeBrainAction({
    state: "MOMENTUM_EXHAUSTION",
    confidence: 80,
    minimumConfidence: 40,
    protectedPosition: true,
    floatingNetProfit: 200,
    profitGivebackRatio: 0.2,
    profitGivebackTrigger: 0.2,
    minimumExitNetProfit: 120,
  }), "LOCK_PROFIT");
});

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

const testThreeBrainConfig = {
  weakScoreThreshold: 35,
  adverseConfirmationCandles: 3,
  minimumExitNetProfit: 120,
  requireAdverseStructure: true,
  managementOverrides: {},
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

test("uses the January 2026 optimized Three-Brain defaults", () => {
  assert.deepEqual(getThreeBrainConfigFromSearch(""), {
    weakScoreThreshold: 35,
    adverseConfirmationCandles: 3,
    minimumExitNetProfit: 120,
    requireAdverseStructure: true,
    managementOverrides: {},
  });
});

test("allows Three-Brain management to override exits without mutating original params", () => {
  const originalParams = { ...params, initial_tp_dist: 7 };
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 108, low: 100, close: 107, volume: 120, ema200: 100, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    trade,
    candles,
    [bullishStructure],
    originalParams,
    1900,
    {
      ...testThreeBrainConfig,
      managementOverrides: { initial_tp_dist: 20 },
    },
  );

  assert.equal(result.isClosedSimulated, false);
  assert.equal(result.initialTP, 120);
  assert.equal(originalParams.initial_tp_dist, 7);
});

test("does not close an unprotected position on two weak adverse candles", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 101, low: 97, close: 98, volume: 80, ema200: 100, spread: 4 },
    { time: 2800, open: 98, high: 103, low: 96, close: 97, volume: 70, ema200: 100, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    trade,
    candles,
    [bullishStructure, bearishStructure],
    params,
    2800,
    testThreeBrainConfig,
  );

  assert.equal(result.isClosedSimulated, false);
});

test("does not bypass reversal confirmation on the first adverse candle", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 106, low: 100, close: 105, volume: 120, ema200: 100, spread: 4 },
    { time: 2800, open: 105, high: 105, low: 101, close: 102, volume: 180, ema200: 106, spread: 4 },
    { time: 3700, open: 102, high: 108, low: 101, close: 107, volume: 80, ema200: 103, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    trade,
    candles,
    [bullishStructure, { ...bearishStructure, time: 2800 }],
    { ...params, initial_tp_dist: 7, tp_trigger: 0 },
    3700,
    { ...testThreeBrainConfig, adverseConfirmationCandles: 2, minimumExitNetProfit: 25 },
  );

  assert.notEqual(result.closeReason, "THREE_BRAIN_EXIT");
});

test("closes protected profit after two weak adverse candles", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 106, low: 100, close: 105, volume: 120, ema200: 100, spread: 4 },
    { time: 2800, open: 105, high: 105, low: 104, close: 105, volume: 70, ema200: 107, spread: 4 },
    { time: 3700, open: 105, high: 105, low: 104, close: 105, volume: 60, ema200: 107, spread: 4 },
    { time: 4600, open: 105, high: 108, low: 104, close: 107, volume: 80, ema200: 106, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    trade,
    candles,
    [bullishStructure, { ...bearishStructure, time: 2800 }],
    { ...params, enable_breakeven: false, breakeven_trigger: 5, initial_tp_dist: 7, tp_trigger: 0 },
    4600,
    { ...testThreeBrainConfig, adverseConfirmationCandles: 2, minimumExitNetProfit: 25 },
  );

  assert.equal(result.closeReason, "THREE_BRAIN_EXIT");
  assert.equal(result.exitTimeSimulated, 3700);
  assert.equal(result.exitPriceSimulated, 105);
});

test("keeps Three-Brain exit parameters separate from original strategy params", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 106, low: 100, close: 105, volume: 120, ema200: 100, spread: 4 },
    { time: 2800, open: 105, high: 105, low: 104, close: 105, volume: 70, ema200: 107, spread: 4 },
    { time: 3700, open: 105, high: 105, low: 104, close: 105, volume: 60, ema200: 107, spread: 4 },
    { time: 4600, open: 105, high: 105, low: 104, close: 105, volume: 50, ema200: 107, spread: 4 },
    { time: 5500, open: 105, high: 108, low: 104, close: 107, volume: 80, ema200: 106, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    trade,
    candles,
    [bullishStructure, { ...bearishStructure, time: 2800 }],
    { ...params, enable_breakeven: false, breakeven_trigger: 5, initial_tp_dist: 7, tp_trigger: 0 },
    5500,
    { ...testThreeBrainConfig, adverseConfirmationCandles: 3, minimumExitNetProfit: 25 },
  );

  assert.equal(result.closeReason, "THREE_BRAIN_EXIT");
  assert.equal(result.exitTimeSimulated, 4600);
});

test("holds after one weak adverse candle so Otak 1 trailing remains the fallback", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 104, low: 97, close: 98, volume: 80, ema200: 100, spread: 4 },
  ];

  const result = simulateThreeBrainTradeOutcome(
    trade,
    candles,
    [bullishStructure, bearishStructure],
    params,
    1900,
    testThreeBrainConfig,
  );

  assert.equal(result.isClosedSimulated, false);
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
    testThreeBrainConfig,
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
    testThreeBrainConfig,
  );

  assert.equal(result.beTriggered, true);
  assert.equal(result.sl, 114);
  assert.equal(result.expansionCount, 0);
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
    testThreeBrainConfig,
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
    testThreeBrainConfig,
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
    testThreeBrainConfig,
  );

  assert.equal(result.isClosedSimulated, true);
  assert.equal(result.closeReason, "24H_FORCE");
  assert.equal(result.exitTimeSimulated, 87400);
  assert.equal(result.exitPriceSimulated, 102);
});

test("calculates Three-Brain Net_Profit with replay costs", () => {
  const candles = [
    { time: 1000, open: 100, high: 101, low: 99, close: 100.5, volume: 100, ema200: 99, spread: 4 },
    { time: 1900, open: 100.5, high: 101, low: 97, close: 98, volume: 80, ema200: 100, spread: 4 },
    { time: 2800, open: 98, high: 103, low: 96, close: 97, volume: 70, ema200: 100, spread: 4 },
  ];

  const result = simulateThreeBrainReplayTradeOutcome(
    { ...trade, commission: 1, swap: -0.5 },
    candles,
    [bullishStructure, bearishStructure],
    { ...params, force_24h_close: false, initial_tp_dist: 3, tp_trigger: 0 },
    2800,
    testThreeBrainConfig,
  );

  assert.equal(result.isClosed, true);
  assert.equal(result.grossProfit, 15);
  assert.equal(result.spreadCost, 0.2);
  assert.equal(result.netProfit, 13.3);
});
