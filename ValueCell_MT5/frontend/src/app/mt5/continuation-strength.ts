export interface ContinuationCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema200: number | null;
}

export interface ContinuationStrengthInput {
  direction: string;
  entryPrice: number;
  currentCandle: ContinuationCandle;
  previousCandles: ContinuationCandle[];
  atr: number | null;
  structureAligned: boolean;
}

export interface ContinuationStrengthComponent {
  key: "structure" | "momentum" | "directional" | "trend" | "activity";
  label: string;
  score: number;
  maximum: number;
  passed: boolean;
  reason: string;
}

export interface ContinuationStrengthResult {
  score: number;
  status: "STRONG" | "NEUTRAL" | "WEAK";
  components: ContinuationStrengthComponent[];
}

export function evaluateContinuationStrength({
  direction,
  entryPrice,
  currentCandle,
  previousCandles,
  atr,
  structureAligned,
}: ContinuationStrengthInput): ContinuationStrengthResult {
  const isBuy = direction.toUpperCase().includes("BUY");
  const directionalMove = isBuy
    ? currentCandle.close - entryPrice
    : entryPrice - currentCandle.close;
  const momentumAligned = atr !== null && atr > 0 && directionalMove >= atr * 0.5;
  const candleAligned = isBuy
    ? currentCandle.close > currentCandle.open
    : currentCandle.close < currentCandle.open;
  const trendAligned = currentCandle.ema200 !== null && (isBuy
    ? currentCandle.close > currentCandle.ema200
    : currentCandle.close < currentCandle.ema200);
  const averageVolume = previousCandles.length > 0
    ? previousCandles.reduce((total, candle) => total + candle.volume, 0) / previousCandles.length
    : null;
  const activityAligned = averageVolume !== null && currentCandle.volume >= averageVolume;

  const components: ContinuationStrengthComponent[] = [
    {
      key: "structure",
      label: "Structure",
      score: structureAligned ? 30 : 0,
      maximum: 30,
      passed: structureAligned,
      reason: structureAligned ? "Struktur terbaru searah posisi." : "Struktur terbaru belum mengonfirmasi arah posisi.",
    },
    {
      key: "momentum",
      label: "Momentum ATR",
      score: momentumAligned ? 20 : 0,
      maximum: 20,
      passed: momentumAligned,
      reason: momentumAligned
        ? `Harga bergerak ${directionalMove.toFixed(2)}, minimal 0.5 x ATR.`
        : "Pergerakan harga belum mencapai 0.5 x ATR dari entry.",
    },
    {
      key: "directional",
      label: "Directional Candle",
      score: candleAligned ? 20 : 0,
      maximum: 20,
      passed: candleAligned,
      reason: candleAligned ? "Candle saat ini searah posisi." : "Candle saat ini berlawanan atau datar.",
    },
    {
      key: "trend",
      label: "EMA200 Trend",
      score: trendAligned ? 15 : 0,
      maximum: 15,
      passed: trendAligned,
      reason: trendAligned ? "Harga berada di sisi EMA200 yang mendukung posisi." : "EMA200 belum mendukung arah posisi.",
    },
    {
      key: "activity",
      label: "Market Activity",
      score: activityAligned ? 15 : 0,
      maximum: 15,
      passed: activityAligned,
      reason: activityAligned ? "Volume saat ini >= rata-rata candle pembanding." : "Volume saat ini di bawah rata-rata candle pembanding.",
    },
  ];

  const score = components.reduce((total, component) => total + component.score, 0);
  const status = score >= 70 ? "STRONG" : score >= 40 ? "NEUTRAL" : "WEAK";

  return { score, status, components };
}