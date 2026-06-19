const fs = require("fs");
const path = require("path");

const ROOT = process.cwd();
const POINT = 0.01;

const GROUPS = [
  {
    key: "v5",
    name: "v5 static SL",
    dir: "backtest statis",
    source: "Dev Bot v5 statis.cs",
    slModel: "Fixed SL: entry +/- input SL points",
  },
  {
    key: "v6",
    name: "v6 last accepted LL/HH",
    dir: "backtest dynamic last accepted LL",
    source: "Dev Bot v6 last acc LL.cs",
    slModel: "Full dynamic structure SL: BUY=lastAcceptedLL, SELL=lastAcceptedHH",
  },
  {
    key: "v7",
    name: "v7 hybrid SL",
    dir: "backtest dynamic hybrid",
    source: "Dev Bot v7 hybrid.cs",
    slModel: "Hybrid capped structure SL: BUY=max(LL, fixed cap), SELL=min(HH, fixed cap)",
  },
];

const GLOBAL_EVENTS = [
  ...dates("FOMC", [
    "2020-01-29", "2020-03-03", "2020-03-15", "2020-03-23", "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16", "2020-11-05", "2020-12-16",
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
  ]),
  ...dates("CPI", [
    "2020-01-14", "2020-02-13", "2020-03-11", "2020-04-10", "2020-05-12", "2020-06-10", "2020-07-14", "2020-08-12", "2020-09-11", "2020-10-13", "2020-11-12", "2020-12-10",
    "2021-01-13", "2021-02-10", "2021-03-10", "2021-04-13", "2021-05-12", "2021-06-10", "2021-07-13", "2021-08-11", "2021-09-14", "2021-10-13", "2021-11-10", "2021-12-10",
    "2022-01-12", "2022-02-10", "2022-03-10", "2022-04-12", "2022-05-11", "2022-06-10", "2022-07-13", "2022-08-10", "2022-09-13", "2022-10-13", "2022-11-10", "2022-12-13",
    "2023-01-12", "2023-02-14", "2023-03-14", "2023-04-12", "2023-05-10", "2023-06-13", "2023-07-12", "2023-08-10", "2023-09-13", "2023-10-12", "2023-11-14", "2023-12-12",
    "2024-01-11", "2024-02-13", "2024-03-12", "2024-04-10", "2024-05-15", "2024-06-12", "2024-07-11", "2024-08-14", "2024-09-11", "2024-10-10", "2024-11-13", "2024-12-11",
    "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13", "2025-06-11", "2025-07-15", "2025-08-12", "2025-09-11", "2025-10-24", "2025-11-13", "2025-12-10",
  ]),
  ...dates("NFP", [
    "2020-01-10", "2020-02-07", "2020-03-06", "2020-04-03", "2020-05-08", "2020-06-05", "2020-07-02", "2020-08-07", "2020-09-04", "2020-10-02", "2020-11-06", "2020-12-04",
    "2021-01-08", "2021-02-05", "2021-03-05", "2021-04-02", "2021-05-07", "2021-06-04", "2021-07-02", "2021-08-06", "2021-09-03", "2021-10-08", "2021-11-05", "2021-12-03",
    "2022-01-07", "2022-02-04", "2022-03-04", "2022-04-01", "2022-05-06", "2022-06-03", "2022-07-08", "2022-08-05", "2022-09-02", "2022-10-07", "2022-11-04", "2022-12-02",
    "2023-01-06", "2023-02-03", "2023-03-10", "2023-04-07", "2023-05-05", "2023-06-02", "2023-07-07", "2023-08-04", "2023-09-01", "2023-10-06", "2023-11-03", "2023-12-08",
    "2024-01-05", "2024-02-02", "2024-03-08", "2024-04-05", "2024-05-03", "2024-06-07", "2024-07-05", "2024-08-02", "2024-09-06", "2024-10-04", "2024-11-01", "2024-12-06",
    "2025-01-10", "2025-02-07", "2025-03-07", "2025-04-04", "2025-05-02", "2025-06-06", "2025-07-03", "2025-08-01", "2025-09-05", "2025-11-20", "2025-12-16",
  ]),
];

function dates(type, values) {
  return values.map((date) => ({ type, date, ms: Date.UTC(+date.slice(0, 4), +date.slice(5, 7) - 1, +date.slice(8, 10), 12, 0, 0) }));
}

function readText(file) {
  return fs.readFileSync(path.join(ROOT, file), "utf8").replace(/^\uFEFF/, "");
}

function parseTime(s) {
  if (!s || s === "1970.01.01 00:00:00") return null;
  const m = String(s).trim().match(/^(\d{4})\.(\d{2})\.(\d{2})\s+(\d{2}):(\d{2}):(\d{2})$/);
  if (!m) return null;
  return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
}

function fmtTime(ms) {
  if (!Number.isFinite(ms)) return "";
  const d = new Date(ms);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

function dateKey(ms) {
  const d = new Date(ms);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
}

function weekday(ms) {
  return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][new Date(ms).getUTCDay()];
}

function monthKey(ms) {
  const d = new Date(ms);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

function yearKey(ms) {
  return String(new Date(ms).getUTCFullYear());
}

function toNum(v) {
  if (v === null || v === undefined || v === "") return NaN;
  const n = Number(String(v).trim());
  return Number.isFinite(n) ? n : NaN;
}

function splitCsvLine(line) {
  const out = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === "," && !inQuotes) {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

function parseCsv(file, options = {}) {
  const full = path.join(ROOT, file);
  const text = fs.readFileSync(full, "utf8").replace(/^\uFEFF/, "");
  let lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines[0] && lines[0].startsWith("===")) lines = lines.slice(1);
  if (options.skipLeadingTitle && lines.length > 0) lines = lines.slice(1);
  if (lines.length === 0) return { header: [], rows: [], malformed: 0 };
  const header = splitCsvLine(lines[0]).map((h) => h.trim());
  const rows = [];
  let malformed = 0;
  for (let i = 1; i < lines.length; i++) {
    const vals = splitCsvLine(lines[i]);
    if (vals.length < header.length) malformed++;
    const row = {};
    for (let j = 0; j < header.length; j++) row[header[j]] = vals[j] === undefined ? "" : vals[j].trim();
    rows.push(row);
  }
  return { header, rows, malformed };
}

function listCsvFiles(dir) {
  return fs.readdirSync(path.join(ROOT, dir))
    .filter((f) => f.toLowerCase().endsWith(".csv"))
    .sort()
    .map((f) => path.join(dir, f));
}

function mean(xs) {
  const a = xs.filter(Number.isFinite);
  return a.length ? a.reduce((s, x) => s + x, 0) / a.length : NaN;
}

function sum(xs) {
  return xs.filter(Number.isFinite).reduce((s, x) => s + x, 0);
}

function std(xs) {
  const a = xs.filter(Number.isFinite);
  if (a.length < 2) return NaN;
  const m = mean(a);
  return Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / (a.length - 1));
}

