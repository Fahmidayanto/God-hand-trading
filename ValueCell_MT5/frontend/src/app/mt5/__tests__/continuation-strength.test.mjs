import assert from "node:assert/strict";
import test from "node:test";

import {
  classifyContinuationState,
  classifyContinuationTrend,
  evaluateStructureStrength,
  evaluateContinuationStrength,
} from "../continuation-strength.ts";

test("distinguishes a healthy pullback from a confirmed reversal", () => {
  assert.equal(classifyContinuationState({
    continuationScore: 58,
    reversalScore: 28,
    trendStatus: "DECLINING",
  }).state, "HEALTHY_PULLBACK");

  assert.equal(classifyContinuationState({
    continuationScore: 18,
    reversalScore: 82,
    trendStatus: "RAPID_DECLINE",
  }).state, "REVERSAL_CONFIRMED");
});

const bullishCandle = {
  time: 120,
  open: 101,
  high: 103.2,
  low: 100.8,
  close: 103,
  volume: 150,
  ema200: 100,
};

test("rates aligned bullish continuation as strong", () => {
  const result = evaluateContinuationStrength({
    direction: "BUY",
    entryPrice: 100,
    currentCandle: bullishCandle,
    previousCandles: [
      { ...bullishCandle, time: 30, close: 100, volume: 85, ema200: 99 },
      { ...bullishCandle, time: 60, close: 101, volume: 90, ema200: 99.4 },
      { ...bullishCandle, time: 90, close: 102, volume: 95, ema200: 99.7 },
    ],
    atr: 2,
    structureAligned: true,
  });

  assert.equal(result.score, 100);
  assert.equal(result.status, "STRONG");
  assert.equal(result.components.length, 5);
});

test("rates adverse bearish evidence for a buy as weak", () => {
  const result = evaluateContinuationStrength({
    direction: "BUY",
    entryPrice: 100,
    currentCandle: {
      ...bullishCandle,
      open: 100,
      high: 100.2,
      low: 97.5,
      close: 98,
      volume: 50,
      ema200: 101,
    },
    previousCandles: [
      { ...bullishCandle, time: 60, volume: 100 },
      { ...bullishCandle, time: 90, volume: 100 },
    ],
    atr: 2,
    structureAligned: false,
  });

  assert.equal(result.score, 3);
  assert.equal(result.status, "WEAK");
});

test("supports sell continuation using mirrored direction checks", () => {
  const result = evaluateContinuationStrength({
    direction: "SELL",
    entryPrice: 100,
    currentCandle: {
      ...bullishCandle,
      open: 99,
      high: 99.2,
      low: 96.8,
      close: 97,
      volume: 150,
      ema200: 101,
    },
    previousCandles: [
      { ...bullishCandle, time: 30, close: 100, volume: 85, ema200: 102 },
      { ...bullishCandle, time: 60, close: 99, volume: 90, ema200: 101.6 },
      { ...bullishCandle, time: 90, close: 98, volume: 95, ema200: 101.3 },
    ],
    atr: 2,
    structureAligned: true,
  });

  assert.equal(result.score, 100);
  assert.equal(result.status, "STRONG");
});

test("scores local momentum gradually using the close three candles earlier", () => {
  const result = evaluateContinuationStrength({
    direction: "BUY",
    entryPrice: 100,
    currentCandle: { ...bullishCandle, close: 101.8 },
    previousCandles: [
      { ...bullishCandle, time: 30, close: 101 },
      { ...bullishCandle, time: 60, close: 101.2 },
      { ...bullishCandle, time: 90, close: 101.4 },
    ],
    atr: 2,
    structureAligned: true,
  });

  const momentum = result.components.find((component) => component.key === "momentum");
  assert.equal(momentum.score, 10);
  assert.match(momentum.reason, /0.40 x ATR/);
});

