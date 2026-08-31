import assert from "node:assert/strict";
import test from "node:test";

import { evaluateContinuationStrength } from "../continuation-strength.ts";

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
      { ...bullishCandle, time: 60, volume: 100 },
      { ...bullishCandle, time: 90, volume: 110 },
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

  assert.equal(result.score, 0);
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
      { ...bullishCandle, time: 60, volume: 100 },
      { ...bullishCandle, time: 90, volume: 110 },
    ],
    atr: 2,
    structureAligned: true,
  });

  assert.equal(result.score, 100);
  assert.equal(result.status, "STRONG");
});