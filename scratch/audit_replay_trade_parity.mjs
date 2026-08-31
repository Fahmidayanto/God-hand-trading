const API_URL = "http://127.0.0.1:8000/api/v1/trading/replay";
const query = new URLSearchParams({
  year_from: "2026",
  month_from: "1",
  year_to: "2026",
  month_to: "8",
});

async function fetchReplay(timeframe) {
  const response = await fetch(`${API_URL}?${query}&timeframe=${timeframe}`);
  if (!response.ok) throw new Error(`${timeframe} replay ${response.status}: ${await response.text()}`);
  return response.json();
}

const [m15Data, h1Data, h4Data] = await Promise.all([
  fetchReplay("M15"),
  fetchReplay("H1"),
  fetchReplay("H4"),
]);

const params = {
  entry_choch: true,
  entry_bos: true,
  entry_bos_cycle_2_plus: true,
  max_bos_cycle: 2,
  h1_ema200_filter: true,
  h4_ema_filter: true,
  ema_slope_filter: true,
  body_ratio_filter: false,
  session_filter: false,
};

function candleIndexAtOrBefore(candles, time) {
  let result = -1;
  for (let index = 0; index < candles.length && candles[index].time <= time; index += 1) result = index;
  return result;
}

function candleAtOrBefore(candles, time) {
  const index = candleIndexAtOrBefore(candles, time);
  return index >= 0 ? candles[index] : null;
}

function getEntryStructureInfo(entryTime, structures, direction = "") {
  let latestType = "";
  let latestTypeBuy = "";
  let latestTypeSell = "";
  let bosCycleBuy = 0;
  let bosCycleSell = 0;

  for (const event of structures) {
    if (event.time > entryTime) break;
    if (event.timeframe && event.timeframe.toUpperCase() !== "M15") continue;

    const type = String(event.type ?? "").toUpperCase();
    const eventDirection = String(event.direction ?? "").toUpperCase();
    const isBull = eventDirection.includes("BULL") || type.includes("BULL");
    const isBear = eventDirection.includes("BEAR") || type.includes("BEAR");

    if (type.includes("CHOCH")) {
      latestType = "CHOCH";
      if (isBull) {
        latestTypeBuy = "CHOCH";
        bosCycleBuy = 0;
      }
      if (isBear) {
        latestTypeSell = "CHOCH";
        bosCycleSell = 0;
      }
    } else if (type.includes("BOS")) {
      latestType = "BOS";
      if (isBull) {
        latestTypeBuy = "BOS";
        bosCycleBuy += 1;
      }
      if (isBear) {
        latestTypeSell = "BOS";
        bosCycleSell += 1;
      }
    }
  }

  const upperDirection = direction.toUpperCase();
  const isSell = upperDirection.includes("SELL") || upperDirection.includes("BEAR");
  const effectiveLatestType = isSell ? latestTypeSell || latestType : latestTypeBuy || latestType;
  return { latestType: effectiveLatestType, bosCycle: isSell ? bosCycleSell : bosCycleBuy };
}

function entryFilterReason(trade) {
  const { latestType, bosCycle } = getEntryStructureInfo(trade.entry_time, m15Data.structures, trade.type);
  if (latestType === "CHOCH" && !params.entry_choch) return "CHoCH disabled";
  if (latestType === "BOS") {
    if (bosCycle === 1 && !params.entry_bos) return "BOS 1 disabled";
    if (bosCycle >= 2 && !params.entry_bos_cycle_2_plus) return "BOS 2+ disabled";
    if (params.max_bos_cycle > 0 && bosCycle > params.max_bos_cycle) return `Max BOS Cycle (${params.max_bos_cycle})`;
  }
  if (latestType !== "CHOCH" && latestType !== "BOS") return "No CHoCH/BOS context";

  const isBuy = trade.type.toUpperCase() === "BUY";
  const m15Index = candleIndexAtOrBefore(m15Data.candles, trade.entry_time);
  const m15Candle = m15Index > 0 ? m15Data.candles[m15Index - 1] : null;
  const previousM15 = m15Index > 1 ? m15Data.candles[m15Index - 2] : null;
  const currentPrice = trade.entry_price > 0
    ? trade.entry_price
    : m15Data.candles[m15Index]?.open ?? m15Candle?.close ?? 0;
  const h1Candle = candleAtOrBefore(h1Data.candles, trade.entry_time);
  const h4Candle = candleAtOrBefore(h4Data.candles, trade.entry_time);

  if (params.session_filter && new Date(trade.entry_time * 1000).getUTCHours() === 1) return "Session Filter";
  if (params.h1_ema200_filter && h1Candle?.ema200 > 0 && (isBuy ? currentPrice <= h1Candle.ema200 : currentPrice >= h1Candle.ema200)) return "H1 EMA200 Filter";
  if (params.h4_ema_filter && h4Candle?.ema200 > 0) {
    const gapThreshold = Math.max(h4Candle.ema200 * 0.0025, 5);
    if (isBuy ? currentPrice <= h4Candle.ema200 + gapThreshold : currentPrice >= h4Candle.ema200 - gapThreshold) return "H4 EMA Filter";
  }
  if (params.ema_slope_filter) {
    if (m15Candle?.ema200 == null || previousM15?.ema200 == null) return "EMA Slope Filter";
    if (isBuy ? m15Candle.ema200 <= previousM15.ema200 : m15Candle.ema200 >= previousM15.ema200) return "EMA Slope Filter";
  }
  return null;
}