test("supports an independent momentum lookback", () => {
  const input = {
    direction: "BUY",
    entryPrice: 100,
    currentCandle: { ...bullishCandle, close: 102 },
    previousCandles: [
      { ...bullishCandle, time: 15, close: 100 },
      { ...bullishCandle, time: 30, close: 101.8 },
      { ...bullishCandle, time: 45, close: 101.9 },
    ],
    atr: 2,
    structureAligned: true,
  };

  const defaultResult = evaluateContinuationStrength(input);
  const oneCandleResult = evaluateContinuationStrength(input, { momentumLookback: 1 });

  assert.equal(defaultResult.components.find((component) => component.key === "momentum").score, 20);
  assert.equal(oneCandleResult.components.find((component) => component.key === "momentum").score, 5);
});

test("does not treat old entry profit as active momentum during a local reversal", () => {
  const result = evaluateContinuationStrength({
    direction: "BUY",
    entryPrice: 100,
    currentCandle: {
      ...bullishCandle,
      open: 109,
      high: 109.2,
      low: 107.5,
      close: 108,
      volume: 80,
    },
    previousCandles: [
      { ...bullishCandle, time: 30, close: 111, volume: 100 },
      { ...bullishCandle, time: 60, close: 110.5, volume: 100 },
      { ...bullishCandle, time: 90, close: 109.5, volume: 100 },
    ],
    atr: 2,
    structureAligned: false,
  });

  const momentum = result.components.find((component) => component.key === "momentum");
  assert.equal(momentum.score, 0);
  assert.equal(result.status, "WEAK");
});

test("scores directional candle quality from doji to impulse", () => {
  const cases = [
    {
      name: "strong adverse",
      candle: { open: 102, high: 102.2, low: 100, close: 100.2 },
      expectedScore: 0,
    },
    {
      name: "doji",
      candle: { open: 101, high: 102, low: 100, close: 101.1 },
      expectedScore: 5,
    },
    {
      name: "weak aligned",
      candle: { open: 101, high: 102, low: 100.5, close: 101.3 },
      expectedScore: 10,
    },
    {
      name: "healthy aligned",
      candle: { open: 101, high: 102.5, low: 100.8, close: 102 },
      expectedScore: 15,
    },
    {
      name: "impulsive aligned",
      candle: { open: 100, high: 102.2, low: 99.8, close: 102 },
      expectedScore: 20,
    },
  ];

  for (const testCase of cases) {
    const result = evaluateContinuationStrength({
      direction: "BUY",
      entryPrice: 100,
      currentCandle: { ...bullishCandle, ...testCase.candle },
      previousCandles: [
        { ...bullishCandle, time: 30, close: 99 },
        { ...bullishCandle, time: 60, close: 99.5 },
        { ...bullishCandle, time: 90, close: 100 },
      ],
      atr: 2,
      structureAligned: true,
    });

    const directional = result.components.find((component) => component.key === "directional");
    assert.equal(directional.score, testCase.expectedScore, testCase.name);
  }
});

test("scores volume by participation and candle direction", () => {
  const cases = [
    {
      name: "high adverse pressure",
      candle: { open: 102, high: 102.2, low: 99.8, close: 100, volume: 140 },
      expectedScore: 0,
    },
    {
      name: "low participation",
      candle: { open: 100, high: 101, low: 99.8, close: 100.7, volume: 70 },
      expectedScore: 3,
    },
    {
      name: "normal aligned participation",
      candle: { open: 100, high: 101.2, low: 99.8, close: 101, volume: 100 },
      expectedScore: 7,
    },
    {
      name: "high aligned participation",
      candle: { open: 100, high: 101.5, low: 99.8, close: 101.2, volume: 130 },
      expectedScore: 12,
    },
    {
      name: "very high aligned impulse",
      candle: { open: 100, high: 102.2, low: 99.8, close: 102, volume: 170 },
      expectedScore: 15,
    },
  ];

  for (const testCase of cases) {
    const result = evaluateContinuationStrength({
      direction: "BUY",
      entryPrice: 100,
      currentCandle: { ...bullishCandle, ...testCase.candle },
      previousCandles: [
        { ...bullishCandle, time: 30, close: 99, volume: 100 },
        { ...bullishCandle, time: 60, close: 99.5, volume: 100 },
        { ...bullishCandle, time: 90, close: 100, volume: 100 },
      ],
      atr: 2,
      structureAligned: true,
    });

    const activity = result.components.find((component) => component.key === "activity");
    assert.equal(activity.score, testCase.expectedScore, testCase.name);
  }
});

