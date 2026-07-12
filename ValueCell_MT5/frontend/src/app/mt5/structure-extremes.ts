export interface StructureEventLike {
  type: string;
  direction: string;
  price: number;
  time: number;
  timeframe: string;
}

/**
 * Keep one meaningful opposite-swing extreme per active CHoCH setup.
 *
 * Bearish: after CHoCH + LL, only highest HH/LH remains visible.
 * Bullish: after CHoCH + HH, only lowest LL/HL remains visible.
 * A BOS closes the cycle; a new CHoCH starts a fresh one.
 */
export function selectSetupExtremeEvents<T extends StructureEventLike>(events: T[]): Set<T> {
  type Cycle = {
    direction: "BULLISH" | "BEARISH";
    setupFormed: boolean;
    extreme?: T;
  };

  const visible = new Set<T>();
  const cycles = new Map<string, Cycle>();
  const chronological = [...events].sort((a, b) => a.time - b.time);

  for (const event of chronological) {
    const type = event.type?.toUpperCase() ?? "";
    const direction = event.direction?.toUpperCase() ?? "";
    const timeframe = event.timeframe || "M15";

    if (type === "CHOCH") {
      visible.add(event);
      if (direction === "BULLISH" || direction === "BEARISH") {
        cycles.set(timeframe, { direction, setupFormed: false });
      } else {
        cycles.delete(timeframe);
      }
      continue;
    }

    if (type === "BOS") {
      visible.add(event);
      cycles.delete(timeframe);
      continue;
    }

    const cycle = cycles.get(timeframe);
    const isHigh = type === "HH" || type === "LH";
    const isLow = type === "LL" || type === "HL";
    if (!cycle || (!isHigh && !isLow)) {
      visible.add(event);
      continue;
    }

    const isSetupSwing = cycle.direction === "BEARISH" ? isLow : isHigh;
    const isCandidateExtreme = cycle.direction === "BEARISH" ? isHigh : isLow;

    if (isSetupSwing) {
      cycle.setupFormed = true;
      visible.add(event);
      continue;
    }

    if (!cycle.setupFormed || !isCandidateExtreme) {
      visible.add(event);
      continue;
    }

    const replacesExtreme = !cycle.extreme || (
      cycle.direction === "BEARISH"
        ? event.price > cycle.extreme.price
        : event.price < cycle.extreme.price
    );

    if (replacesExtreme) {
      if (cycle.extreme) visible.delete(cycle.extreme);
      cycle.extreme = event;
      visible.add(event);
    }
  }

  return visible;
}
