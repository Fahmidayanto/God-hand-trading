import assert from "node:assert/strict";
import test from "node:test";

test("replay follows the newest candle and restores price autoscale", async () => {
  let followReplayPlayhead;
  try {
    ({ followReplayPlayhead } = await import("../replay-chart.ts"));
  } catch {
    // The first TDD run intentionally reaches this path until the helper exists.
  }

  assert.equal(typeof followReplayPlayhead, "function");

  const priceScaleOptions = [];
  let scrollCalls = 0;
  const chart = {
    priceScale: (id) => {
      assert.equal(id, "right");
      return { applyOptions: (options) => priceScaleOptions.push(options) };
    },
    timeScale: () => ({ scrollToRealTime: () => { scrollCalls += 1; } }),
  };

  followReplayPlayhead(chart);

  assert.deepEqual(priceScaleOptions, [{ autoScale: true }]);
  assert.equal(scrollCalls, 1);
});