test("uses only the latest twenty candles for the volume baseline", () => {
  const previousCandles = [
    { ...bullishCandle, time: 1, close: 99, volume: 10_000 },
    ...Array.from({ length: 20 }, (_, index) => ({
      ...bullishCandle,
      time: index + 2,
      close: 99 + index * 0.05,
      volume: 100,
    })),
  ];
  const result = evaluateContinuationStrength({
    direction: "BUY",
    entryPrice: 100,
    currentCandle: { ...bullishCandle, volume: 130 },
    previousCandles,
    atr: 2,
    structureAligned: true,
  });

  const activity = result.components.find((component) => component.key === "activity");
  assert.equal(activity.score, 12);
});

test("supports an independent volume baseline lookback", () => {
  const input = {
    direction: "BUY",
    entryPrice: 100,
    currentCandle: { ...bullishCandle, volume: 130 },
    previousCandles: [
      { ...bullishCandle, time: 30, close: 99, volume: 20 },
      { ...bullishCandle, time: 60, close: 99.5, volume: 100 },
      { ...bullishCandle, time: 90, close: 100, volume: 100 },
    ],
    atr: 2,
    structureAligned: true,
  };

  const defaultResult = evaluateContinuationStrength(input);
  const twoCandleResult = evaluateContinuationStrength(input, { volumeLookback: 2 });

  assert.equal(defaultResult.components.find((component) => component.key === "activity").score, 15);
  assert.equal(twoCandleResult.components.find((component) => component.key === "activity").score, 12);
});

test("classifies three-score continuation trends", () => {
  assert.deepEqual(classifyContinuationTrend([45, 58, 72]), {
    status: "IMPROVING",
    change: 27,
  });
  assert.deepEqual(classifyContinuationTrend([70, 68, 69]), {
    status: "STABLE",
    change: -1,
  });
  assert.deepEqual(classifyContinuationTrend([82, 74, 65]), {
    status: "DECLINING",
    change: -17,
  });
  assert.deepEqual(classifyContinuationTrend([85, 72, 60]), {
    status: "RAPID_DECLINE",
    change: -25,
  });
});

test("keeps score trend unknown until three scores exist", () => {
  assert.deepEqual(classifyContinuationTrend([60, 55]), {
    status: "INSUFFICIENT_DATA",
    change: -5,
  });
});

test("scores EMA200 context from adverse to strong trend", () => {
  const cases = [
    {
      name: "wrong side",
      currentEma: 102,
      previousEma: 101,
      close: 101,
      expectedScore: 0,
    },
    {
      name: "near EMA",
      currentEma: 100.7,
      previousEma: 100.5,
      close: 101,
      expectedScore: 5,
    },
    {
      name: "flat EMA",
      currentEma: 100,
      previousEma: 100,
      close: 101,
      expectedScore: 8,
    },
    {
      name: "supportive slope",
      currentEma: 100,
      previousEma: 99.5,
      close: 101,
      expectedScore: 12,
    },
    {
      name: "strong healthy trend",
      currentEma: 100,
      previousEma: 99,
      close: 102,
      expectedScore: 15,
    },
    {
      name: "overextended",
      currentEma: 100,
      previousEma: 99,
      close: 105,
      expectedScore: 12,
    },
  ];

  for (const testCase of cases) {
    const result = evaluateContinuationStrength({
      direction: "BUY",
      entryPrice: 100,
      currentCandle: {
        ...bullishCandle,
        close: testCase.close,
        ema200: testCase.currentEma,
      },
      previousCandles: [
        { ...bullishCandle, time: 30, close: 99, ema200: testCase.previousEma },
        { ...bullishCandle, time: 60, close: 99.5, ema200: testCase.previousEma },
        { ...bullishCandle, time: 90, close: 100, ema200: testCase.previousEma },
      ],
      atr: 2,
      structureAligned: true,
    });

    const trend = result.components.find((component) => component.key === "trend");
    assert.equal(trend.score, testCase.expectedScore, testCase.name);
  }
});

