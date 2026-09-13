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
  structure?: ContinuationStructure | null;
}

export interface ContinuationStrengthConfig {
  bosFollowThroughAtr: number;
  maximumStructureAgeCandles: number | null;
  momentumLookback: number;
  directionalMode: "single" | "average" | "majority" | "strict" | "smoothed";
  directionalLookback: number;
  directionalBodyThreshold: number;
  directionalCloseThreshold: number;
  directionalRangeAtrThreshold: number;
  directionalWeight: number;
  emaSlopeLookback: number;
  emaSlopeMethod: "endpoint" | "average" | "confirmation" | "atr-normalized";
  emaMinimumDistanceAtr: number;
  emaWeight: number;
  volumeLookback: number;
  volumeMethod: "average" | "median" | "ema" | "trimmed-mean";
  volumeLowThreshold: number;
  volumeStrongThreshold: number;
  volumeImpulseThreshold: number;
  volumeMode: "independent" | "directional" | "penalty" | "confirmation";
  volumeWeight: number;
}

export const DEFAULT_CONTINUATION_STRENGTH_CONFIG: ContinuationStrengthConfig = {
  bosFollowThroughAtr: 0.5,
  maximumStructureAgeCandles: 4,
  momentumLookback: 3,
  directionalMode: "single",
  directionalLookback: 1,
  directionalBodyThreshold: 0.7,
  directionalCloseThreshold: 0.8,
  directionalRangeAtrThreshold: 1,
  directionalWeight: 20,
  emaSlopeLookback: 3,
  emaSlopeMethod: "endpoint",
  emaMinimumDistanceAtr: 0,
  emaWeight: 15,
  volumeLookback: 20,
  volumeMethod: "average",
  volumeLowThreshold: 0.8,
  volumeStrongThreshold: 1.2,
  volumeImpulseThreshold: 1.6,
  volumeMode: "directional",
  volumeWeight: 15,
};

export interface ContinuationStructure {
  type: string;
  direction: string;
  price: number;
  time: number;
  timeframe?: string;
  status?: string;
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
  reversalScore: number;
  state: ContinuationState;
  confidence: number;
  components: ContinuationStrengthComponent[];
}

export type ContinuationState =
  | "STRONG_CONTINUATION"
  | "HEALTHY_PULLBACK"
  | "MOMENTUM_EXHAUSTION"
  | "REVERSAL_CONFIRMED"
  | "UNCERTAIN";

export type ContinuationTrendStatus =
  | "IMPROVING"
  | "STABLE"
  | "DECLINING"
  | "RAPID_DECLINE"
  | "INSUFFICIENT_DATA";

export function classifyContinuationState({
  continuationScore,
  reversalScore,
  trendStatus,
}: {
  continuationScore: number;
  reversalScore: number;
  trendStatus: ContinuationTrendStatus;
}): { state: ContinuationState; confidence: number } {
  const confidence = Math.min(100, Math.round(Math.abs(continuationScore - reversalScore)));
  if (continuationScore >= 70 && reversalScore <= 30 && trendStatus !== "RAPID_DECLINE") {
    return { state: "STRONG_CONTINUATION", confidence };
  }
  if (continuationScore <= 30 && reversalScore >= 70 && trendStatus === "RAPID_DECLINE") {
    return { state: "REVERSAL_CONFIRMED", confidence };
  }
  if (continuationScore >= 45 && reversalScore < 45) {
    return { state: "HEALTHY_PULLBACK", confidence };
  }
  if (continuationScore < 45 && reversalScore >= 45) {
    return { state: "MOMENTUM_EXHAUSTION", confidence };
  }
  return { state: "UNCERTAIN", confidence };
}

export function classifyContinuationTrend(scores: number[]): {
  status: ContinuationTrendStatus;
  change: number;
} {
  const recentScores = scores.slice(-3);
  const change = recentScores.length >= 2
    ? recentScores.at(-1)! - recentScores[0]
    : 0;
  if (recentScores.length < 3) return { status: "INSUFFICIENT_DATA", change };

  const [first, second, third] = recentScores;
  if (change <= -20) return { status: "RAPID_DECLINE", change };
  if (first > second && second > third) return { status: "DECLINING", change };
  if (first < second && second < third) return { status: "IMPROVING", change };
  return { status: "STABLE", change };
}