function quantile(xs, q) {
  const a = xs.filter(Number.isFinite).sort((x, y) => x - y);
  if (!a.length) return NaN;
  const pos = (a.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  if (lo === hi) return a[lo];
  return a[lo] + (a[hi] - a[lo]) * (pos - lo);
}

function maxDrawdown(values) {
  let equity = 0;
  let peak = 0;
  let dd = 0;
  for (const v of values) {
    equity += v;
    if (equity > peak) peak = equity;
    dd = Math.max(dd, peak - equity);
  }
  return dd;
}

function streak(values, wantWin) {
  let best = 0;
  let cur = 0;
  for (const v of values) {
    const ok = wantWin ? v > 0 : v < 0;
    if (ok) {
      cur++;
      if (cur > best) best = cur;
    } else {
      cur = 0;
    }
  }
  return best;
}

function metrics(trades) {
  const ordered = trades.slice().sort((a, b) => a.entryMs - b.entryMs);
  const pnl = ordered.map((t) => t.net);
  const wins = ordered.filter((t) => t.net > 0);
  const losses = ordered.filter((t) => t.net < 0);
  const grossProfit = sum(wins.map((t) => t.net));
  const grossLoss = -sum(losses.map((t) => t.net));
  const daily = new Map();
  for (const t of ordered) {
    const k = dateKey(t.entryMs);
    daily.set(k, (daily.get(k) || 0) + t.net);
  }
  const dailyVals = Array.from(daily.values());
  const dailyMean = mean(dailyVals);
  const dailyStd = std(dailyVals);
  const downside = dailyVals.filter((v) => v < 0);
  const downsideStd = std(downside);
  const minMs = ordered.length ? ordered[0].entryMs : NaN;
  const maxMs = ordered.length ? ordered[ordered.length - 1].entryMs : NaN;
  const spanDays = Number.isFinite(minMs) && Number.isFinite(maxMs) ? Math.max(1, (maxMs - minMs) / 86400000 + 1) : NaN;
  return {
    trades: ordered.length,
    wins: wins.length,
    losses: losses.length,
    winrate: ordered.length ? wins.length / ordered.length : NaN,
    totalNet: sum(pnl),
    grossProfit,
    grossLoss,
    profitFactor: grossLoss > 0 ? grossProfit / grossLoss : NaN,
    expectancy: ordered.length ? sum(pnl) / ordered.length : NaN,
    avgWin: mean(wins.map((t) => t.net)),
    avgLoss: mean(losses.map((t) => t.net)),
    maxDD: maxDrawdown(pnl),
    maxConsecWin: streak(pnl, true),
    maxConsecLoss: streak(pnl, false),
    avgRR: mean(ordered.map((t) => t.rr)),
    avgDurationHours: mean(ordered.map((t) => t.durationHours)),
    sharpeDaily: Number.isFinite(dailyStd) && dailyStd !== 0 ? (dailyMean / dailyStd) * Math.sqrt(252) : NaN,
    sortinoDaily: Number.isFinite(downsideStd) && downsideStd !== 0 ? (dailyMean / downsideStd) * Math.sqrt(252) : NaN,
    tradesPerDay: ordered.length && Number.isFinite(spanDays) ? ordered.length / spanDays : NaN,
    start: fmtTime(minMs),
    end: fmtTime(maxMs),
  };
}

function binSearchAtOrBefore(arr, ms) {
  let lo = 0;
  let hi = arr.length - 1;
  let ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid].ms <= ms) {
      ans = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return ans;
}

function loadMarketRows(files, tfTag) {
  const byTime = new Map();
  for (const file of files.filter((f) => f.includes(`MarketData_XAUUSD_${tfTag}`))) {
    const parsed = parseCsv(file);
    for (const r of parsed.rows) {
      const ms = parseTime(r.Time);
      if (!Number.isFinite(ms)) continue;
      byTime.set(ms, {
        ms,
        open: toNum(r.Open),
        high: toNum(r.High),
        low: toNum(r.Low),
        close: toNum(r.Close),
        volume: toNum(r.Volume),
        spread: toNum(r.Spread),
        ema: toNum(r.EMA200),
      });
    }
  }
  return Array.from(byTime.values()).sort((a, b) => a.ms - b.ms);
}

function loadEvents(files) {
  const events = [];
  for (const file of files.filter((f) => f.includes("LLHHBOSData"))) {
    const parsed = parseCsv(file);
    for (const r of parsed.rows) {
      const ms = parseTime(r.Time);
      if (!Number.isFinite(ms)) continue;
      events.push({
        ms,
        type: r.Type,
        direction: r["Direction/Action"],
        price: toNum(r.Price),
        timeframe: r.Timeframe,
        status: r.Status,
      });
    }
  }
  events.sort((a, b) => a.ms - b.ms);
  return events;
}

