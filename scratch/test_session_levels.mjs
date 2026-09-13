import test from 'node:test';
import assert from 'node:assert/strict';

// Logika fungsi calculateSessionLiquidityLevels yang independen untuk verifikasi
function calculateSessionLiquidityLevels(currentCandle, allCandles) {
  if (!currentCandle || !allCandles || allCandles.length === 0) return [];
  const cutoffTime = currentCandle.time - 7 * 86400;
  
  let startIdx = 0;
  let lo = 0;
  let hi = allCandles.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (allCandles[mid].time >= cutoffTime) {
      startIdx = mid;
      hi = mid - 1;
    } else {
      lo = mid + 1;
    }
  }

  const sessionBuckets = new Map();
  let currIdx = startIdx;
  const totalCandles = allCandles.length;

  while (currIdx < totalCandles && allCandles[currIdx].time <= currentCandle.time) {
    const c = allCandles[currIdx];
    const d = new Date(c.time * 1000);
    const hour = d.getUTCHours();
    const dayKey = d.toISOString().slice(0, 10);

    let sess = null;
    let typeH = "ASIA_H";
    let typeL = "ASIA_L";

    if (hour >= 0 && hour < 8) {
      sess = "ASIA";
      typeH = "ASIA_H";
      typeL = "ASIA_L";
    } else if (hour >= 8 && hour < 14) {
      sess = "LON";
      typeH = "LON_H";
      typeL = "LON_L";
    } else if (hour >= 14 && hour < 21) {
      sess = "NY";
      typeH = "NY_H";
      typeL = "NY_L";
    }

    if (sess) {
      const bucketKey = `${dayKey}_${sess}`;
      let bucket = sessionBuckets.get(bucketKey);
      if (!bucket) {
        bucket = {
          session: sess,
          typeH,
          typeL,
          dayKey,
          startTime: c.time,
          sessionEndTime: c.time,
          high: c.high,
          low: c.low,
        };
        sessionBuckets.set(bucketKey, bucket);
      } else {
        if (c.high > bucket.high) bucket.high = c.high;
        if (c.low < bucket.low) bucket.low = c.low;
        bucket.sessionEndTime = c.time;
      }
    }
    currIdx++;
  }

  const results = [];
  sessionBuckets.forEach((bucket) => {
    const currD = new Date(currentCandle.time * 1000);
    const currDayKey = currD.toISOString().slice(0, 10);

    let projEndTime = currentCandle.time;
    if (bucket.dayKey < currDayKey) {
      let scan = startIdx;
      while (scan < totalCandles) {
        const sc = allCandles[scan];
        const scDay = new Date(sc.time * 1000).toISOString().slice(0, 10);
        if (scDay === bucket.dayKey) {
          projEndTime = sc.time;
        } else if (scDay > bucket.dayKey) {
          break;
        }
        scan++;
      }
    }

    let maxHighAfter = -Infinity;
    let minLowAfter = Infinity;
    let hasBrokenH = false;
    let hasBrokenL = false;

    let evalIdx = startIdx;
    while (evalIdx < totalCandles && allCandles[evalIdx].time <= projEndTime) {
      const ec = allCandles[evalIdx];
      if (ec.time > bucket.sessionEndTime) {
        if (ec.high > maxHighAfter) maxHighAfter = ec.high;
        if (ec.low < minLowAfter) minLowAfter = ec.low;
        if (ec.close >= bucket.high) hasBrokenH = true;
        if (ec.close <= bucket.low) hasBrokenL = true;
      }
      evalIdx++;
    }

    let statusH = "UNTOUCHED";
    if (hasBrokenH) {
      statusH = "BROKEN";
    } else if (maxHighAfter >= bucket.high) {
      statusH = "SWEPT";
    }

    let statusL = "UNTOUCHED";
    if (hasBrokenL) {
      statusL = "BROKEN";
    } else if (minLowAfter <= bucket.low) {
      statusL = "SWEPT";
    }

    results.push(
      {
        id: `${bucket.typeH}-${bucket.startTime}-${bucket.high.toFixed(2)}`,
        type: bucket.typeH,
        price: bucket.high,
        startTime: bucket.startTime,
        endTime: projEndTime,
        status: statusH,
        label: `${bucket.session} H ${bucket.high.toFixed(2)}`,
        periodLabel: bucket.session,
      },
      {
        id: `${bucket.typeL}-${bucket.startTime}-${bucket.low.toFixed(2)}`,
        type: bucket.typeL,
        price: bucket.low,
        startTime: bucket.startTime,
        endTime: projEndTime,
        status: statusL,
        label: `${bucket.session} L ${bucket.low.toFixed(2)}`,
        periodLabel: bucket.session,
      }
    );
  });

  return results;
}

test('detects Asia, London, NY levels with correct status transitions', () => {
  // Base date: 2026-03-10 00:00:00 UTC (1773091200)
  const baseTime = Date.UTC(2026, 2, 10, 0, 0, 0) / 1000;

  const candles = [
    // Asia Session (02:00 UTC)
    { time: baseTime + 2 * 3600, open: 2600, high: 2620, low: 2595, close: 2610 },
    // Asia Session (05:00 UTC) - sets session high and low
    { time: baseTime + 5 * 3600, open: 2610, high: 2630, low: 2590, close: 2615 },
    // London Session (09:00 UTC) - sweeps Asia High (wick 2632, close 2625)
    { time: baseTime + 9 * 3600, open: 2615, high: 2632, low: 2610, close: 2625 },
    // London Session (12:00 UTC) - sets London High 2640
    { time: baseTime + 12 * 3600, open: 2625, high: 2640, low: 2620, close: 2635 },
    // NY Session (15:00 UTC) - breaks London High (close 2645 >= 2640)
    { time: baseTime + 15 * 3600, open: 2635, high: 2650, low: 2630, close: 2645 },
  ];

  // 1. Evaluasi pada jam 09:00 London (setelah wick sweep Asia High)
  const levelsAtLonOpen = calculateSessionLiquidityLevels(candles[2], candles);
  const asiaHAtLonOpen = levelsAtLonOpen.find(l => l.type === 'ASIA_H');
  assert.equal(asiaHAtLonOpen.price, 2630);
  assert.equal(asiaHAtLonOpen.status, 'SWEPT'); // Disapu wick 2632 pada London 09:00 (close 2625 < 2630)

  // 2. Evaluasi pada jam 15:00 NY (setelah candle 12:00 close 2635 menembus 2630)
  const levelsAtNY = calculateSessionLiquidityLevels(candles[4], candles);
  assert.equal(levelsAtNY.length, 6); // 2 Asia + 2 Lon + 2 NY

  const asiaH = levelsAtNY.find(l => l.type === 'ASIA_H');
  const asiaL = levelsAtNY.find(l => l.type === 'ASIA_L');
  const lonH = levelsAtNY.find(l => l.type === 'LON_H');
  const lonL = levelsAtNY.find(l => l.type === 'LON_L');
  const nyH = levelsAtNY.find(l => l.type === 'NY_H');

  assert.equal(asiaH.price, 2630);
  assert.equal(asiaH.status, 'BROKEN'); // Ditutup tembus oleh candle 12:00 (close 2635)

  assert.equal(asiaL.price, 2590);
  assert.equal(asiaL.status, 'UNTOUCHED');

  assert.equal(lonH.price, 2640);
  assert.equal(lonH.status, 'BROKEN'); // Ditutup tembus close 2645 pada NY 15:00

  assert.equal(nyH.price, 2650);
  assert.equal(nyH.status, 'UNTOUCHED');
});