function key(type, entryTime) {
  return `${type}_${entryTime}`;
}

const rawExecuted = m15Data.trades.filter((trade) => trade.status === "EXECUTED");
const candidateMap = new Map();

for (const event of m15Data.structures) {
  const type = String(event.type ?? "").toUpperCase();
  const direction = String(event.direction ?? "").toUpperCase();
  if (!type.includes("CHOCH") && !type.includes("BOS")) continue;
  if (!direction.includes("BULL") && !direction.includes("BEAR")) continue;

  const tradeType = direction.includes("BULL") ? "BUY" : "SELL";
  const entryTime = Number(event.time) + 900;
  const eventCandle = m15Data.candles.find((candle) => candle.time === Number(event.time));
  if (!eventCandle) continue;
  const spread = eventCandle.spread > 0 ? eventCandle.spread : 3;
  const entryPrice = tradeType === "BUY"
    ? Number((eventCandle.close + spread * 0.01).toFixed(2))
    : eventCandle.close;
  const candidate = { type: tradeType, entry_time: entryTime, entry_price: entryPrice, source_event: type };
  candidateMap.set(key(tradeType, entryTime), candidate);
}

const uiCandidates = [...candidateMap.values()].map((candidate) => ({
  ...candidate,
  rejectReason: entryFilterReason(candidate),
}));
const uiExecuted = uiCandidates.filter((candidate) => candidate.rejectReason === null);
const uiRejected = uiCandidates.filter((candidate) => candidate.rejectReason !== null);
const uiMap = new Map(uiCandidates.map((candidate) => [key(candidate.type, candidate.entry_time), candidate]));
const rawMap = new Map(rawExecuted.map((trade) => [key(trade.type, trade.entry_time), trade]));

const rawMatchedUiExecuted = rawExecuted.filter((trade) => uiMap.get(key(trade.type, trade.entry_time))?.rejectReason === null);
const rawMatchedUiRejected = rawExecuted
  .filter((trade) => uiMap.get(key(trade.type, trade.entry_time))?.rejectReason !== null && uiMap.has(key(trade.type, trade.entry_time)))
  .map((trade) => ({
    ticket: trade.ticket,
    type: trade.type,
    entry_time: trade.entry_time,
    net_profit: trade.net_profit,
    reason: uiMap.get(key(trade.type, trade.entry_time)).rejectReason,
  }));
const rawOnly = rawExecuted.map((trade) => {
  const exactKey = key(trade.type, trade.entry_time);
  if (uiMap.has(exactKey)) return null;
  const nearest = uiCandidates
    .filter((candidate) => candidate.type === trade.type)
    .map((candidate) => ({ candidate, offset: candidate.entry_time - trade.entry_time }))
    .sort((left, right) => Math.abs(left.offset) - Math.abs(right.offset))[0];
  return {
    ticket: trade.ticket,
    type: trade.type,
    entry_time: trade.entry_time,
    net_profit: trade.net_profit,
    nearest_offset_seconds: nearest?.offset ?? null,
  };
}).filter(Boolean);
const uiExecutedOnly = uiExecuted.filter((candidate) => !rawMap.has(key(candidate.type, candidate.entry_time)));

const rejectionCounts = Object.groupBy(uiRejected, (candidate) => candidate.rejectReason);
const rejectionSummary = Object.fromEntries(
  Object.entries(rejectionCounts).map(([reason, candidates]) => [reason, candidates.length]),
);

console.log(JSON.stringify({
  rawApi: { executed: rawExecuted.length },
  uiSimulator: {
    candidates: uiCandidates.length,
    executed: uiExecuted.length,
    rejected: uiRejected.length,
    rejectionSummary,
  },
  overlap: {
    exactTimeDirection: rawExecuted.length - rawOnly.length,
    rawMatchedUiExecuted: rawMatchedUiExecuted.length,
    rawMatchedUiRejected: rawMatchedUiRejected.length,
    rawOnly: rawOnly.length,
    uiExecutedOnly: uiExecutedOnly.length,
  },
  rawMatchedUiRejected,
  rawOnly,
  uiExecutedOnly,
}, null, 2));