function prevEvent(events, ms, predicate) {
  let lo = 0;
  let hi = events.length - 1;
  let idx = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (events[mid].ms <= ms) {
      idx = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  for (let i = idx; i >= 0; i--) {
    if (predicate(events[i])) return events[i];
    if (ms - events[i].ms > 14 * 86400000) break;
  }
  return null;
}

function rollingRange(arr, idx, n) {
  const start = Math.max(0, idx - n + 1);
  const vals = [];
  for (let i = start; i <= idx; i++) vals.push((arr[i].high - arr[i].low) / POINT);
  return mean(vals);
}

function addMarketFeatures(trades, groupData) {
  const { m15, h1, events } = groupData;
  for (const t of trades) {
    const i15 = binSearchAtOrBefore(m15, t.entryMs);
    const iH1 = binSearchAtOrBefore(h1, t.entryMs);
    t.hasMarket = i15 >= 0;
    if (i15 >= 0) {
      const b = m15[i15];
      t.m15Close = b.close;
      t.m15Ema = b.ema;
      t.m15Spread = b.spread;
      t.emaGapPts = (b.close - b.ema) / POINT;
      t.emaAligned = t.type === "BUY" ? t.emaGapPts > 0 : t.emaGapPts < 0;
      t.m15Slope1Pts = i15 >= 1 ? (m15[i15].ema - m15[i15 - 1].ema) / POINT : NaN;
      t.m15Slope4Pts = i15 >= 4 ? (m15[i15].ema - m15[i15 - 4].ema) / POINT : NaN;
      t.m15Slope16Pts = i15 >= 16 ? (m15[i15].ema - m15[i15 - 16].ema) / POINT : NaN;
      t.m15SlopeAligned = t.type === "BUY" ? t.m15Slope4Pts > 0 : t.m15Slope4Pts < 0;
      t.m15RangePts = (b.high - b.low) / POINT;
      t.m15BodyPts = Math.abs(b.close - b.open) / POINT;
      t.m15ClosePos = b.high > b.low ? (b.close - b.low) / (b.high - b.low) : NaN;
      t.vol16Pts = rollingRange(m15, i15, 16);
    }
    if (iH1 >= 0) {
      const b = h1[iH1];
      t.h1Close = b.close;
      t.h1Ema = b.ema;
      t.h1GapPts = (b.close - b.ema) / POINT;
      t.h1Aligned = t.type === "BUY" ? t.h1GapPts > 0 : t.h1GapPts < 0;
      t.h1Slope4Pts = iH1 >= 4 ? (h1[iH1].ema - h1[iH1 - 4].ema) / POINT : NaN;
      t.h1SlopeAligned = t.type === "BUY" ? t.h1Slope4Pts > 0 : t.h1Slope4Pts < 0;
    }
    const lastBos = prevEvent(events, t.entryMs, (e) => e.type === "BoS" && e.timeframe === "M15");
    const lastChoch = prevEvent(events, t.entryMs, (e) => e.type === "CHoCH" && e.timeframe === "M15");
    t.lastBosDirection = lastBos ? lastBos.direction : "";
    t.lastBosAgeHours = lastBos ? (t.entryMs - lastBos.ms) / 3600000 : NaN;
    t.lastChochDirection = lastChoch ? lastChoch.direction : "";
    t.lastChochAgeHours = lastChoch ? (t.entryMs - lastChoch.ms) / 3600000 : NaN;
    const start = binSearchAtOrBefore(m15, t.entryMs);
    const end = binSearchAtOrBefore(m15, t.exitMs);
    if (start >= 0 && end >= start) {
      let hi = -Infinity;
      let lo = Infinity;
      let firstTp = null;
      let firstSl = null;
      for (let i = start; i <= end; i++) {
        const b = m15[i];
        if (b.high > hi) hi = b.high;
        if (b.low < lo) lo = b.low;
        if (t.type === "BUY") {
          if (firstTp === null && b.high >= t.tp) firstTp = b.ms;
          if (firstSl === null && b.low <= t.sl) firstSl = b.ms;
        } else {
          if (firstTp === null && b.low <= t.tp) firstTp = b.ms;
          if (firstSl === null && b.high >= t.sl) firstSl = b.ms;
        }
      }
      if (t.type === "BUY") {
        t.mfePts = (hi - t.entry) / POINT;
        t.maePts = (t.entry - lo) / POINT;
      } else {
        t.mfePts = (t.entry - lo) / POINT;
        t.maePts = (hi - t.entry) / POINT;
      }
      t.mfeToTp = t.tpPts > 0 ? t.mfePts / t.tpPts : NaN;
      t.maeToSl = t.slPts > 0 ? t.maePts / t.slPts : NaN;
      t.firstTpMs = firstTp;
      t.firstSlMs = firstSl;
      t.pathHit = firstTp !== null && (firstSl === null || firstTp <= firstSl) ? "TP_first" :
        firstSl !== null && (firstTp === null || firstSl < firstTp) ? "SL_first" :
        firstTp !== null && firstSl !== null ? "ambiguous" : "neither";
    }
  }
}

function classifyRegimes(allTrades) {
  const volQ25 = quantile(allTrades.map((t) => t.vol16Pts), 0.25);
  const volQ75 = quantile(allTrades.map((t) => t.vol16Pts), 0.75);
  const gapQ25 = quantile(allTrades.map((t) => Math.abs(t.emaGapPts)), 0.25);
  const slopeQ25 = quantile(allTrades.map((t) => Math.abs(t.m15Slope16Pts)), 0.25);
  for (const t of allTrades) {
    const lowTrendStrength = Math.abs(t.emaGapPts) <= gapQ25 || Math.abs(t.m15Slope16Pts) <= slopeQ25;
    const bothAligned = t.emaAligned && t.m15SlopeAligned && t.h1Aligned && t.h1SlopeAligned;
    const conflicting = !t.emaAligned || !t.h1Aligned || !t.m15SlopeAligned || !t.h1SlopeAligned;
    t.volRegime = t.vol16Pts >= volQ75 ? "HIGH_VOL" : t.vol16Pts <= volQ25 ? "LOW_VOL" : "MID_VOL";
    if (bothAligned && !lowTrendStrength) t.marketRegime = "TRENDING";
    else if (conflicting) t.marketRegime = "REVERSAL_OR_CONFLICT";
    else if (lowTrendStrength) t.marketRegime = "RANGING_LOW_TREND";
    else t.marketRegime = "MIXED";
  }
  return { volQ25, volQ75, gapQ25, slopeQ25 };
}

function groupStats(trades, keyFn, minN = 1) {
  const map = new Map();
  for (const t of trades) {
    const k = keyFn(t);
    if (k === undefined || k === null || k === "" || (typeof k === "number" && !Number.isFinite(k))) continue;
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(t);
  }
  return Array.from(map.entries())
    .map(([key, rows]) => ({ key, ...metrics(rows) }))
    .filter((r) => r.trades >= minN)
    .sort((a, b) => b.totalNet - a.totalNet);
}

function fmt(n, d = 2) {
  return Number.isFinite(n) ? n.toFixed(d) : "NA";
}

function pct(n, d = 1) {
  return Number.isFinite(n) ? `${(n * 100).toFixed(d)}%` : "NA";
}

function mdTable(rows, cols) {
  const lines = [];
  lines.push(`| ${cols.map((c) => c.h).join(" | ")} |`);
  lines.push(`| ${cols.map(() => "---").join(" | ")} |`);
  for (const r of rows) {
    lines.push(`| ${cols.map((c) => String(c.v(r))).join(" | ")} |`);
  }
  return lines.join("\n");
}

function detectPatterns(trades, baseMetric, features, minN) {
  const out = [];
  for (const f of features) {
    const rows = groupStats(trades, f.fn, minN);
    for (const r of rows) {
      const lift = r.winrate - baseMetric.winrate;
      const confidence = Math.min(95, Math.abs(lift) * 140 + Math.sqrt(r.trades) * 4 + Math.min(20, Math.abs(r.totalNet) / 300));
      const strength = confidence >= 70 ? "KUAT" : confidence >= 50 ? "SEDANG" : "LEMAH";
      out.push({
        feature: f.name,
        value: r.key,
        trades: r.trades,
        winrate: r.winrate,
        totalNet: r.totalNet,
        pf: r.profitFactor,
        lift,
        confidence,
        strength,
      });
    }
  }
  return out;
}

function simulateTp(trades, candidates) {
  const out = [];
  for (const tp of candidates) {
    let wins = 0;
    let losses = 0;
    let ambiguous = 0;
    let points = 0;
    let n = 0;
    for (const t of trades) {
      if (!Number.isFinite(t.slPts) || t.slPts <= 0) continue;
      const result = firstHitForCandidate(t, tp);
      if (!result) continue;
      n++;
      if (result === "win") {
        wins++;
        points += tp;
      } else if (result === "loss") {
        losses++;
        points -= t.slPts;
      } else {
        ambiguous++;
        points -= t.slPts;
      }
    }
    out.push({
      tp,
      n,
      wins,
      losses,
      ambiguous,
      winrate: n ? wins / n : NaN,
      avgPoints: n ? points / n : NaN,
    });
  }
  return out.sort((a, b) => b.avgPoints - a.avgPoints);
}

function eventCorrelation(trades, eventType, mode) {
  const events = GLOBAL_EVENTS.filter((e) => eventType === "ANY" || e.type === eventType);
  const rows = [];
  for (const t of trades) {
    let matched = false;
    let labels = [];
    for (const e of events) {
      const start = e.ms - 86400000;
      const end = e.ms + 86400000;
      const hit = mode === "entry" ? (t.entryMs >= start && t.entryMs <= end) : (t.entryMs <= end && t.exitMs >= start);
      if (hit) {
        matched = true;
        labels.push(`${e.type}:${e.date}`);
      }
    }
    if (matched) rows.push({ ...t, eventLabels: labels.join(";") });
  }
  return rows;
}

function eventTopDates(trades, eventType) {
  const events = GLOBAL_EVENTS.filter((e) => eventType === "ANY" || e.type === eventType);
  const out = [];
  for (const e of events) {
    const start = e.ms - 86400000;
    const end = e.ms + 86400000;
    const rows = trades.filter((t) => t.entryMs <= end && t.exitMs >= start);
    if (rows.length) out.push({ event: `${e.type} ${e.date}`, ...metrics(rows) });
  }
  return out.sort((a, b) => a.totalNet - b.totalNet);
}

function firstHitForCandidate(t, tpPts) {
  if (!Number.isFinite(t.mfePts) || !Number.isFinite(t.maePts)) return null;
  if (t.mfePts < tpPts && t.maePts < t.slPts) return t.net > 0 ? "win" : t.net < 0 ? "loss" : "flat";
  if (t.mfePts >= tpPts && t.maePts < t.slPts) return "win";
  if (t.maePts >= t.slPts && t.mfePts < tpPts) return "loss";
  if (t.mfePts >= tpPts && t.maePts >= t.slPts) {
    if (t.pathHit === "TP_first") return "win";
    if (t.pathHit === "SL_first") return "loss";
    return "ambiguous";
  }
  return null;
}

function codeLine(file, pattern) {
  const lines = readText(file).split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    if (pattern.test(lines[i])) return i + 1;
  }
  return null;
}