test("supports an independent EMA slope lookback", () => {
  const input = {
    direction: "BUY",
    entryPrice: 100,
    currentCandle: { ...bullishCandle, close: 102, ema200: 100 },
    previousCandles: [
      { ...bullishCandle, time: 30, close: 99, ema200: 99 },
      { ...bullishCandle, time: 60, close: 99.5, ema200: 100 },
      { ...bullishCandle, time: 90, close: 100, ema200: 100 },
    ],
    atr: 2,
    structureAligned: true,
  };

  const defaultResult = evaluateContinuationStrength(input);
  const oneCandleResult = evaluateContinuationStrength(input, { emaSlopeLookback: 1 });

  assert.equal(defaultResult.components.find((component) => component.key === "trend").score, 15);
  assert.equal(oneCandleResult.components.find((component) => component.key === "trend").score, 8);
});

test("scores M15 structure quality from missing to confirmed follow-through", () => {
  const currentCandle = { ...bullishCandle, time: 10_000, close: 103 };
  const baseStructure = {
    type: "BOS",
    direction: "BULLISH",
    price: 102,
    time: 9_100,
    timeframe: "M15",
    status: "ACCEPTED",
  };

  assert.equal(evaluateStructureStrength({
    direction: "BUY",
    currentCandle,
    atr: 2,
    structure: null,
  }).score, 5);
  assert.equal(evaluateStructureStrength({
    direction: "BUY",
    currentCandle,
    atr: 2,
    structure: { ...baseStructure, direction: "BEARISH" },
  }).score, 0);
  assert.equal(evaluateStructureStrength({
    direction: "BUY",
    currentCandle,
    atr: 2,
    structure: { ...baseStructure, time: 1_000 },
  }).score, 10);
  assert.equal(evaluateStructureStrength({
    direction: "BUY",
    currentCandle,
    atr: 2,
    structure: { ...baseStructure, type: "CHOCH" },
  }).score, 15);
  assert.equal(evaluateStructureStrength({
    direction: "BUY",
    currentCandle: { ...currentCandle, close: 102.5 },
    atr: 2,
    structure: baseStructure,
  }).score, 22);
  assert.equal(evaluateStructureStrength({
    direction: "BUY",
    currentCandle,
    atr: 2,
    structure: baseStructure,
  }).score, 30);
});

test("limits unaccepted aligned structure to preliminary evidence", () => {
  const result = evaluateStructureStrength({
    direction: "SELL",
    currentCandle: { ...bullishCandle, time: 10_000, close: 97 },
    atr: 2,
    structure: {
      type: "BOS",
      direction: "BEARISH",
      price: 98,
      time: 9_100,
      timeframe: "M15",
      status: "PENDING",
    },
  });

  assert.equal(result.score, 10);
});

test("supports configurable BoS age and follow-through thresholds", () => {
  const structure = {
    type: "BOS",
    direction: "BULLISH",
    price: 100,
    time: 0,
    timeframe: "M15",
    status: "ACCEPTED",
  };
  const currentCandle = { ...bullishCandle, time: 5 * 15 * 60, close: 101.2 };

  assert.equal(evaluateStructureStrength({
    direction: "BUY",
    currentCandle,
    atr: 2,
    structure,
  }).score, 10);
  assert.equal(evaluateStructureStrength({
    direction: "BUY",
    currentCandle,
    atr: 2,
    structure,
    config: { maximumStructureAgeCandles: 6, bosFollowThroughAtr: 0.75 },
  }).score, 22);
  assert.equal(evaluateStructureStrength({
    direction: "BUY",
    currentCandle,
    atr: 2,
    structure,
    config: { maximumStructureAgeCandles: null, bosFollowThroughAtr: 0.5 },
  }).score, 30);
});