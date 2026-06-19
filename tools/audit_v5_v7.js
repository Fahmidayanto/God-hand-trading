const fs = require("fs");
const path = require("path");

const ROOT = process.cwd();
const OUT_DIR = path.join(ROOT, "Dokumen", "Audit");
const POINT = 0.01;

const GROUPS = [
  {
    key: "v5",
    name: "v5 static SL",
    dir: "backtest statis",
    source: "Dev_Bot_v5_statis.cs",
    slModel: "Static point SL/TP by entry count",
  },
  {
    key: "v7",
    name: "v7 dynamic hybrid SL",
    dir: "backtest dynamic hybrid",
    source: "Dev_Bot_v7_hybrid.cs",
    slModel: "Structure SL with max-distance branch plus 1000 point buffer branch",
  },
];

function splitCsvLine(line) {
  const out = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        quoted = !quoted;
      }
    } else if (ch === "," && !quoted) {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

function parseCsv(rel) {
  const full = path.join(ROOT, rel);
  let lines = fs.readFileSync(full, "utf8").replace(/^\uFEFF/, "").split(/\r?\n/).filter((l) => l.trim());
  if (lines[0] && lines[0].startsWith("===")) lines = lines.slice(1);
  if (!lines.length) return { header: [], rows: [], malformed: 0 };
  const header = splitCsvLine(lines[0]).map((h) => h.trim());
  const rows = [];
  let malformed = 0;
  for (let i = 1; i < lines.length; i++) {
    const vals = splitCsvLine(lines[i]);
    if (vals.length !== header.length) malformed++;
    const r = {};
    for (let j = 0; j < header.length; j++) r[header[j]] = (vals[j] || "").trim();
    rows.push(r);
  }
  return { header, rows, malformed };
}

function listCsvRecursive(dir) {
  const base = path.join(ROOT, dir);
  const out = [];
  function walk(abs) {
    for (const ent of fs.readdirSync(abs, { withFileTypes: true })) {
      const p = path.join(abs, ent.name);
      if (ent.isDirectory()) walk(p);
      else if (ent.name.toLowerCase().endsWith(".csv")) out.push(path.relative(ROOT, p));
    }
  }
  walk(base);
  return out.sort();
}

function listCsvDirect(dir) {
  return fs.readdirSync(path.join(ROOT, dir))
    .filter((f) => f.toLowerCase().endsWith(".csv"))
    .sort()
    .map((f) => path.join(dir, f));
}

function parseTime(s) {
  if (!s || s === "1970.01.01 00:00:00") return NaN;
  const m = String(s).match(/^(\d{4})\.(\d{2})\.(\d{2})\s+(\d{2}):(\d{2}):(\d{2})$/);
  if (!m) return NaN;
  return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
}

function fmtTime(ms) {
  if (!Number.isFinite(ms)) return "";
  const d = new Date(ms);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
}

function dateKey(ms) {
  if (!Number.isFinite(ms)) return "";
  return fmtTime(ms).slice(0, 10);
}

function yearKey(ms) {
  return Number.isFinite(ms) ? String(new Date(ms).getUTCFullYear()) : "";
}

function monthKey(ms) {
  return Number.isFinite(ms) ? fmtTime(ms).slice(0, 7) : "";
}

function weekday(ms) {
  return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][new Date(ms).getUTCDay()];
}

function toNum(v) {
  if (v === undefined || v === null || v === "") return NaN;
  const n = Number(String(v).trim());
  return Number.isFinite(n) ? n : NaN;
}

function sum(xs) {
  return xs.filter(Number.isFinite).reduce((a, b) => a + b, 0);
}

function mean(xs) {
  const a = xs.filter(Number.isFinite);
  return a.length ? sum(a) / a.length : NaN;
}

function median(xs) {
  return quantile(xs, 0.5);
}

function quantile(xs, q) {
  const a = xs.filter(Number.isFinite).sort((x, y) => x - y);
  if (!a.length) return NaN;
  const p = (a.length - 1) * q;
  const lo = Math.floor(p);
  const hi = Math.ceil(p);
  if (lo === hi) return a[lo];
  return a[lo] + (a[hi] - a[lo]) * (p - lo);
}

function maxDrawdown(pnls) {
  let eq = 0;
  let peak = 0;
  let dd = 0;
  for (const p of pnls) {
    eq += p;
    peak = Math.max(peak, eq);
    dd = Math.max(dd, peak - eq);
  }
  return dd;
}

function streak(pnls, win) {
  let best = 0;
  let cur = 0;
  for (const p of pnls) {
    const ok = win ? p > 0 : p < 0;
    cur = ok ? cur + 1 : 0;
    best = Math.max(best, cur);
  }
  return best;
}

function metrics(trades) {
  const rows = trades.slice().sort((a, b) => a.entryMs - b.entryMs);
  const wins = rows.filter((t) => t.net > 0);
  const losses = rows.filter((t) => t.net < 0);
  const gp = sum(wins.map((t) => t.net));
  const gl = -sum(losses.map((t) => t.net));
  const pnl = rows.map((t) => t.net);
  return {
    trades: rows.length,
    wins: wins.length,
    losses: losses.length,
    winrate: rows.length ? wins.length / rows.length : NaN,
    totalNet: sum(pnl),
    grossProfit: gp,
    grossLoss: gl,
    profitFactor: gl > 0 ? gp / gl : NaN,
    expectancy: rows.length ? sum(pnl) / rows.length : NaN,
    avgWin: mean(wins.map((t) => t.net)),
    avgLoss: mean(losses.map((t) => t.net)),
    maxDD: maxDrawdown(pnl),
    maxConsecWin: streak(pnl, true),
    maxConsecLoss: streak(pnl, false),
    avgSlPts: mean(rows.map((t) => t.slPts)),
    medSlPts: median(rows.map((t) => t.slPts)),
    avgTpPts: mean(rows.map((t) => t.tpPts)),
    avgRR: mean(rows.map((t) => t.rr)),
    avgDurationHours: mean(rows.map((t) => t.durationHours)),
  };
}

function fmt(n, d = 2) {
  return Number.isFinite(n) ? n.toFixed(d) : "NA";
}

function pct(n, d = 1) {
  return Number.isFinite(n) ? `${(n * 100).toFixed(d)}%` : "NA";
}

function mdTable(rows, cols) {
  const clean = (v) => String(v === undefined || v === null ? "" : v).replace(/\|/g, "\\|").replace(/\r?\n/g, "<br>");
  const lines = [];
  lines.push(`| ${cols.map((c) => c.h).join(" | ")} |`);
  lines.push(`| ${cols.map(() => "---").join(" | ")} |`);
  for (const r of rows) lines.push(`| ${cols.map((c) => clean(c.v(r))).join(" | ")} |`);
  return lines.join("\n");
}

function groupRows(trades, keyFn) {
  const m = new Map();
  for (const t of trades) {
    const key = keyFn(t);
    if (key === undefined || key === null || key === "" || (typeof key === "number" && !Number.isFinite(key))) continue;
    if (!m.has(key)) m.set(key, []);
    m.get(key).push(t);
  }
  return Array.from(m.entries()).map(([key, rows]) => ({ key, rows, ...metrics(rows) }));
}