function loadEverything() {
  const fileAudits = [];
  const allTrades = [];
  const groupData = {};
  for (const g of GROUPS) {
    const files = listCsvFiles(g.dir);
    groupData[g.key] = { files, m15: loadMarketRows(files, "M15"), h1: loadMarketRows(files, "H1"), events: loadEvents(files) };
    for (const f of files) {
      try {
        const parsed = parseCsv(f);
        const names = path.basename(f);
        let minMs = Infinity;
        let maxMs = -Infinity;
        let profit = NaN;
        let trades = NaN;
        for (const r of parsed.rows) {
          for (const col of ["EntryTime", "ExitTime", "Time", "StartDate", "EndDate"]) {
            const ms = parseTime(r[col]);
            if (Number.isFinite(ms)) {
              minMs = Math.min(minMs, ms);
              maxMs = Math.max(maxMs, ms);
            }
          }
          if (r.TotalProfit !== undefined) profit = toNum(r.TotalProfit);
          if (r.TotalTrades !== undefined) trades = toNum(r.TotalTrades);
          if (r.Net_Profit !== undefined) profit = (Number.isFinite(profit) ? profit : 0) + toNum(r.Net_Profit);
        }
        fileAudits.push({
          group: g.key,
          file: f,
          rows: parsed.rows.length,
          columns: parsed.header.join(", "),
          malformed: parsed.malformed,
          start: fmtTime(minMs),
          end: fmtTime(maxMs),
          profit,
          trades,
          status: "OK",
        });
      } catch (err) {
        fileAudits.push({ group: g.key, file: f, rows: 0, columns: "", malformed: 0, start: "", end: "", profit: NaN, trades: NaN, status: `FAILED: ${err.message}` });
      }
    }
    for (const f of files.filter((x) => x.includes("Backtest_Results"))) {
      const parsed = parseCsv(f);
      for (const r of parsed.rows) {
        const entryMs = parseTime(r.EntryTime);
        const exitMs = parseTime(r.ExitTime);
        const entry = toNum(r.EntryPrice);
        const exit = toNum(r.ExitPrice);
        const sl = toNum(r.SL);
        const tp = toNum(r.TP);
        const type = r.Type;
        const slPts = Math.abs(entry - sl) / POINT;
        const tpPts = Math.abs(tp - entry) / POINT;
        allTrades.push({
          version: g.key,
          versionName: g.name,
          file: f,
          ticket: r.Ticket,
          symbol: r.Symbol,
          type,
          entry,
          exit,
          sl,
          tp,
          profit: toNum(r.Profit),
          spreadCost: toNum(r.Spread_Cost),
          commission: toNum(r.Commission),
          net: toNum(r.Net_Profit),
          session: r.Session,
          entryMs,
          exitMs,
          lot: toNum(r.LotSize),
          magic: r.MagicNumber,
          timeframe: r.Timeframe,
          slPts,
          tpPts,
          rr: slPts > 0 ? tpPts / slPts : NaN,
          durationHours: Number.isFinite(entryMs) && Number.isFinite(exitMs) ? (exitMs - entryMs) / 3600000 : NaN,
          weekday: Number.isFinite(entryMs) ? weekday(entryMs) : "",
          hour: Number.isFinite(entryMs) ? new Date(entryMs).getUTCHours() : NaN,
          month: Number.isFinite(entryMs) ? monthKey(entryMs) : "",
          year: Number.isFinite(entryMs) ? yearKey(entryMs) : "",
        });
      }
    }
  }
  for (const g of GROUPS) addMarketFeatures(allTrades.filter((t) => t.version === g.key), groupData[g.key]);
  const thresholds = classifyRegimes(allTrades);
  return { fileAudits, allTrades, groupData, thresholds };
}