export function evaluateStructureStrength({
  direction,
  currentCandle,
  atr,
  structure,
  config = DEFAULT_CONTINUATION_STRENGTH_CONFIG,
}: {
  direction: string;
  currentCandle: ContinuationCandle;
  atr: number | null;
  structure: ContinuationStructure | null;
  config?: Partial<ContinuationStrengthConfig>;
}): { score: number; passed: boolean; reason: string } {
  if (!structure) return { score: 5, passed: false, reason: "Belum ada struktur M15 valid terbaru." };

  const directionUpper = direction.toUpperCase();
  const structureDirection = `${structure.direction ?? ""} ${structure.type ?? ""}`.toUpperCase();
  const aligned = directionUpper.includes("BUY")
    ? structureDirection.includes("BULL") || structureDirection.includes("BUY")
    : structureDirection.includes("BEAR") || structureDirection.includes("SELL");
  if (!aligned) return { score: 0, passed: false, reason: "Struktur M15 terbaru berlawanan dengan posisi." };

  const maximumStructureAgeCandles = config.maximumStructureAgeCandles
    ?? (config.maximumStructureAgeCandles === null ? null : DEFAULT_CONTINUATION_STRENGTH_CONFIG.maximumStructureAgeCandles);
  const ageSeconds = Math.max(0, currentCandle.time - structure.time);
  if (maximumStructureAgeCandles !== null && ageSeconds > maximumStructureAgeCandles * 15 * 60) {
    return { score: 10, passed: false, reason: `Struktur searah sudah lebih lama dari ${maximumStructureAgeCandles} candle M15.` };
  }

  const accepted = !structure.status || structure.status.toUpperCase() === "ACCEPTED";
  if (!accepted) return { score: 10, passed: false, reason: "Struktur searah masih preliminary dan belum accepted." };

  const type = structure.type.toUpperCase();
  if (type.includes("CHOCH")) return { score: 15, passed: true, reason: "CHoCH M15 searah memberi konfirmasi awal." };
  if (!type.includes("BOS")) return { score: 10, passed: false, reason: "Struktur searah belum berupa CHoCH atau BoS terkonfirmasi." };

  const followThrough = directionUpper.includes("BUY")
    ? currentCandle.close - structure.price
    : structure.price - currentCandle.close;
  const followThroughRatio = atr !== null && atr > 0 ? followThrough / atr : 0;
  const bosFollowThroughAtr = config.bosFollowThroughAtr ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.bosFollowThroughAtr;
  return followThroughRatio >= bosFollowThroughAtr
    ? { score: 30, passed: true, reason: `BoS accepted dengan follow-through ${followThroughRatio.toFixed(2)} x ATR.` }
    : { score: 22, passed: true, reason: `BoS accepted; follow-through baru ${followThroughRatio.toFixed(2)} x ATR.` };
}

function getDirectionalEvidence(
  candle: ContinuationCandle,
  isBuy: boolean,
  atr: number | null,
  config: Partial<ContinuationStrengthConfig>,
) {
  const range = Math.max(0, candle.high - candle.low);
  const bodyRatio = range > 0 ? Math.abs(candle.close - candle.open) / range : 0;
  const rangeAtrRatio = atr !== null && atr > 0 ? range / atr : 0;
  const aligned = isBuy ? candle.close > candle.open : candle.close < candle.open;
  const closeLocation = range > 0
    ? isBuy ? (candle.close - candle.low) / range : (candle.high - candle.close) / range
    : 0.5;
  const bodyThreshold = config.directionalBodyThreshold ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.directionalBodyThreshold;
  const closeThreshold = config.directionalCloseThreshold ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.directionalCloseThreshold;
  const rangeThreshold = config.directionalRangeAtrThreshold ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.directionalRangeAtrThreshold;
  const score = bodyRatio < 0.1
    ? 5
    : !aligned
      ? bodyRatio >= 0.5 ? 0 : 5
      : bodyRatio >= bodyThreshold && closeLocation >= closeThreshold && rangeAtrRatio >= rangeThreshold
        ? 20
        : bodyRatio >= Math.min(0.5, bodyThreshold) && closeLocation >= Math.min(0.65, closeThreshold)
          ? 15
          : 10;
  return { score, aligned, bodyRatio, closeLocation, rangeAtrRatio };
}