function bestGroup(trades, keyFn, minN = 1) {
  const rows = groupRows(trades, keyFn).filter((r) => r.trades >= minN);
  return rows.sort((a, b) => b.totalNet - a.totalNet)[0] || null;
}

function worstGroup(trades, keyFn, minN = 1) {
  const rows = groupRows(trades, keyFn).filter((r) => r.trades >= minN);
  return rows.sort((a, b) => a.totalNet - b.totalNet)[0] || null;
}

function binAtOrBefore(arr, ms) {
  let lo = 0, hi = arr.length - 1, ans = -1;
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

function loadMarket(files, tf) {
  const byTime = new Map();
  for (const f of files.filter((x) => x.includes(`MarketData_XAUUSD_${tf}`))) {
    const parsed = parseCsv(f);
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
  const out = [];
  for (const f of files.filter((x) => x.includes("LLHHBOSData"))) {
    const parsed = parseCsv(f);
    for (const r of parsed.rows) {
      const ms = parseTime(r.Time);
      if (!Number.isFinite(ms)) continue;
      out.push({
        ms,
        type: r.Type,
        direction: r["Direction/Action"],
        price: toNum(r.Price),
        timeframe: r.Timeframe,
        status: r.Status,
      });
    }
  }
  return out.sort((a, b) => a.ms - b.ms);
}

function prevEvent(events, ms, fn) {
  let idx = binAtOrBefore(events, ms);
  for (let i = idx; i >= 0; i--) {
    if (fn(events[i])) return events[i];
    if (ms - events[i].ms > 21 * 86400000) break;
  }
  return null;
}

function rollingRange(arr, idx, n) {
  const start = Math.max(0, idx - n + 1);
  const vals = [];
  for (let i = start; i <= idx; i++) vals.push((arr[i].high - arr[i].low) / POINT);
  return mean(vals);
}

function trueRange(arr, idx) {
  const b = arr[idx];
  if (!b) return NaN;
  if (idx <= 0) return (b.high - b.low) / POINT;
  const pc = arr[idx - 1].close;
  return Math.max(b.high - b.low, Math.abs(b.high - pc), Math.abs(b.low - pc)) / POINT;
}

function atr(arr, idx, n) {
  const start = Math.max(0, idx - n + 1);
  const vals = [];
  for (let i = start; i <= idx; i++) vals.push(trueRange(arr, i));
  return mean(vals);
}

function addMarketFeatures(trades, m15, h1, events) {
  for (const t of trades) {
    const i15 = binAtOrBefore(m15, t.entryMs);
    const ih1 = binAtOrBefore(h1, t.entryMs);
    if (i15 >= 0) {
      const b = m15[i15];
      t.m15Close = b.close;
      t.m15Ema = b.ema;
      t.m15Spread = b.spread;
      t.emaGapPts = (b.close - b.ema) / POINT;
      t.emaSideAligned = t.type === "BUY" ? t.emaGapPts > 0 : t.emaGapPts < 0;
      t.m15Slope4Pts = i15 >= 4 ? (m15[i15].ema - m15[i15 - 4].ema) / POINT : NaN;
      t.m15Slope16Pts = i15 >= 16 ? (m15[i15].ema - m15[i15 - 16].ema) / POINT : NaN;
      t.m15SlopeAligned = t.type === "BUY" ? t.m15Slope4Pts > 0 : t.m15Slope4Pts < 0;
      t.vol16Pts = rollingRange(m15, i15, 16);
      t.atr14Pts = atr(m15, i15, 14);
      t.entryBarRangePts = (b.high - b.low) / POINT;
      t.entryBarBodyPts = Math.abs(b.close - b.open) / POINT;
      t.closePos = b.high > b.low ? (b.close - b.low) / (b.high - b.low) : NaN;
    }
    if (ih1 >= 0) {
      const b = h1[ih1];
      t.h1Close = b.close;
      t.h1Ema = b.ema;
      t.h1GapPts = (b.close - b.ema) / POINT;
      t.h1SideAligned = t.type === "BUY" ? t.h1GapPts > 0 : t.h1GapPts < 0;
      t.h1Slope4Pts = ih1 >= 4 ? (h1[ih1].ema - h1[ih1 - 4].ema) / POINT : NaN;
      t.h1SlopeAligned = t.type === "BUY" ? t.h1Slope4Pts > 0 : t.h1Slope4Pts < 0;
    }
    const lastBos = prevEvent(events, t.entryMs, (e) => e.type === "BoS" && e.timeframe === "M15");
    const lastChoch = prevEvent(events, t.entryMs, (e) => e.type === "CHoCH" && e.timeframe === "M15");
    t.lastBosDirection = lastBos ? lastBos.direction : "";
    t.lastBosAgeHours = lastBos ? (t.entryMs - lastBos.ms) / 3600000 : NaN;
    t.lastBosPrice = lastBos ? lastBos.price : NaN;
    t.lastChochDirection = lastChoch ? lastChoch.direction : "";
    t.lastChochAgeHours = lastChoch ? (t.entryMs - lastChoch.ms) / 3600000 : NaN;

    const start = binAtOrBefore(m15, t.entryMs);
    const end = binAtOrBefore(m15, t.exitMs);
    if (start >= 0 && end >= start) {
      let hi = -Infinity;
      let lo = Infinity;
      let firstTp = null;
      let firstSl = null;
      for (let i = start; i <= end; i++) {
        const b = m15[i];
        hi = Math.max(hi, b.high);
        lo = Math.min(lo, b.low);
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
      if (firstTp !== null && firstSl !== null && firstTp === firstSl) t.pathHit = "same_bar_ambiguous";
      else if (firstTp !== null && (firstSl === null || firstTp < firstSl)) t.pathHit = "TP_first";
      else if (firstSl !== null && (firstTp === null || firstSl < firstTp)) t.pathHit = "SL_first";
      else t.pathHit = "neither";
    }

    const afterStart = binAtOrBefore(m15, t.exitMs) + 1;
    const afterEnd = binAtOrBefore(m15, t.exitMs + 96 * 3600000);
    if (afterStart > 0 && afterEnd >= afterStart) {
      let postFav = 0;
      let postTarget = false;
      for (let i = afterStart; i <= afterEnd; i++) {
        const b = m15[i];
        if (t.type === "BUY") {
          postFav = Math.max(postFav, (b.high - t.exit) / POINT);
          if (b.high >= t.tp) postTarget = true;
        } else {
          postFav = Math.max(postFav, (t.exit - b.low) / POINT);
          if (b.low <= t.tp) postTarget = true;
        }
      }
      t.postExitFavorablePts96h = postFav;
      t.postExitOriginalTpHit96h = postTarget;
    }
  }
}

function classify(trades) {
  const volQ25 = quantile(trades.map((t) => t.vol16Pts), 0.25);
  const volQ75 = quantile(trades.map((t) => t.vol16Pts), 0.75);
  const gapQ25 = quantile(trades.map((t) => Math.abs(t.emaGapPts)), 0.25);
  const slopeQ25 = quantile(trades.map((t) => Math.abs(t.m15Slope16Pts)), 0.25);
  for (const t of trades) {
    t.volRegime = t.vol16Pts >= volQ75 ? "HIGH_VOL" : t.vol16Pts <= volQ25 ? "LOW_VOL" : "MID_VOL";
    const side = t.emaSideAligned && t.h1SideAligned;
    const slope = t.m15SlopeAligned && t.h1SlopeAligned;
    const weak = Math.abs(t.emaGapPts) <= gapQ25 || Math.abs(t.m15Slope16Pts) <= slopeQ25;
    if (side && slope && !weak) t.marketRegime = "TRENDING_CONFLUENT";
    else if (!side || !slope) t.marketRegime = "EMA_OR_SLOPE_CONFLICT";
    else if (weak || t.volRegime === "LOW_VOL") t.marketRegime = "RANGING_LOW_TREND";
    else t.marketRegime = "MIXED_TRANSITION";

    if (t.net < 0 && Number.isFinite(t.mfeToTp) && t.mfeToTp < 0.25) t.lossPattern = "fake_break_no_follow_through";
    else if (t.net < 0 && Number.isFinite(t.mfeToTp) && t.mfeToTp >= 0.5) t.lossPattern = "right_then_reversed";
    else if (t.net < 0 && t.postExitOriginalTpHit96h) t.lossPattern = "stopped_then_target_later";
    else if (t.net < 0 && t.slPts > 3000) t.lossPattern = "wide_sl_loss";
    else if (t.net < 0 && t.slPts < 2100) t.lossPattern = "tight_sl_loss";
    else if (t.net < 0) t.lossPattern = "ordinary_sl_loss";
    else if (t.net > 0 && t.marketRegime === "TRENDING_CONFLUENT") t.winPattern = "trend_continuation";
    else if (t.net > 0 && t.session === "Asia") t.winPattern = "asia_continuation";
    else if (t.net > 0) t.winPattern = "other_win";
  }
  return { volQ25, volQ75, gapQ25, slopeQ25 };
}

function inferEntrySet(t) {
  const sp = Math.round(t.slPts);
  const tp = Math.round(t.tpPts);
  if (t.version === "v5") {
    if (Math.abs(sp - 3000) <= 5 && Math.abs(tp - 3500) <= 5) return "entry1_runtime_3000/3500";
    if (Math.abs(sp - 3000) <= 5 && Math.abs(tp - 3000) <= 5) return "entry1_static_3000/3000";
    if (Math.abs(sp - 2000) <= 5 && Math.abs(tp - 2500) <= 5) return "entry2_static_2000/2500";
    if (Math.abs(sp - 3500) <= 5 && Math.abs(tp - 3000) <= 5) return "entry3_static_3500/3000";
    return "static_other";
  }
  if (t.version === "v7") {
    const tpTag = Math.abs(tp - 3500) <= 5 ? "_tp3500_runtime" : "";
    if (Math.abs(t.slPts - 3000) <= 5) return `hybrid_zone3_capped_3000${tpTag}`;
    if (t.slPts > 3005) return `hybrid_buffer_final_gt_3000${tpTag}`;
    if (t.slPts < 2995) return `hybrid_structure_inside_3000${tpTag}`;
    return "hybrid_other";
  }
  return "";
}

function exitReason(t) {
  const tol = 0.15;
  if (t.type === "BUY") {
    if (Math.abs(t.exit - t.tp) <= tol || t.exit > t.tp) return "TP";
    if (Math.abs(t.exit - t.sl) <= tol || t.exit < t.sl) return "SL";
  } else {
    if (Math.abs(t.exit - t.tp) <= tol || t.exit < t.tp) return "TP";
    if (Math.abs(t.exit - t.sl) <= tol || t.exit > t.sl) return "SL";
  }
  return t.net > 0 ? "WIN_OTHER" : "LOSS_OTHER";
}

function loadTrades(g, files) {
  const trades = [];
  for (const f of files.filter((x) => path.basename(x).startsWith("Backtest_Results_"))) {
    const parsed = parseCsv(f);
    for (const r of parsed.rows) {
      const entryMs = parseTime(r.EntryTime);
      const exitMs = parseTime(r.ExitTime);
      const entry = toNum(r.EntryPrice);
      const exit = toNum(r.ExitPrice);
      const sl = toNum(r.SL);
      const tp = toNum(r.TP);
      const profit = toNum(r.Profit);
      const move = Math.abs(exit - entry);
      const inferredLot = move > 0 ? Math.abs(profit) / (move * 100) : NaN;
      const t = {
        version: g.key,
        versionName: g.name,
        file: f,
        ticket: r.Ticket,
        symbol: r.Symbol,
        type: r.Type,
        entry,
        exit,
        sl,
        tp,
        profit,
        spreadCost: toNum(r.Spread_Cost),
        commission: toNum(r.Commission),
        net: toNum(r.Net_Profit),
        session: r.Session,
        entryRaw: r.EntryTime,
        exitRaw: r.ExitTime,
        entryMs,
        exitMs,
        lotCsv: toNum(r.LotSize),
        inferredLot,
        magic: r.MagicNumber,
        timeframe: r.Timeframe,
        year: yearKey(entryMs),
        month: monthKey(entryMs),
        date: dateKey(entryMs),
        weekday: Number.isFinite(entryMs) ? weekday(entryMs) : "",
        hour: Number.isFinite(entryMs) ? new Date(entryMs).getUTCHours() : NaN,
        minute: Number.isFinite(entryMs) ? new Date(entryMs).getUTCMinutes() : NaN,
        durationHours: Number.isFinite(entryMs) && Number.isFinite(exitMs) ? (exitMs - entryMs) / 3600000 : NaN,
        slPts: Math.abs(entry - sl) / POINT,
        tpPts: Math.abs(tp - entry) / POINT,
      };
      t.rr = t.slPts > 0 ? t.tpPts / t.slPts : NaN;
      t.exitReason = exitReason(t);
      t.entrySet = inferEntrySet(t);
      trades.push(t);
    }
  }
  return trades.sort((a, b) => a.entryMs - b.entryMs);
}

function fileAudit(g, files) {
  return files.map((f) => {
    try {
      const p = parseCsv(f);
      let minMs = Infinity;
      let maxMs = -Infinity;
      for (const r of p.rows) {
        for (const c of ["EntryTime", "ExitTime", "Time", "StartDate", "EndDate"]) {
          const ms = parseTime(r[c]);
          if (Number.isFinite(ms)) {
            minMs = Math.min(minMs, ms);
            maxMs = Math.max(maxMs, ms);
          }
        }
      }
      return {
        version: g.key,
        file: f,
        rows: p.rows.length,
        columns: p.header.join("; "),
        malformed: p.malformed,
        start: fmtTime(minMs),
        end: fmtTime(maxMs),
        status: "OK",
      };
    } catch (err) {
      return { version: g.key, file: f, rows: 0, columns: "", malformed: 0, start: "", end: "", status: `ERROR: ${err.message}` };
    }
  });
}

function codeLine(file, pattern) {
  const lines = fs.readFileSync(path.join(ROOT, file), "utf8").split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) if (pattern.test(lines[i])) return i + 1;
  return "";
}

function writeCsv(rel, rows, cols) {
  const q = (v) => {
    if (v === undefined || v === null || (typeof v === "number" && !Number.isFinite(v))) return "";
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  fs.writeFileSync(path.join(ROOT, rel), [cols.join(","), ...rows.map((r) => cols.map((c) => q(r[c])).join(","))].join("\n"), "utf8");
}

function tradeExample(t) {
  if (!t) return "-";
  return `${t.entryRaw} ${t.type} En ${fmt(t.entry)} SL ${fmt(t.sl)} TP ${fmt(t.tp)} ${t.session} H${String(t.hour).padStart(2, "0")} Net ${fmt(t.net)}`;
}

function yearlyComparisonRows(allTrades) {
  const rows = [];
  const years = Array.from(new Set(allTrades.map((t) => t.year))).sort();
  for (const y of years) {
    for (const g of GROUPS) {
      const tr = allTrades.filter((t) => t.version === g.key && t.year === y);
      if (!tr.length) continue;
      const m = metrics(tr);
      const bestSession = bestGroup(tr, (t) => t.session, 2);
      const worstSession = worstGroup(tr, (t) => t.session, 2);
      const bestHour = bestGroup(tr, (t) => `H${String(t.hour).padStart(2, "0")}`, 2);
      const worstHour = worstGroup(tr, (t) => `H${String(t.hour).padStart(2, "0")}`, 2);
      const bestRegime = bestGroup(tr, (t) => t.marketRegime, 2);
      const worstRegime = worstGroup(tr, (t) => t.marketRegime, 2);
      const entryMix = groupRows(tr, (t) => t.type).map((r) => `${r.key}:${r.trades}/${fmt(r.totalNet, 0)}`).join(", ");
      const entrySet = groupRows(tr, (t) => t.entrySet).sort((a, b) => b.trades - a.trades).map((r) => `${r.key}:${r.trades}`).join(", ");
      const worstTrade = tr.slice().sort((a, b) => a.net - b.net)[0];
      const bestTrade = tr.slice().sort((a, b) => b.net - a.net)[0];
      const primaryLoss = worstGroup(tr.filter((t) => t.net < 0), (t) => t.lossPattern || "loss", 1);
      const analysis = [
        m.totalNet >= 0 ? `positif ${fmt(m.totalNet)} net` : `negatif ${fmt(m.totalNet)} net`,
        bestRegime ? `regime terbaik ${bestRegime.key} (${fmt(bestRegime.totalNet)})` : "",
        worstRegime ? `risiko ${worstRegime.key} (${fmt(worstRegime.totalNet)})` : "",
        primaryLoss ? `loss utama ${primaryLoss.key} (${primaryLoss.trades} trade, ${fmt(primaryLoss.totalNet)})` : "",
      ].filter(Boolean).join("; ");
      const solution = worstRegime && worstRegime.totalNet < 0
        ? `Turunkan risk atau blok ${worstRegime.key}; prioritaskan ${bestSession ? bestSession.key : "session positif"} dan ${bestHour ? bestHour.key : "hour positif"}.`
        : `Pertahankan filter; hindari segmen negatif ${worstSession ? worstSession.key : "N/A"} / ${worstHour ? worstHour.key : "N/A"}.`;
      rows.push({
        year: y,
        version: g.key,
        trades: m.trades,
        wr: pct(m.winrate),
        net: fmt(m.totalNet),
        pf: fmt(m.profitFactor),
        avgSL: fmt(m.avgSlPts, 0),
        avgTP: fmt(m.avgTpPts, 0),
        avgRR: fmt(m.avgRR, 2),
        entryMix,
        entrySet,
        bestSession: bestSession ? `${bestSession.key} ${fmt(bestSession.totalNet)}` : "NA",
        worstSession: worstSession ? `${worstSession.key} ${fmt(worstSession.totalNet)}` : "NA",
        bestHour: bestHour ? `${bestHour.key} ${fmt(bestHour.totalNet)}` : "NA",
        worstHour: worstHour ? `${worstHour.key} ${fmt(worstHour.totalNet)}` : "NA",
        bestTrade: tradeExample(bestTrade),
        worstTrade: tradeExample(worstTrade),
        analysis,
        solution,
      });
    }
  }
  return rows;
}

function segmentRows(allTrades, mode) {
  const rows = [];
  const features = [
    ["direction", (t) => t.type],
    ["session", (t) => t.session],
    ["hour", (t) => `H${String(t.hour).padStart(2, "0")}`],
    ["session_hour", (t) => `${t.session} H${String(t.hour).padStart(2, "0")}`],
    ["regime", (t) => t.marketRegime],
    ["vol", (t) => t.volRegime],
    ["entry_set", (t) => t.entrySet],
    ["loss_pattern", (t) => t.lossPattern],
  ];
  for (const g of GROUPS) {
    const tr = allTrades.filter((t) => t.version === g.key);
    const base = metrics(tr);
    for (const [feature, fn] of features) {
      for (const r of groupRows(tr, fn).filter((x) => x.trades >= Math.max(3, Math.ceil(tr.length * 0.04)))) {
        const lift = r.winrate - base.winrate;
        const isIdeal = r.totalNet > 0 && r.profitFactor > 1.15 && lift >= 0;
        const isDanger = r.totalNet < 0 || r.profitFactor < 0.85 || lift < -0.12;
        if ((mode === "ideal" && isIdeal) || (mode === "danger" && isDanger)) {
          rows.push({
            version: g.key,
            feature,
            value: r.key,
            trades: r.trades,
            wr: pct(r.winrate),
            netNum: r.totalNet,
            net: fmt(r.totalNet),
            pf: fmt(r.profitFactor),
            lift: pct(lift),
            analysis: mode === "ideal"
              ? `Repeating edge: ${r.trades} trade, PF ${fmt(r.profitFactor)}, net ${fmt(r.totalNet)}.`
              : `Risk cluster: ${r.trades} trade, PF ${fmt(r.profitFactor)}, net ${fmt(r.totalNet)}.`,
            solution: mode === "ideal" ? "Prioritaskan atau tambah risk kecil hanya bila confluence sama." : "Blok, kurangi lot, atau butuh filter tambahan sebelum entry.",
          });
        }
      }
    }
  }
  rows.sort((a, b) => mode === "ideal" ? b.netNum - a.netNum : a.netNum - b.netNum);
  return rows;
}

function fakeReversalRows(allTrades) {
  const rows = [];
  for (const g of GROUPS) {
    const years = Array.from(new Set(allTrades.filter((t) => t.version === g.key).map((t) => t.year))).sort();
    for (const y of years) {
      const losses = allTrades.filter((t) => t.version === g.key && t.year === y && t.net < 0);
      if (!losses.length) continue;
      const noFollow = losses.filter((t) => t.lossPattern === "fake_break_no_follow_through");
      const reversed = losses.filter((t) => t.lossPattern === "right_then_reversed");
      const later = losses.filter((t) => t.postExitOriginalTpHit96h);
      const sess = worstGroup(losses, (t) => t.session, 1);
      const hr = worstGroup(losses, (t) => `H${String(t.hour).padStart(2, "0")}`, 1);
      const example = losses.slice().sort((a, b) => {
        const as = (a.postExitOriginalTpHit96h ? 100000 : 0) + (a.mfeToTp || 0) * 1000;
        const bs = (b.postExitOriginalTpHit96h ? 100000 : 0) + (b.mfeToTp || 0) * 1000;
        return bs - as;
      })[0];
      rows.push({
        version: g.key,
        year: y,
        losses: losses.length,
        noFollow: noFollow.length,
        rightThenReversed: reversed.length,
        stoppedThenTp96h: later.length,
        worstSession: sess ? `${sess.key} ${fmt(sess.totalNet)}` : "NA",
        worstHour: hr ? `${hr.key} ${fmt(hr.totalNet)}` : "NA",
        example: tradeExample(example),
        analysis: `${noFollow.length} loss tanpa follow-through; ${reversed.length} loss sempat benar >=50% TP; ${later.length} loss mencapai TP awal <=96h setelah exit.`,
        solution: later.length ? "Uji buffer SL/BE-delay untuk pola stop-sweep; jangan tambah risk pada jam/session cluster negatif." : "Tambahkan validasi follow-through candle/ATR sebelum entry.",
      });
    }
  }
  return rows;
}

function matchedRows(allTrades) {
  const v5 = allTrades.filter((t) => t.version === "v5");
  const v7 = allTrades.filter((t) => t.version === "v7");
  const map7 = new Map(v7.map((t) => [`${t.year}|${t.ticket}|${t.type}`, t]));
  const rows = [];
  for (const a of v5) {
    const b = map7.get(`${a.year}|${a.ticket}|${a.type}`);
    if (!b) continue;
    rows.push({
      year: a.year,
      ticket: a.ticket,
      type: a.type,
      entryTime: a.entryRaw,
      v5Session: a.session,
      v7Session: b.session,
      v5SLPts: a.slPts,
      v7SLPts: b.slPts,
      v5TPPts: a.tpPts,
      v7TPPts: b.tpPts,
      v5Net: a.net,
      v7Net: b.net,
      diffNet: b.net - a.net,
      outcomeChange: `${a.net > 0 ? "W" : "L"}->${b.net > 0 ? "W" : "L"}`,
      v5Trade: a,
      v7Trade: b,
    });
  }
  return rows;
}

function sourceAuditRows() {
  return [
    {
      finding: "Only actual source diff is the M15 entry SL/TP block and SELL entry offset",
      evidence: "git diff shows 68 changed lines; v7 changes BUY/SELL SL logic, BUY TP handling, and SELL entry offset from -3 to -5 points.",
      code: `${GROUPS[0].source}:3409 / ${GROUPS[1].source}:3409`,
      severity: "HIGH",
    },
    {
      finding: "v7 hybrid max cap is applied before adding 1000-point structure buffer",
      evidence: "When distanceToLL/HH <= 3000, v7 sets SL to LL-1000 or HH+1000; final risk can exceed 3000 points.",
      code: `${GROUPS[1].source}:${codeLine(GROUPS[1].source, /dynamicSL_Buy/)}-${codeLine(GROUPS[1].source, /tp_M15 = entryPrice_M15 \+ DefaultTP_Buy_M15/)}`,
      severity: "HIGH",
    },
    {
      finding: "v7 minSLDistance_Buy is declared but never used",
      evidence: "minSLDistance_Buy appears only on declaration line; no too-close branch exists.",
      code: `${GROUPS[1].source}:${codeLine(GROUPS[1].source, /minSLDistance_Buy/)}`,
      severity: "MEDIUM",
    },
    {
      finding: "v7 BUY Entry2TP_Buy_M15 is bypassed",
      evidence: "v7 BUY always assigns DefaultTP_Buy_M15; SELL still varies TP by entryCountSell_M15.",
      code: `${GROUPS[1].source}:${codeLine(GROUPS[1].source, /tp_M15 = entryPrice_M15 \+ DefaultTP_Buy_M15/)}`,
      severity: "HIGH",
    },
    {
      finding: "Backtest TP runtime does not match source default input",
      evidence: "Source DefaultTP_Buy/Sell_M15 is 3000, but Backtest_Results show actual TP distance near 3500 points on the canonical trades.",
      code: `${GROUPS[0].source}:${codeLine(GROUPS[0].source, /DefaultTP_Buy_M15/)}-${codeLine(GROUPS[0].source, /DefaultTP_Sell_M15/)}`,
      severity: "MEDIUM",
    },
    {
      finding: "OnTick gates M15 detection behind a new H1 bar check",
      evidence: "Both files return when rates_H1[0].time == lastBarTime_H1 before DetectAndDraw_M15, so M15 logic only continues when the H1 bar changes.",
      code: `${GROUPS[0].source}:${codeLine(GROUPS[0].source, /rates_H1\[0\]\.time == lastBarTime_H1/)} / ${GROUPS[1].source}:${codeLine(GROUPS[1].source, /rates_H1\[0\]\.time == lastBarTime_H1/)}`,
      severity: "HIGH",
    },
    {
      finding: "Trailing and max-hold logic are defined but disabled",
      evidence: "ApplyTrailingStop_M15 and ShouldForceCloseTrade are commented in runtime path; backtest trades can stay open far beyond MaxHoldHours_M15=24.",
      code: `${GROUPS[0].source}:${codeLine(GROUPS[0].source, /ApplyTrailingStop_M15\(\).*DISABLED/)} / ${GROUPS[0].source}:${codeLine(GROUPS[0].source, /ShouldForceCloseTrade\(currentBuyTrade_M15\)/)}`,
      severity: "MEDIUM",
    },
    {
      finding: "CSV LotSize is wrong versus executed order size",
      evidence: "trade.Buy/Sell uses 0.05 lots, but CheckTradeClosure saves lotSize=0.01; CSV LotSize column is therefore not executable-size evidence.",
      code: `${GROUPS[0].source}:${codeLine(GROUPS[0].source, /trade\.Buy\(0\.05/)} / ${GROUPS[0].source}:${codeLine(GROUPS[0].source, /double lotSize = 0\.01/)}`,
      severity: "HIGH",
    },
    {
      finding: "Session label uses TimeCurrent despite comment saying GMT",
      evidence: "GetCurrentSession calls TimeCurrent and maps raw server hour to Asia/London/Overlap/NewYork.",
      code: `${GROUPS[0].source}:${codeLine(GROUPS[0].source, /string GetCurrentSession/)}-${codeLine(GROUPS[0].source, /London_NewYork_Overlap/)}`,
      severity: "MEDIUM",
    },
  ];
}

function makeReport(data) {
  const { allTrades, fileAudits, thresholds, matchRows } = data;
  const lines = [];
  const master = GROUPS.map((g) => ({ version: g.key, name: g.name, slModel: g.slModel, ...metrics(allTrades.filter((t) => t.version === g.key)) }));
  const yearRows = yearlyComparisonRows(allTrades);
  const idealRows = segmentRows(allTrades, "ideal");
  const dangerRows = segmentRows(allTrades, "danger");
  const reversal = fakeReversalRows(allTrades);
  const matches = matchRows;
  const outcomeRows = groupRows(matches, (r) => r.outcomeChange).map((r) => ({
    outcome: r.key,
    trades: r.trades,
    diffNet: fmt(sum(r.rows.map((x) => x.diffNet))),
    avgV5SL: fmt(mean(r.rows.map((x) => x.v5SLPts)), 0),
    avgV7SL: fmt(mean(r.rows.map((x) => x.v7SLPts)), 0),
  })).sort((a, b) => b.trades - a.trades);
  const slBugRows = GROUPS.map((g) => {
    const tr = allTrades.filter((t) => t.version === g.key);
    const gt3000 = tr.filter((t) => t.slPts > 3005);
    const lt2100 = tr.filter((t) => t.slPts < 2100);
    const dur24 = tr.filter((t) => t.durationHours > 24);
    const lotBad = tr.filter((t) => Number.isFinite(t.inferredLot) && Math.abs(t.inferredLot - t.lotCsv) > 0.02);
    return {
      version: g.key,
      slGt3000: gt3000.length,
      slGt3000Net: fmt(sum(gt3000.map((t) => t.net))),
      slLt2100: lt2100.length,
      slLt2100Net: fmt(sum(lt2100.map((t) => t.net))),
      dur24: dur24.length,
      lotMismatch: lotBad.length,
      avgInferredLot: fmt(mean(tr.map((t) => t.inferredLot)), 3),
      avgCsvLot: fmt(mean(tr.map((t) => t.lotCsv)), 3),
    };
  });

  lines.push("# Audit Forensik v5 Static SL vs v7 Dynamic Hybrid SL");
  lines.push("");
  lines.push(`Generated: ${new Date().toISOString().slice(0, 19)}Z`);
  lines.push("Scope: source `Dev_Bot_v5_statis.cs`, `Dev_Bot_v7_hybrid.cs`, and direct CSVs under `backtest statis` / `backtest dynamic hybrid`. Recursive CSV audit is included for hygiene, but duplicated nested Backtest_Results files are not double-counted in trade statistics.");
  lines.push("");
  lines.push("## 1. Executive Summary");
  lines.push(mdTable(master, [
    { h: "Version", v: (r) => r.name },
    { h: "SL model", v: (r) => r.slModel },
    { h: "Trades", v: (r) => r.trades },
    { h: "WR", v: (r) => pct(r.winrate) },
    { h: "Net", v: (r) => fmt(r.totalNet) },
    { h: "PF", v: (r) => fmt(r.profitFactor) },
    { h: "MaxDD", v: (r) => fmt(r.maxDD) },
    { h: "Exp/trade", v: (r) => fmt(r.expectancy) },
    { h: "Avg SL", v: (r) => fmt(r.avgSlPts, 0) },
    { h: "Avg TP", v: (r) => fmt(r.avgTpPts, 0) },
  ]));
  lines.push("");
  lines.push("Main evidence-based conclusions:");
  lines.push("- v7 changes exits, not signal selection: the matched-ticket table shows the same entry universe in practice, so performance differences come from SL/TP geometry and the small SELL entry offset.");
  lines.push("- v7 does not enforce a true 3000-point final risk cap. The cap is checked before the 1000-point buffer, creating final SL distances above 3000 points.");
  lines.push("- The biggest structural bug outside SL is runtime cadence: both EAs return when the H1 bar is unchanged before M15 detection, which explains the hour-clustered entries and means this is not a pure every-M15-bar strategy.");
  lines.push("- CSV LotSize is unreliable: source executes 0.05 lots but exports 0.01; profit amounts imply about 0.05 lot.");
  lines.push("");

  lines.push("## 2. Source-Code Findings");
  lines.push(mdTable(sourceAuditRows(), [
    { h: "Finding", v: (r) => r.finding },
    { h: "Evidence", v: (r) => r.evidence },
    { h: "Code reference", v: (r) => r.code },
    { h: "Severity", v: (r) => r.severity },
  ]));
  lines.push("");
  const minuteRows = GROUPS.map((g) => {
    const tr = allTrades.filter((t) => t.version === g.key);
    const minute00 = tr.filter((t) => t.minute === 0).length;
    const minute05 = tr.filter((t) => t.minute === 5).length;
    const other = tr.length - minute00 - minute05;
    return { version: g.key, trades: tr.length, minute00, minute05, other, pct00: pct(minute00 / tr.length) };
  });
  lines.push("Entry-minute evidence for the H1 gate finding:");
  lines.push(mdTable(minuteRows, [
    { h: "Ver", v: (r) => r.version },
    { h: "Trades", v: (r) => r.trades },
    { h: "Minute 00", v: (r) => r.minute00 },
    { h: "Minute 05", v: (r) => r.minute05 },
    { h: "Other minutes", v: (r) => r.other },
    { h: "% minute 00", v: (r) => r.pct00 },
  ]));
  lines.push("");
  lines.push("Exact v5->v7 diff: v7 replaces static SL/TP selection in the BUY branch with dynamicSL_Buy/lastAcceptedLL_M15 logic, sets BUY TP always to DefaultTP_Buy_M15, replaces static SELL SL with dynamicSL_Sell/lastAcceptedHH_M15 logic, and shifts SELL entry from close-3 points to close-5 points.");
  lines.push("");

  lines.push("## 3. CSV Coverage and Data Hygiene");
  const fileSummary = GROUPS.map((g) => {
    const files = fileAudits.filter((f) => f.version === g.key);
    return { version: g.key, files: files.length, failed: files.filter((f) => f.status !== "OK").length, rows: sum(files.map((f) => f.rows)), malformed: sum(files.map((f) => f.malformed)) };
  });
  lines.push(mdTable(fileSummary, [
    { h: "Version", v: (r) => r.version },
    { h: "CSV audited recursively", v: (r) => r.files },
    { h: "Failed", v: (r) => r.failed },
    { h: "Rows", v: (r) => r.rows },
    { h: "Malformed lines", v: (r) => r.malformed },
  ]));
  lines.push("");
  lines.push("- `backtest statis/sBacktest_Results_XAUUSD_2020-12-30.csv` exists as a nested extra file and has different session labels from the canonical direct 2020 result. It is audited in file coverage but excluded from aggregate stats to avoid double-counting 2020.");
  lines.push("- `backtest dynamic hybrid/MarketData_XAUUSD_H1_2024-06-14.csv` overlaps with the 2024-12-30 H1 file. Market bars are deduped by timestamp.");
  lines.push("");

  lines.push("## 4. Yearly Comparison: Entry, SL, TP, Session, Hour, Analysis, Solution");
  lines.push(mdTable(yearRows, [
    { h: "Year", v: (r) => r.year },
    { h: "Ver", v: (r) => r.version },
    { h: "Trades/WR/Net/PF", v: (r) => `${r.trades} / ${r.wr} / ${r.net} / ${r.pf}` },
    { h: "Entry mix", v: (r) => r.entryMix },
    { h: "Entry/SL/TP set", v: (r) => `${r.entrySet}; avgSL ${r.avgSL}; avgTP ${r.avgTP}; RR ${r.avgRR}` },
    { h: "Best/Worst session", v: (r) => `${r.bestSession} / ${r.worstSession}` },
    { h: "Best/Worst hour", v: (r) => `${r.bestHour} / ${r.worstHour}` },
    { h: "Best trade", v: (r) => r.bestTrade },
    { h: "Worst trade", v: (r) => r.worstTrade },
    { h: "Analysis", v: (r) => r.analysis },
    { h: "Solution", v: (r) => r.solution },
  ]));
  lines.push("");

  lines.push("## 5. Matched Trade Comparison");
  lines.push(`Matched v5-v7 trades by year/ticket/type: ${matches.length}.`);
  lines.push(mdTable(outcomeRows, [
    { h: "Outcome change", v: (r) => r.outcome },
    { h: "Trades", v: (r) => r.trades },
    { h: "v7-v5 net delta", v: (r) => r.diffNet },
    { h: "Avg v5 SL", v: (r) => r.avgV5SL },
    { h: "Avg v7 SL", v: (r) => r.avgV7SL },
  ]));
  lines.push("");
  const worstDelta = matches.slice().sort((a, b) => a.diffNet - b.diffNet).slice(0, 12);
  const bestDelta = matches.slice().sort((a, b) => b.diffNet - a.diffNet).slice(0, 12);
  lines.push("Worst v7-v5 deltas:");
  lines.push(mdTable(worstDelta, [
    { h: "Year", v: (r) => r.year },
    { h: "Ticket", v: (r) => r.ticket },
    { h: "Type", v: (r) => r.type },
    { h: "Entry", v: (r) => r.entryTime },
    { h: "Session", v: (r) => r.v7Session },
    { h: "v5 SL/TP/net", v: (r) => `${fmt(r.v5SLPts, 0)}/${fmt(r.v5TPPts, 0)}/${fmt(r.v5Net)}` },
    { h: "v7 SL/TP/net", v: (r) => `${fmt(r.v7SLPts, 0)}/${fmt(r.v7TPPts, 0)}/${fmt(r.v7Net)}` },
    { h: "Delta", v: (r) => fmt(r.diffNet) },
    { h: "Analysis", v: (r) => r.v7SLPts > r.v5SLPts ? "v7 SL wider; larger loss or delayed exit" : "v7 SL tighter/capped; stopped before v5 outcome" },
    { h: "Solution", v: () => "Use final-risk cap after buffer; test BE/partial rules on reversal clusters." },
  ]));
  lines.push("");
  lines.push("Best v7-v5 deltas:");
  lines.push(mdTable(bestDelta, [
    { h: "Year", v: (r) => r.year },
    { h: "Ticket", v: (r) => r.ticket },
    { h: "Type", v: (r) => r.type },
    { h: "Entry", v: (r) => r.entryTime },
    { h: "Session", v: (r) => r.v7Session },
    { h: "v5 SL/TP/net", v: (r) => `${fmt(r.v5SLPts, 0)}/${fmt(r.v5TPPts, 0)}/${fmt(r.v5Net)}` },
    { h: "v7 SL/TP/net", v: (r) => `${fmt(r.v7SLPts, 0)}/${fmt(r.v7TPPts, 0)}/${fmt(r.v7Net)}` },
    { h: "Delta", v: (r) => fmt(r.diffNet) },
    { h: "Analysis", v: (r) => r.v7SLPts > r.v5SLPts ? "structure+buffer survived pullback" : "tighter hybrid reduced loss" },
    { h: "Solution", v: () => "Keep only when regime/session also positive; avoid treating isolated saved trades as universal proof." },
  ]));
  lines.push("");

  lines.push("## 6. Ideal Market Conditions");
  lines.push(`Regime thresholds from actual entries: vol16 Q25=${fmt(thresholds.volQ25)} pts, vol16 Q75=${fmt(thresholds.volQ75)} pts, abs EMA gap Q25=${fmt(thresholds.gapQ25)} pts, abs M15 slope16 Q25=${fmt(thresholds.slopeQ25)} pts.`);
  lines.push(mdTable(idealRows.slice(0, 30), [
    { h: "Ver", v: (r) => r.version },
    { h: "Feature", v: (r) => r.feature },
    { h: "Value", v: (r) => r.value },
    { h: "Trades", v: (r) => r.trades },
    { h: "WR", v: (r) => r.wr },
    { h: "Net", v: (r) => r.net },
    { h: "PF", v: (r) => r.pf },
    { h: "Lift", v: (r) => r.lift },
    { h: "Analysis", v: (r) => r.analysis },
    { h: "Solution", v: (r) => r.solution },
  ]));
  lines.push("");

  lines.push("## 7. Dangerous Market Regimes and Bad Clusters");
  lines.push(mdTable(dangerRows.slice(0, 40), [
    { h: "Ver", v: (r) => r.version },
    { h: "Feature", v: (r) => r.feature },
    { h: "Value", v: (r) => r.value },
    { h: "Trades", v: (r) => r.trades },
    { h: "WR", v: (r) => r.wr },
    { h: "Net", v: (r) => r.net },
    { h: "PF", v: (r) => r.pf },
    { h: "Lift", v: (r) => r.lift },
    { h: "Analysis", v: (r) => r.analysis },
    { h: "Solution", v: (r) => r.solution },
  ]));
  lines.push("");

  lines.push("## 8. Fake Reversal / Session-Hour Patterns by Year");
  lines.push(mdTable(reversal, [
    { h: "Ver", v: (r) => r.version },
    { h: "Year", v: (r) => r.year },
    { h: "Losses", v: (r) => r.losses },
    { h: "No follow", v: (r) => r.noFollow },
    { h: "Right then reversed", v: (r) => r.rightThenReversed },
    { h: "Stopped then TP <=96h", v: (r) => r.stoppedThenTp96h },
    { h: "Worst session/hour", v: (r) => `${r.worstSession} / ${r.worstHour}` },
    { h: "Example entry/SL/TP/session/hour", v: (r) => r.example },
    { h: "Analysis", v: (r) => r.analysis },
    { h: "Solution", v: (r) => r.solution },
  ]));
  lines.push("");

  lines.push("## 9. SL/TP, Hold-Time, and Export Integrity Checks");
  lines.push(mdTable(slBugRows, [
    { h: "Ver", v: (r) => r.version },
    { h: "SL >3000 count/net", v: (r) => `${r.slGt3000}/${r.slGt3000Net}` },
    { h: "SL <2100 count/net", v: (r) => `${r.slLt2100}/${r.slLt2100Net}` },
    { h: "Duration >24h", v: (r) => r.dur24 },
    { h: "Lot mismatch count", v: (r) => r.lotMismatch },
    { h: "Avg inferred lot", v: (r) => r.avgInferredLot },
    { h: "Avg CSV lot", v: (r) => r.avgCsvLot },
  ]));
  lines.push("");
  for (const g of GROUPS) {
    const tr = allTrades.filter((t) => t.version === g.key);
    lines.push(`### ${g.key} by entry set`);
    lines.push(mdTable(groupRows(tr, (t) => t.entrySet).sort((a, b) => b.trades - a.trades), [
      { h: "Entry/SL/TP set", v: (r) => r.key },
      { h: "Trades", v: (r) => r.trades },
      { h: "WR", v: (r) => pct(r.winrate) },
      { h: "Net", v: (r) => fmt(r.totalNet) },
      { h: "PF", v: (r) => fmt(r.profitFactor) },
      { h: "Avg SL", v: (r) => fmt(r.avgSlPts, 0) },
      { h: "Avg TP", v: (r) => fmt(r.avgTpPts, 0) },
    ]));
    lines.push("");
  }

  lines.push("## 10. Overfit Risk");
  const yearly = groupRows(allTrades, (t) => `${t.version}_${t.year}`);
  const overfit = GROUPS.map((g) => {
    const yr = yearly.filter((r) => r.key.startsWith(`${g.key}_`));
    const nets = yr.map((r) => r.totalNet);
    const pos = nets.filter((n) => n > 0).sort((a, b) => b - a);
    const totalPositive = sum(pos);
    const top2Share = totalPositive ? sum(pos.slice(0, 2)) / totalPositive : NaN;
    return {
      version: g.key,
      positiveYears: nets.filter((n) => n > 0).length,
      negativeYears: nets.filter((n) => n < 0).length,
      worstYear: yr.slice().sort((a, b) => a.totalNet - b.totalNet)[0]?.key || "",
      bestYear: yr.slice().sort((a, b) => b.totalNet - a.totalNet)[0]?.key || "",
      top2Share: pct(top2Share),
      evidence: "Hardcoded point thresholds, disabled session/news filters, and strong dependency on a small set of yearly regimes.",
      risk: top2Share > 0.65 || nets.filter((n) => n < 0).length >= 2 ? "HIGH" : "MEDIUM",
    };
  });
  lines.push(mdTable(overfit, [
    { h: "Ver", v: (r) => r.version },
    { h: "Positive years", v: (r) => r.positiveYears },
    { h: "Negative years", v: (r) => r.negativeYears },
    { h: "Best year", v: (r) => r.bestYear },
    { h: "Worst year", v: (r) => r.worstYear },
    { h: "Top-2 positive share", v: (r) => r.top2Share },
    { h: "Evidence", v: (r) => r.evidence },
    { h: "Risk", v: (r) => r.risk },
  ]));
  lines.push("");

  lines.push("## 11. Recommendations Bound to Evidence");
  lines.push("1. Fix v7 SL formula to cap final risk after the 1000-point buffer, not before it. Example: BUY final SL should be `MathMax(lastAcceptedLL_M15 - buffer, entryPrice_M15 - maxRisk)`; SELL final SL should be `MathMin(lastAcceptedHH_M15 + buffer, entryPrice_M15 + maxRisk)`.");
  lines.push("2. Restore BUY entry-count TP logic in v7 or intentionally remove Entry2TP_Buy_M15/Entry3TP_Buy_M15. Current source leaves BUY Entry2 TP inputs unused.");
  lines.push("3. Move M15 detection before the H1 unchanged-bar return, or keep independent last-bar gates per timeframe. Current code suppresses three out of four M15 bars.");
  lines.push("4. Export actual deal volume instead of hardcoded `lotSize = 0.01`; otherwise risk, cost, and lot-based analytics are contaminated.");
  lines.push("5. Activate or delete MaxHoldHours/MinHoldHours logic. The CSV contains trades far beyond 24h while the source advertises a 24h max hold input.");
  lines.push("6. Use the danger table as no-trade/risk-reduction candidates, then retest out-of-sample by year. Do not optimize only on total net; the yearly tables show regime instability.");
  lines.push("");

  lines.push("## 12. Limits");
  lines.push("- Intrabar tick order is unavailable, so same-M15-bar TP/SL conflicts are marked path-ambiguous.");
  lines.push("- Session labels are taken from the EA CSV/source, but source uses `TimeCurrent`; broker-server timezone is not separately exported.");
  lines.push("- No external calendar/news data was used; every conclusion above comes from supplied source and CSV only.");
  lines.push("");

  return lines.join("\n");
}

function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const allTrades = [];
  const fileAudits = [];
  const groupData = {};
  for (const g of GROUPS) {
    const recursiveFiles = listCsvRecursive(g.dir);
    const directFiles = listCsvDirect(g.dir);
    fileAudits.push(...fileAudit(g, recursiveFiles));
    const marketFiles = directFiles;
    const m15 = loadMarket(marketFiles, "M15");
    const h1 = loadMarket(marketFiles, "H1");
    const events = loadEvents(marketFiles);
    const trades = loadTrades(g, directFiles);
    addMarketFeatures(trades, m15, h1, events);
    groupData[g.key] = { m15: m15.length, h1: h1.length, events: events.length, trades: trades.length };
    allTrades.push(...trades);
  }
  const thresholds = classify(allTrades);
  for (const t of allTrades) {
    t.entrySet = inferEntrySet(t);
  }
  const matchRows = matchedRows(allTrades);
  const data = { allTrades, fileAudits, groupData, thresholds, matchRows };
  const report = makeReport(data);
  const reportPath = path.join(OUT_DIR, "AUDIT_V5_V7_FORENSIC_2026-05-17.md");
  fs.writeFileSync(reportPath, report, "utf8");
  writeCsv("Dokumen/Audit/v5_v7_file_audit.csv", fileAudits, ["version", "file", "status", "rows", "malformed", "start", "end", "columns"]);
  writeCsv("Dokumen/Audit/v5_v7_trade_features.csv", allTrades, [
    "version", "file", "ticket", "type", "entryRaw", "exitRaw", "entry", "exit", "sl", "tp", "profit", "net",
    "session", "hour", "minute", "weekday", "year", "month", "durationHours", "lotCsv", "inferredLot",
    "slPts", "tpPts", "rr", "entrySet", "exitReason", "emaGapPts", "emaSideAligned", "m15Slope4Pts",
    "m15Slope16Pts", "m15SlopeAligned", "h1GapPts", "h1SideAligned", "h1Slope4Pts", "h1SlopeAligned",
    "vol16Pts", "atr14Pts", "volRegime", "marketRegime", "mfePts", "maePts", "mfeToTp", "maeToSl",
    "pathHit", "postExitFavorablePts96h", "postExitOriginalTpHit96h", "lossPattern", "winPattern",
    "lastBosDirection", "lastBosAgeHours", "lastBosPrice", "lastChochDirection", "lastChochAgeHours",
  ]);
  writeCsv("Dokumen/Audit/v5_v7_matched_trades.csv", matchRows.map((r) => ({
    year: r.year,
    ticket: r.ticket,
    type: r.type,
    entryTime: r.entryTime,
    v5Session: r.v5Session,
    v7Session: r.v7Session,
    v5SLPts: r.v5SLPts,
    v7SLPts: r.v7SLPts,
    v5TPPts: r.v5TPPts,
    v7TPPts: r.v7TPPts,
    v5Net: r.v5Net,
    v7Net: r.v7Net,
    diffNet: r.diffNet,
    outcomeChange: r.outcomeChange,
  })), ["year", "ticket", "type", "entryTime", "v5Session", "v7Session", "v5SLPts", "v7SLPts", "v5TPPts", "v7TPPts", "v5Net", "v7Net", "diffNet", "outcomeChange"]);
  fs.writeFileSync(path.join(OUT_DIR, "v5_v7_summary.json"), JSON.stringify({
    generatedAt: new Date().toISOString(),
    groupData,
    thresholds,
    master: GROUPS.map((g) => ({ version: g.key, ...metrics(allTrades.filter((t) => t.version === g.key)) })),
    matchedTrades: matchRows.length,
  }, null, 2), "utf8");
  console.log(`Wrote ${reportPath}`);
  console.log(`Trades analyzed: ${allTrades.length}`);
  console.log(`Matched trades: ${matchRows.length}`);
  console.log(`CSV files audited: ${fileAudits.length}`);
}

main();