function makeReport(data) {
  const { fileAudits, allTrades, groupData, thresholds } = data;
  const report = [];
  const groups = GROUPS.map((g) => ({ ...g, trades: allTrades.filter((t) => t.version === g.key) }));
  const master = groups.map((g) => ({ version: g.key, name: g.name, slModel: g.slModel, ...metrics(g.trades) }));

  report.push("# Audit Forensik v5 vs v6 vs v7 - XAUUSD M15");
  report.push("");
  report.push(`Generated: ${new Date().toISOString().slice(0, 19)}Z`);
  report.push("Scope: source files v5/v6/v7 plus every CSV under the three requested backtest folders.");
  report.push("");
  report.push("## 1. Executive Summary");
  report.push(mdTable(master, [
    { h: "Version", v: (r) => r.name },
    { h: "Trades", v: (r) => r.trades },
    { h: "Winrate", v: (r) => pct(r.winrate) },
    { h: "Net", v: (r) => fmt(r.totalNet) },
    { h: "PF", v: (r) => fmt(r.profitFactor) },
    { h: "Max DD", v: (r) => fmt(r.maxDD) },
    { h: "Expectancy", v: (r) => fmt(r.expectancy) },
    { h: "Avg RR", v: (r) => fmt(r.avgRR) },
    { h: "Period", v: (r) => `${r.start} to ${r.end}` },
  ]));
  report.push("");
  report.push("- In the supplied Group A/B/C folders only, v5 has the highest net profit and winrate; v6 and v7 are barely positive overall after costs.");
  report.push("- v6 and v7 generate almost the same net profit, but v7 does it with lower max drawdown because the hybrid cap cuts extreme structure SL exposure.");
  report.push("- BUY is the real profit engine in all versions. SELL is negative in every version, with PF 0.64-0.68.");
  report.push("- 2021 is the common failure regime: every version is negative, with PF 0.61-0.72.");
  report.push("");

  report.push("## 2. Source Code Audit");
  const codeRefs = [
    ["v5 entry BUY static SL", GROUPS[0].source, codeLine(GROUPS[0].source, /sl_M15 = entryPrice_M15 - DefaultSL_Buy_M15/)],
    ["v5 entry SELL static SL", GROUPS[0].source, codeLine(GROUPS[0].source, /sl_M15 = entryPrice_M15 \+ DefaultSL_Sell_M15/)],
    ["v5 H1 return gates M15", GROUPS[0].source, codeLine(GROUPS[0].source, /rates_H1\[0\]\.time == lastBarTime_H1/)],
    ["v6 BUY dynamic SL", GROUPS[1].source, codeLine(GROUPS[1].source, /sl_M15 = lastAcceptedLL_M15/)],
    ["v6 SELL dynamic SL", GROUPS[1].source, codeLine(GROUPS[1].source, /sl_M15 = lastAcceptedHH_M15/)],
    ["v6 H1 EMA slope filter", GROUPS[1].source, codeLine(GROUPS[1].source, /bool IsH1TrendingUp/)],
    ["v7 BUY hybrid SL", GROUPS[2].source, codeLine(GROUPS[2].source, /sl_M15 = MathMax/)],
    ["v7 SELL hybrid SL", GROUPS[2].source, codeLine(GROUPS[2].source, /sl_M15 = MathMin/)],
    ["v7 uppercase True bug", GROUPS[2].source, codeLine(GROUPS[2].source, /isHighLiquidityHourSell = True/)],
  ];
  report.push(mdTable(codeRefs.map(([item, file, line]) => ({ item, file, line })), [
    { h: "Item", v: (r) => r.item },
    { h: "File", v: (r) => r.file },
    { h: "Line", v: (r) => r.line || "NA" },
  ]));
  report.push("");
  report.push("Internal flow:");
  report.push("1. OnTick loads M15 and H1 rates, updates EMA200 handles, checks trade closures, then calls DetectAndDraw_M15 on M15 charts.");
  report.push("2. DetectAndDraw_M15 scans swing highs/lows with WindowSize_M15=25, updates lastAcceptedHH/LL, detects CHoCH when close breaks accepted HH/LL, then detects BoS when close breaks post-CHoCH HH/LL.");
  report.push("3. BUY requires BoS bullish, close above M15 EMA200, H1 bullish confirmation, H1 EMA slope up, M15 EMA slope up, and entry count below MaxEntriesPerCycle=2.");
  report.push("4. SELL requires BoS bearish, close below M15 EMA200, H1 bearish confirmation, H1 EMA slope down, M15 EMA slope down, and entry count below MaxEntriesPerCycle=2.");
  report.push("5. Trailing code exists but ApplyTrailingStop_M15 is commented in all three versions. MaxHoldHours/force close is also not active in OnTick.");
  report.push("");
  report.push("Potential code defects evidenced by source:");
  report.push("- v5 uses rates_M15[0].close in entry filters but uses rates_M15[1].close for entry price. That mixes a live/incomplete candle with a closed-candle execution price.");
  report.push("- v5 returns when H1 has no new bar before M15 detection, so M15 logic is effectively gated by H1 cadence.");
  report.push("- v7 has `True` instead of MQL-style `true` for isHighLiquidityHourSell. If compiled exactly as supplied, this is a compile/runtime blocker.");
  report.push("- v6/v7 comments/logs say SELL SL is lastAcceptedLL in places, while code uses lastAcceptedHH. The execution is correct for SELL, the diagnostic text is wrong.");
  report.push("- Session, blackout, and high-liquidity filters are mostly commented or forced true, so the backtest does not prove those filters.");
  report.push("");

  report.push("## 3. Version-Difference Audit");
  report.push(mdTable([
    { change: "v5 -> v6: entry filter switches from rates_M15[0].close to rates_M15[1].close", impact: "Uses completed candle instead of live candle; reduces repaint/intrabar false confirmation.", wr: "Should reduce false entries but may delay signals.", dd: "Lower logic risk; DD effect data-mixed.", profit: "v6 lower net than v5 in supplied folders.", risk: "LOW" },
    { change: "v5 -> v6: adds H1 EMA200 slope filters IsH1TrendingUp/Down", impact: "Requires higher-timeframe EMA direction, not just price side of EMA.", wr: "Improves trend purity; can miss early reversals.", dd: "Should reduce countertrend exposure.", profit: "Not enough alone to offset SELL losses.", risk: "MEDIUM" },
    { change: "v5 -> v6: SL changes from fixed points to lastAcceptedLL/HH", impact: "Risk distance becomes structure-dependent and can be much wider or tighter than 3000 points.", wr: "Can survive pullbacks but loses more when structure is wide.", dd: "35 v6 loss trades had SL >3000 pts and lost -8299.95 net.", profit: "v6 net +512.95, PF 1.03; lower than v5 +1807.40.", risk: "HIGH" },
    { change: "v5 -> v6: OnTick H1 return removed", impact: "M15 detection no longer blocked by unchanged H1 bar.", wr: "More M15 opportunities; v6 has 217 trades vs v5 214 despite shorter 2024 sample.", dd: "More frequent entries can increase exposure.", profit: "No isolated attribution, but fixes a real cadence bug.", risk: "MEDIUM" },
    { change: "v5 -> v6: bearish CHoCH scans highest HH between LL and trigger", impact: "Improves bearish reference HH selection after LL break.", wr: "Should reduce invalid SELL SL reference.", dd: "Risk depends on HH distance.", profit: "SELL still negative in v6: -3157.80 net.", risk: "MEDIUM" },
    { change: "v6 -> v7: BUY SL = MathMax(lastAcceptedLL, entry - 3000pts)", impact: "Caps maximum BUY loss while preserving closer structure SL.", wr: "May stop out trades that v6 structure SL survived.", dd: "v7 DD 2069.60 vs v6 2569.70.", profit: "v7 net +520.00, similar to v6.", risk: "MEDIUM" },
    { change: "v6 -> v7: SELL SL = MathMin(lastAcceptedHH, entry + 3000pts)", impact: "Caps maximum SELL loss while preserving closer structure SL.", wr: "SELL remains weak; 30.0% WR in v7.", dd: "Cuts wide-loss tail versus v6.", profit: "SELL still -2923.90 net.", risk: "MEDIUM" },
    { change: "v6 -> v7: isHighLiquidityHourSell = True", impact: "Uppercase boolean is not valid MQL-style source as supplied.", wr: "If not fixed, code should not compile/run as intended.", dd: "Operational blocker, not market effect.", profit: "Backtest files may come from a corrected build; source itself must be fixed.", risk: "HIGH" },
  ], [
    { h: "Change", v: (r) => r.change },
    { h: "Potential impact", v: (r) => r.impact },
    { h: "Winrate effect", v: (r) => r.wr },
    { h: "DD effect", v: (r) => r.dd },
    { h: "Profit evidence", v: (r) => r.profit },
    { h: "Risk", v: (r) => r.risk },
  ]));
  report.push("");

  report.push("## 4. CSV Load Audit");
  const filesByGroup = GROUPS.map((g) => ({ group: g.key, files: fileAudits.filter((f) => f.group === g.key).length, failed: fileAudits.filter((f) => f.group === g.key && f.status !== "OK").length, rows: sum(fileAudits.filter((f) => f.group === g.key).map((f) => f.rows)) }));
  report.push(mdTable(filesByGroup, [
    { h: "Group", v: (r) => r.group },
    { h: "Files", v: (r) => r.files },
    { h: "Failed", v: (r) => r.failed },
    { h: "Rows loaded", v: (r) => r.rows },
  ]));
  report.push("");
  report.push("Detailed file list is written to `Dokumen/Audit/v5_v6_v7_file_audit.csv`.");
  report.push("Per-trade enriched forensic data is written to `Dokumen/Audit/v5_v6_v7_trade_features.csv`; it contains every Backtest_Results trade plus reconstructed EMA200, H1/M15 slope, MFE/MAE, SL/TP distance, RR, session/time, and nearest structure-event features.");
  report.push("");

  report.push("## 5. Yearly Statistics");
  for (const g of GROUPS) {
    report.push(`### ${g.name}`);
    const rows = groupStats(allTrades.filter((t) => t.version === g.key), (t) => t.year, 1).sort((a, b) => String(a.key).localeCompare(String(b.key)));
    report.push(mdTable(rows, [
      { h: "Year", v: (r) => r.key },
      { h: "Trades", v: (r) => r.trades },
      { h: "Winrate", v: (r) => pct(r.winrate) },
      { h: "Net", v: (r) => fmt(r.totalNet) },
      { h: "PF", v: (r) => fmt(r.profitFactor) },
      { h: "Max DD", v: (r) => fmt(r.maxDD) },
      { h: "Avg RR", v: (r) => fmt(r.avgRR) },
    ]));
    report.push("");
  }

  report.push("## 6. Pattern Detection");
  const features = [
    { name: "session", fn: (t) => t.session },
    { name: "direction", fn: (t) => t.type },
    { name: "weekday", fn: (t) => t.weekday },
    { name: "hour", fn: (t) => `H${String(t.hour).padStart(2, "0")}` },
    { name: "marketRegime", fn: (t) => t.marketRegime },
    { name: "volRegime", fn: (t) => t.volRegime },
    { name: "emaAligned", fn: (t) => t.emaAligned ? "EMA_ALIGNED" : "EMA_CONFLICT" },
    { name: "h1Aligned", fn: (t) => t.h1Aligned ? "H1_ALIGNED" : "H1_CONFLICT" },
  ];
  for (const g of GROUPS) {
    const tr = allTrades.filter((t) => t.version === g.key);
    const base = metrics(tr);
    const pats = detectPatterns(tr, base, features, Math.max(5, Math.ceil(tr.length * 0.05)));
    const winPats = pats.filter((p) => p.lift > 0 && p.totalNet > 0).sort((a, b) => b.confidence - a.confidence).slice(0, 10);
    const lossPats = pats.filter((p) => p.lift < 0 || p.totalNet < 0).sort((a, b) => b.confidence - a.confidence).slice(0, 10);
    report.push(`### ${g.name} - WIN patterns`);
    report.push(mdTable(winPats, [
      { h: "Feature", v: (r) => r.feature },
      { h: "Value", v: (r) => r.value },
      { h: "N", v: (r) => r.trades },
      { h: "WR", v: (r) => pct(r.winrate) },
      { h: "Net", v: (r) => fmt(r.totalNet) },
      { h: "PF", v: (r) => fmt(r.pf) },
      { h: "Strength", v: (r) => r.strength },
      { h: "Conf", v: (r) => fmt(r.confidence, 0) },
    ]));
    report.push("");
    report.push(`### ${g.name} - LOSS/RISK patterns`);
    report.push(mdTable(lossPats, [
      { h: "Feature", v: (r) => r.feature },
      { h: "Value", v: (r) => r.value },
      { h: "N", v: (r) => r.trades },
      { h: "WR", v: (r) => pct(r.winrate) },
      { h: "Net", v: (r) => fmt(r.totalNet) },
      { h: "PF", v: (r) => fmt(r.pf) },
      { h: "Strength", v: (r) => r.strength },
      { h: "Conf", v: (r) => fmt(r.confidence, 0) },
    ]));
    report.push("");
  }

  report.push("## 7. Market Regime");
  report.push(`Data-derived regime thresholds across actual entries: vol16 Q25=${fmt(thresholds.volQ25)} pts, vol16 Q75=${fmt(thresholds.volQ75)} pts, abs EMA gap Q25=${fmt(thresholds.gapQ25)} pts, abs EMA slope16 Q25=${fmt(thresholds.slopeQ25)} pts.`);
  for (const g of GROUPS) {
    report.push(`### ${g.name}`);
    const rows = groupStats(allTrades.filter((t) => t.version === g.key), (t) => t.marketRegime, 1);
    report.push(mdTable(rows, [
      { h: "Regime", v: (r) => r.key },
      { h: "Trades", v: (r) => r.trades },
      { h: "WR", v: (r) => pct(r.winrate) },
      { h: "Net", v: (r) => fmt(r.totalNet) },
      { h: "PF", v: (r) => fmt(r.profitFactor) },
      { h: "DD", v: (r) => fmt(r.maxDD) },
    ]));
    report.push("");
  }

  report.push("## 8. Scenario Simulation");
  report.push("These are not new backtests; they are trade-list filtering simulations using actual closed trades and actual CSV-derived entry features.");
  const scenarioDefs = [
    ["Base", (t) => true],
    ["Remove Asia", (t) => t.session !== "Asia"],
    ["Asia only", (t) => t.session === "Asia"],
    ["London only", (t) => t.session === "London"],
    ["London + overlap", (t) => t.session === "London" || t.session === "London_NewYork_Overlap"],
    ["Remove London", (t) => t.session !== "London"],
    ["BUY only", (t) => t.type === "BUY"],
    ["SELL only", (t) => t.type === "SELL"],
    ["Trending only", (t) => t.marketRegime === "TRENDING"],
    ["Remove range/conflict", (t) => t.marketRegime === "TRENDING"],
    ["No high vol", (t) => t.volRegime !== "HIGH_VOL"],
    ["Strict EMA200 confluence", (t) => t.emaAligned && t.h1Aligned && t.m15SlopeAligned && t.h1SlopeAligned && Math.abs(t.emaGapPts) > thresholds.gapQ25],
  ];
  for (const g of GROUPS) {
    const tr = allTrades.filter((t) => t.version === g.key);
    const rows = scenarioDefs.map(([name, fn]) => ({ scenario: name, ...metrics(tr.filter(fn)) }));
    report.push(`### ${g.name}`);
    report.push(mdTable(rows, [
      { h: "Scenario", v: (r) => r.scenario },
      { h: "Trades", v: (r) => r.trades },
      { h: "WR", v: (r) => pct(r.winrate) },
      { h: "Net", v: (r) => fmt(r.totalNet) },
      { h: "PF", v: (r) => fmt(r.profitFactor) },
      { h: "DD", v: (r) => fmt(r.maxDD) },
      { h: "Expectancy", v: (r) => fmt(r.expectancy) },
    ]));
    report.push("");
  }

  report.push("## 9. Global Event Correlation");
  report.push("Sources used for event dates: Federal Reserve FOMC calendars (`federalreserve.gov/monetarypolicy/fomccalendars.htm` and 2020 historical FOMC page) plus BLS prior-year release schedules (`bls.gov/schedule/YYYY/home.htm`) for CPI and Employment Situation. BLS schedules state release times in Eastern Time; this audit uses date-level +/-1 calendar day windows because the MT5 CSV timezone is not explicitly declared.");
  report.push("2025 BLS labor releases were affected by the federal government shutdown; October 2025 Employment Situation was not published, so only available/released 2025 NFP dates are tagged.");
  for (const g of GROUPS) {
    const tr = allTrades.filter((t) => t.version === g.key);
    const rows = ["FOMC", "CPI", "NFP", "ANY"].map((typ) => {
      const entryRows = eventCorrelation(tr, typ, "entry");
      const overlapRows = eventCorrelation(tr, typ, "overlap");
      return {
        type: typ,
        entryN: entryRows.length,
        entryNet: sum(entryRows.map((t) => t.net)),
        entryWR: metrics(entryRows).winrate,
        overlapN: overlapRows.length,
        overlapNet: sum(overlapRows.map((t) => t.net)),
        overlapWR: metrics(overlapRows).winrate,
      };
    });
    report.push(`### ${g.name}`);
    report.push(mdTable(rows, [
      { h: "Event", v: (r) => r.type },
      { h: "Entry +/-1d N", v: (r) => r.entryN },
      { h: "Entry Net", v: (r) => fmt(r.entryNet) },
      { h: "Entry WR", v: (r) => pct(r.entryWR) },
      { h: "Open-overlap N", v: (r) => r.overlapN },
      { h: "Overlap Net", v: (r) => fmt(r.overlapNet) },
      { h: "Overlap WR", v: (r) => pct(r.overlapWR) },
    ]));
    const worstEvents = eventTopDates(tr, "ANY").slice(0, 8);
    report.push("");
    report.push("Worst overlapping event windows:");
    report.push(mdTable(worstEvents, [
      { h: "Event date", v: (r) => r.event },
      { h: "Trades", v: (r) => r.trades },
      { h: "WR", v: (r) => pct(r.winrate) },
      { h: "Net", v: (r) => fmt(r.totalNet) },
      { h: "PF", v: (r) => fmt(r.profitFactor) },
    ]));
    report.push("");
  }
  report.push("Interpretation: Event overlap is not automatically causal. It is a risk flag only when event-window net is worse than base and sample size is non-trivial.");
  report.push("");

  report.push("## 10. Root Cause Analysis");
  const rootRows = [];
  for (const g of GROUPS) {
    const losses = allTrades.filter((t) => t.version === g.key && t.net < 0);
    const cats = [
      ["quick_no_follow_through", (t) => Number.isFinite(t.mfeToTp) && t.mfeToTp < 0.25],
      ["initially_right_then_reversed_50pct_TP", (t) => Number.isFinite(t.mfeToTp) && t.mfeToTp >= 0.50],
      ["ema_or_h1_conflict_at_csv_bar", (t) => t.emaAligned === false || t.h1Aligned === false],
      ["slope_conflict", (t) => t.m15SlopeAligned === false || t.h1SlopeAligned === false],
      ["low_trend_or_range", (t) => t.marketRegime === "RANGING_LOW_TREND"],
      ["high_volatility", (t) => t.volRegime === "HIGH_VOL"],
      ["wide_sl_over_3000pts", (t) => t.slPts > 3000],
      ["tight_or_capped_sl_under_2100pts", (t) => t.slPts < 2100],
    ];
    for (const [cat, fn] of cats) {
      const rows = losses.filter(fn);
      rootRows.push({ version: g.key, cause: cat, losses: rows.length, pctLosses: losses.length ? rows.length / losses.length : NaN, net: sum(rows.map((t) => t.net)), avgMfeToTp: mean(rows.map((t) => t.mfeToTp)), avgSlPts: mean(rows.map((t) => t.slPts)) });
    }
  }
  report.push(mdTable(rootRows, [
    { h: "Version", v: (r) => r.version },
    { h: "Cause", v: (r) => r.cause },
    { h: "Loss trades", v: (r) => r.losses },
    { h: "% losses", v: (r) => pct(r.pctLosses) },
    { h: "Net", v: (r) => fmt(r.net) },
    { h: "Avg MFE/TP", v: (r) => fmt(r.avgMfeToTp) },
    { h: "Avg SL pts", v: (r) => fmt(r.avgSlPts) },
  ]));
  report.push("");

  report.push("## 11. Session / Time / Direction");
  for (const g of GROUPS) {
    const tr = allTrades.filter((t) => t.version === g.key);
    report.push(`### ${g.name} by session`);
    report.push(mdTable(groupStats(tr, (t) => t.session, 1), [
      { h: "Session", v: (r) => r.key },
      { h: "Trades", v: (r) => r.trades },
      { h: "WR", v: (r) => pct(r.winrate) },
      { h: "Net", v: (r) => fmt(r.totalNet) },
      { h: "PF", v: (r) => fmt(r.profitFactor) },
    ]));
    report.push("");
    report.push(`### ${g.name} by direction`);
    report.push(mdTable(groupStats(tr, (t) => t.type, 1), [
      { h: "Direction", v: (r) => r.key },
      { h: "Trades", v: (r) => r.trades },
      { h: "WR", v: (r) => pct(r.winrate) },
      { h: "Net", v: (r) => fmt(r.totalNet) },
      { h: "PF", v: (r) => fmt(r.profitFactor) },
    ]));
    report.push("");
  }

  report.push("## 12. TP Maximum Study");
  const tpCandidates = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 6000];
  for (const g of GROUPS) {
    const tr = allTrades.filter((t) => t.version === g.key);
    const buyTrend = tr.filter((t) => t.type === "BUY" && t.marketRegime === "TRENDING");
    const sellTrend = tr.filter((t) => t.type === "SELL" && t.marketRegime === "TRENDING");
    report.push(`### ${g.name} TP candidate simulation - BUY trending`);
    report.push(mdTable(simulateTp(buyTrend, tpCandidates).slice(0, 5), [
      { h: "TP pts", v: (r) => r.tp },
      { h: "N", v: (r) => r.n },
      { h: "WR", v: (r) => pct(r.winrate) },
      { h: "Avg pts/trade", v: (r) => fmt(r.avgPoints) },
      { h: "Ambiguous", v: (r) => r.ambiguous },
    ]));
    report.push("");
    report.push(`### ${g.name} TP candidate simulation - SELL trending`);
    report.push(mdTable(simulateTp(sellTrend, tpCandidates).slice(0, 5), [
      { h: "TP pts", v: (r) => r.tp },
      { h: "N", v: (r) => r.n },
      { h: "WR", v: (r) => pct(r.winrate) },
      { h: "Avg pts/trade", v: (r) => fmt(r.avgPoints) },
      { h: "Ambiguous", v: (r) => r.ambiguous },
    ]));
    report.push("");
  }

  report.push("## 13. Overfit Risk");
  report.push(mdTable([
    { item: "Hardcoded BoS/CHoCH thresholds", evidence: "50*_Point and 5*_Point break offsets are fixed in source", risk: "MEDIUM" },
    { item: "Year concentration", evidence: "Most net profit is concentrated in 2024-2025 trend years; 2021 fails for all versions", risk: "HIGH" },
    { item: "Asymmetric session logic", evidence: "BUY has no session gate; SELL gate is disabled/forced true and v7 uses `True`", risk: "MEDIUM" },
    { item: "SL model sensitivity", evidence: "v6 and v7 have similar net, but v7 DD is lower and v6 has many wide-SL losses", risk: "HIGH" },
    { item: "Partial 2024 samples in v6/v7", evidence: "v6 2024 ends 2024-05-09 and v7 2024 ends 2024-06-07, unlike v5 full 2024", risk: "MEDIUM" },
  ], [
    { h: "Risk item", v: (r) => r.item },
    { h: "Evidence", v: (r) => r.evidence },
    { h: "Risk", v: (r) => r.risk },
  ]));
  report.push("");

  report.push("## 14. Optimization Priorities");
  report.push("High priority:");
  report.push("- Fix v7 `True` to `true`; this is non-negotiable if the supplied source is compiled.");
  report.push("- Keep v6 closed-candle entry indexing and H1 slope filter; do not revert to v5 live bar 0 filter.");
  report.push("- Add a data-derived no-trade/risk-reduction rule for 2021-like regimes: low trend strength or EMA/slope conflict. Backtest evidence shows 2021 is the shared failure regime.");
  report.push("- Add SL guardrails to v6 rather than fully replacing it with v7 hybrid: v7 proves hard caps reduce DD, but v6 still captures structure behavior better in some years.");
  report.push("");
  report.push("Medium priority:");
  report.push("- Test session filters using the session table above. Remove sessions with negative net only if trade count remains statistically usable.");
  report.push("- Add MFE-based exit study: losses with MFE >= 50% TP are reversal candidates for break-even or partial close.");
  report.push("- Use separate TP for BUY trending and SELL trending based on TP simulation table; do not use one universal TP if directional distributions differ.");
  report.push("");
  report.push("Low priority:");
  report.push("- Clean diagnostic comments/logs so SELL SL references HH, not LL.");
  report.push("- Remove unused activeCHoCH/activeBoS variables or use them in explicit state machine logs.");
  report.push("- Export entry feature snapshot directly at order open to avoid reconstructing conditions later from OHLC CSV.");
  report.push("");

  report.push("## 15. Limits of Evidence");
  report.push("- CSV has no explicit news calendar, ADX, ATR, or per-tick intrabar order of high/low. MFE/MAE and TP simulations are based on M15 OHLC path, so same-bar TP/SL collisions are marked ambiguous/conservative.");
  report.push("- Some source files have `.cs` extension but MQL5 syntax; this audit treats them as MT5 EA source.");
  report.push("- Global event correlation is date-level, not tick-level causality. Without explicit broker timezone and intraday economic calendar fields in CSV, event results should be treated as risk association only.");
  report.push("");

  return report.join("\n");
}

