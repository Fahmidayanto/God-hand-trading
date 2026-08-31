import assert from "node:assert/strict";
import test from "node:test";

import { evaluateExitTargetObserver } from "../exit-target-observer.ts";

const baseInput = {
  continuationStatus: "NEUTRAL",
  continuationScore: 50,
  floatingNetProfit: 10,
  maxFavorablePoints: 300,
  maxAdversePoints: 100,
  protectEnabled: true,
  protectTriggerPoints: 500,
  isBreakevenActive: false,
  isTargetMaxed: false,
  expansionCount: 0,
  holdSeconds: 3600,
  maxHoldSeconds: 86400,
  structureAligned: true,
};

test("forces an exit alert when maximum hold is reached", () => {
  const result = evaluateExitTargetObserver({ ...baseInput, holdSeconds: 86400 });
  assert.equal(result.status, "FORCE_EXIT_ALERT");
});

test("raises an exit alert for weak continuation and broken structure", () => {
  const result = evaluateExitTargetObserver({
    ...baseInput,
    continuationStatus: "WEAK",
    continuationScore: 20,
    floatingNetProfit: -25,
    structureAligned: false,
  });
  assert.equal(result.status, "EXIT_ALERT");
});

test("protects meaningful floating profit before extending target", () => {
  const result = evaluateExitTargetObserver({
    ...baseInput,
    continuationStatus: "STRONG",
    continuationScore: 85,
    floatingNetProfit: 60,
    maxFavorablePoints: 700,
    structureAligned: true,
  });
  assert.equal(result.status, "PROTECT");
});

test("does not protect when Otak 1 protect and trailing is disabled", () => {
  const result = evaluateExitTargetObserver({
    ...baseInput,
    continuationStatus: "STRONG",
    continuationScore: 85,
    floatingNetProfit: 60,
    maxFavorablePoints: 700,
    protectEnabled: false,
    structureAligned: true,
  });
  assert.equal(result.status, "EXTEND");
});

test("extends target only for strong aligned continuation", () => {
  const result = evaluateExitTargetObserver({
    ...baseInput,
    continuationStatus: "STRONG",
    continuationScore: 85,
    floatingNetProfit: 40,
    structureAligned: true,
  });
  assert.equal(result.status, "EXTEND");
});

test("holds when no higher-priority action is present", () => {
  const result = evaluateExitTargetObserver(baseInput);
  assert.equal(result.status, "HOLD");
});