function getVolumeBaseline(values: number[], method: ContinuationStrengthConfig["volumeMethod"]): number | null {
  if (values.length === 0) return null;
  if (method === "median") {
    const sorted = [...values].sort((left, right) => left - right);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle];
  }
  if (method === "ema") {
    const multiplier = 2 / (values.length + 1);
    return values.slice(1).reduce((value, current) => current * multiplier + value * (1 - multiplier), values[0]);
  }
  if (method === "trimmed-mean" && values.length >= 3) {
    const sorted = [...values].sort((left, right) => left - right).slice(1, -1);
    return sorted.reduce((total, value) => total + value, 0) / sorted.length;
  }
  return values.reduce((total, value) => total + value, 0) / values.length;
}

export function evaluateContinuationStrength({
  direction,
  entryPrice,
  currentCandle,
  previousCandles,
  atr,
  structureAligned,
  structure,
}: ContinuationStrengthInput, config: Partial<ContinuationStrengthConfig> = {}): ContinuationStrengthResult {
  const isBuy = direction.toUpperCase().includes("BUY");
  const momentumLookback = Math.max(1, Math.round(config.momentumLookback ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.momentumLookback));
  const localMomentumReference = previousCandles.at(-momentumLookback)?.close;
  const localDirectionalMove = localMomentumReference == null
    ? 0
    : isBuy
      ? currentCandle.close - localMomentumReference
      : localMomentumReference - currentCandle.close;
  const momentumAtrRatio = atr !== null && atr > 0 ? localDirectionalMove / atr : 0;
  const momentumScore = momentumAtrRatio >= 1
    ? 20
    : momentumAtrRatio >= 0.5
      ? 15
      : momentumAtrRatio >= 0.25
        ? 10
        : momentumAtrRatio > 0
          ? 5
          : 0;
  const directionalLookback = Math.max(1, Math.round(config.directionalLookback ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.directionalLookback));
  const directionalMode = config.directionalMode ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.directionalMode;
  const directionalEvidence = [...previousCandles.slice(-(directionalLookback - 1)), currentCandle]
    .map((candle) => getDirectionalEvidence(candle, isBuy, atr, config));
  const currentDirectional = directionalEvidence.at(-1)!;
  const alignedCount = directionalEvidence.filter((evidence) => evidence.aligned).length;
  const averageDirectionalScore = directionalEvidence.reduce((total, evidence) => total + evidence.score, 0) / directionalEvidence.length;
  const directionalScore = directionalMode === "single"
    ? currentDirectional.score
    : directionalMode === "majority" && alignedCount < Math.ceil(directionalEvidence.length / 2)
      ? Math.min(5, averageDirectionalScore)
      : directionalMode === "strict" && directionalEvidence.slice(-2).some((evidence) => !evidence.aligned)
        ? Math.min(5, averageDirectionalScore)
        : Math.round(averageDirectionalScore);
  const { aligned: candleAligned, bodyRatio, closeLocation, rangeAtrRatio } = currentDirectional;
  const emaSlopeLookback = Math.max(1, Math.round(config.emaSlopeLookback ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.emaSlopeLookback));
  const previousEma = previousCandles.at(-emaSlopeLookback)?.ema200;
  const trendAligned = currentCandle.ema200 !== null && (isBuy
    ? currentCandle.close > currentCandle.ema200
    : currentCandle.close < currentCandle.ema200);
  const emaDistanceRatio = currentCandle.ema200 !== null && atr !== null && atr > 0
    ? Math.abs(currentCandle.close - currentCandle.ema200) / atr
    : 0;
  const emaSlopeRatio = currentCandle.ema200 !== null && previousEma != null && atr !== null && atr > 0
    ? (isBuy ? currentCandle.ema200 - previousEma : previousEma - currentCandle.ema200) / atr
    : 0;
  const emaChanges = previousCandles.slice(-emaSlopeLookback).map((candle, index, values) => {
    const nextEma = index === values.length - 1 ? currentCandle.ema200 : values[index + 1]?.ema200;
    if (candle.ema200 == null || nextEma == null) return 0;
    return isBuy ? nextEma - candle.ema200 : candle.ema200 - nextEma;
  });
  const emaSlopeMethod = config.emaSlopeMethod ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.emaSlopeMethod;
  const effectiveEmaSlopeRatio = emaSlopeMethod === "average" && atr !== null && atr > 0 && emaChanges.length > 0
    ? emaChanges.reduce((total, value) => total + value, 0) / emaChanges.length / atr
    : emaSlopeMethod === "confirmation"
      ? (emaChanges.slice(-3).filter((value) => value > 0).length >= 2 ? Math.max(emaSlopeRatio, 0.01) : Math.min(emaSlopeRatio, 0))
      : emaSlopeRatio;
  const minimumEmaDistance = config.emaMinimumDistanceAtr ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.emaMinimumDistanceAtr;
  const trendScore = !trendAligned || emaDistanceRatio < minimumEmaDistance
    ? 0
    : emaDistanceRatio < 0.2
      ? 5
      : emaDistanceRatio > 2
        ? effectiveEmaSlopeRatio > 0 ? 12 : 8
        : effectiveEmaSlopeRatio >= 0.5
          ? 15
          : effectiveEmaSlopeRatio > 0
            ? 12
            : 8;
  const volumeLookback = Math.max(1, Math.round(config.volumeLookback ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.volumeLookback));
  const volumeBaselineCandles = previousCandles.slice(-volumeLookback);
  const volumeMethod = config.volumeMethod ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.volumeMethod;
  const averageVolume = getVolumeBaseline(volumeBaselineCandles.map((candle) => candle.volume), volumeMethod);
  const volumeRatio = averageVolume !== null && averageVolume > 0
    ? currentCandle.volume / averageVolume
    : 0;
  const volumeLowThreshold = config.volumeLowThreshold ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.volumeLowThreshold;
  const volumeStrongThreshold = config.volumeStrongThreshold ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.volumeStrongThreshold;
  const volumeImpulseThreshold = config.volumeImpulseThreshold ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.volumeImpulseThreshold;
  const volumeMode = config.volumeMode ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.volumeMode;
  const volumeDirectionConfirmed = directionalEvidence.slice(-3).filter((evidence) => evidence.aligned).length >= 2;
  const volumePositive = volumeMode === "independent" || (volumeMode === "confirmation" ? volumeDirectionConfirmed : candleAligned);
  const activityScore = averageVolume === null
    ? 0
    : volumeRatio < volumeLowThreshold
      ? 3
      : !volumePositive || directionalScore < 10
        ? volumeRatio >= volumeStrongThreshold ? 0 : 3
        : volumeRatio >= volumeImpulseThreshold && directionalScore === 20
          ? 15
          : volumeRatio >= volumeStrongThreshold
            ? 12
            : 7;
  const structureStrength = structure === undefined
    ? {
        score: structureAligned ? 30 : 0,
        passed: structureAligned,
        reason: structureAligned ? "Struktur terbaru searah posisi." : "Struktur terbaru belum mengonfirmasi arah posisi.",
      }
    : evaluateStructureStrength({ direction, currentCandle, atr, structure, config });

  const directionalWeight = Math.max(0, config.directionalWeight ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.directionalWeight);
  const emaWeight = Math.max(0, config.emaWeight ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.emaWeight);
  const volumeWeight = Math.max(0, config.volumeWeight ?? DEFAULT_CONTINUATION_STRENGTH_CONFIG.volumeWeight);
  const totalWeight = 50 + directionalWeight + emaWeight + volumeWeight;
  const scoreScale = totalWeight > 0 ? 100 / totalWeight : 1;
  const scaleComponent = (score: number, sourceMaximum: number, targetMaximum: number) => targetMaximum > 0
    ? score / sourceMaximum * targetMaximum * scoreScale
    : 0;
  const components: ContinuationStrengthComponent[] = [
    {
      key: "structure",
      label: "Structure",
      score: structureStrength.score,
      maximum: 30,
      passed: structureStrength.passed,
      reason: structureStrength.reason,
    },
    {
      key: "momentum",
      label: "Momentum ATR",
      score: momentumScore,
      maximum: 20,
      passed: momentumScore >= 10,
      reason: localMomentumReference == null
        ? `Belum tersedia ${momentumLookback} candle sebelumnya untuk mengukur momentum lokal.`
        : momentumAtrRatio <= 0
          ? `Momentum lokal berlawanan arah (${momentumAtrRatio.toFixed(2)} x ATR).`
          : `Momentum lokal searah ${momentumAtrRatio.toFixed(2)} x ATR selama ${momentumLookback} candle.`,
    },
    {
      key: "directional",
      label: "Directional Candle",
      score: scaleComponent(directionalScore, 20, directionalWeight),
      maximum: directionalWeight * scoreScale,
      passed: directionalScore >= 10,
      reason: `Body ${(bodyRatio * 100).toFixed(0)}%, posisi close ${(closeLocation * 100).toFixed(0)}%, range ${rangeAtrRatio.toFixed(2)} x ATR.`,
    },
    {
      key: "trend",
      label: "EMA200 Trend",
      score: scaleComponent(trendScore, 15, emaWeight),
      maximum: emaWeight * scoreScale,
      passed: trendScore >= 8,
      reason: currentCandle.ema200 === null
        ? "EMA200 belum tersedia."
        : `Jarak ${emaDistanceRatio.toFixed(2)} x ATR; slope ${emaSlopeLookback} candle ${emaSlopeRatio.toFixed(2)} x ATR.`,
    },
    {
      key: "activity",
      label: "Market Activity",
      score: scaleComponent(activityScore, 15, volumeWeight),
      maximum: volumeWeight * scoreScale,
      passed: activityScore >= 7,
      reason: averageVolume === null
        ? "Belum tersedia candle sebelumnya untuk baseline volume."
        : `Volume ${volumeRatio.toFixed(2)} x rata-rata ${volumeLookback} candle terbaru; arah candle ${candleAligned ? "searah" : "berlawanan"}.`,
    },
  ];

  components[0].score *= scoreScale;
  components[0].maximum *= scoreScale;
  components[1].score *= scoreScale;
  components[1].maximum *= scoreScale;
  const score = Math.round(components.reduce((total, component) => total + component.score, 0));
  const status = score >= 70 ? "STRONG" : score >= 40 ? "NEUTRAL" : "WEAK";
  const adverseStructureScore = structureStrength.passed ? 0 : structureStrength.score === 0 ? 30 : 15;
  const adverseMomentumScore = momentumAtrRatio <= -1 ? 20 : momentumAtrRatio <= -0.5 ? 15 : momentumAtrRatio < 0 ? 8 : 0;
  const adverseDirectionalScore = (!candleAligned && bodyRatio >= 0.5 ? 20 : !candleAligned ? 10 : 0) / 20 * directionalWeight;
  const adverseTrendScore = (!trendAligned ? 15 : effectiveEmaSlopeRatio < 0 ? 8 : 0) / 15 * emaWeight;
  const adverseActivityScore = (!candleAligned && volumeRatio >= volumeStrongThreshold ? 15 : !candleAligned && volumeRatio >= volumeLowThreshold ? 7 : 0) / 15 * volumeWeight;
  const reversalScore = Math.round((adverseStructureScore
    + adverseMomentumScore
    + adverseDirectionalScore
    + adverseTrendScore
    + adverseActivityScore) * scoreScale);
  const trend = classifyContinuationTrend([
    ...previousCandles.slice(-2).map((previousCandle) => {
      const directionalClose = isBuy
        ? previousCandle.close - entryPrice
        : entryPrice - previousCandle.close;
      return atr !== null && atr > 0
        ? Math.max(0, Math.min(100, 50 + directionalClose / atr * 10))
        : 50;
    }),
    score,
  ]);
  const classification = classifyContinuationState({
    continuationScore: score,
    reversalScore,
    trendStatus: trend.status,
  });

  return {
    score,
    status,
    reversalScore,
    state: classification.state,
    confidence: classification.confidence,
    components,
  };
}