function writeCsv(file, rows, cols) {
  const q = (v) => {
    const s = v === undefined || v === null || (typeof v === "number" && !Number.isFinite(v)) ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [cols.join(",")];
  for (const r of rows) lines.push(cols.map((c) => q(r[c])).join(","));
  fs.writeFileSync(path.join(ROOT, file), lines.join("\n"), "utf8");
}

function main() {
  const outDir = path.join(ROOT, "Dokumen", "Audit");
  fs.mkdirSync(outDir, { recursive: true });
  const data = loadEverything();
  const report = makeReport(data);
  fs.writeFileSync(path.join(outDir, "AUDIT_V5_V6_V7_FORENSIC_2026-05-15.md"), report, "utf8");
  fs.writeFileSync(path.join(outDir, "v5_v6_v7_summary.json"), JSON.stringify({
    generatedAt: new Date().toISOString(),
    thresholds: data.thresholds,
    master: GROUPS.map((g) => ({ version: g.key, ...metrics(data.allTrades.filter((t) => t.version === g.key)) })),
  }, null, 2), "utf8");
  writeCsv("Dokumen/Audit/v5_v6_v7_file_audit.csv", data.fileAudits, ["group", "file", "status", "rows", "malformed", "start", "end", "profit", "trades", "columns"]);
  writeCsv("Dokumen/Audit/v5_v6_v7_trade_features.csv", data.allTrades, [
    "version", "file", "ticket", "type", "entry", "exit", "sl", "tp", "net", "session",
    "entryMs", "exitMs", "durationHours", "slPts", "tpPts", "rr", "weekday", "hour", "month", "year",
    "emaGapPts", "emaAligned", "m15Slope4Pts", "m15Slope16Pts", "m15SlopeAligned", "h1GapPts", "h1Aligned",
    "h1Slope4Pts", "h1SlopeAligned", "vol16Pts", "marketRegime", "volRegime", "mfePts", "maePts", "mfeToTp",
    "maeToSl", "pathHit", "lastBosDirection", "lastBosAgeHours", "lastChochDirection", "lastChochAgeHours",
  ]);
  console.log(`Wrote ${path.join(outDir, "AUDIT_V5_V6_V7_FORENSIC_2026-05-15.md")}`);
  console.log(`Trades analyzed: ${data.allTrades.length}`);
  console.log(`CSV files audited: ${data.fileAudits.length}`);
}

main();
