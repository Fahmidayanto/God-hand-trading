export type ExitTargetObserverStatus =
  | "HOLD"
  | "PROTECT"
  | "EXTEND"
  | "EXIT_ALERT"
  | "FORCE_EXIT_ALERT";

export interface ExitTargetObserverInput {
  continuationStatus: "STRONG" | "NEUTRAL" | "WEAK";
  continuationScore: number;
  floatingNetProfit: number;
  maxFavorablePoints: number;
  maxAdversePoints: number;
  protectEnabled: boolean;
  protectTriggerPoints: number;
  isBreakevenActive: boolean;
  isTargetMaxed: boolean;
  expansionCount: number;
  holdSeconds: number;
  maxHoldSeconds: number;
  structureAligned: boolean;
}

export interface ExitTargetObserverResult {
  status: ExitTargetObserverStatus;
  title: string;
  reason: string;
  tone: "neutral" | "positive" | "warning" | "critical";
  observerOnly: true;
}

export function evaluateExitTargetObserver(
  input: ExitTargetObserverInput,
): ExitTargetObserverResult {
  if (input.maxHoldSeconds > 0 && input.holdSeconds >= input.maxHoldSeconds) {
    return {
      status: "FORCE_EXIT_ALERT",
      title: "Maximum Hold Tercapai",
      reason: "Durasi posisi telah mencapai batas hold maksimum.",
      tone: "critical",
      observerOnly: true,
    };
  }

  if (input.continuationStatus === "WEAK" && !input.structureAligned) {
    return {
      status: "EXIT_ALERT",
      title: "Continuation Melemah",
      reason: "Otak 2 lemah dan struktur terbaru tidak lagi searah posisi.",
      tone: "critical",
      observerOnly: true,
    };
  }

  if (
    input.protectEnabled &&
    input.maxFavorablePoints >= input.protectTriggerPoints &&
    !input.isBreakevenActive
  ) {
    return {
      status: "PROTECT",
      title: "Lindungi Profit",
      reason: "Profit dan pergerakan favorable sudah bermakna, tetapi breakeven belum aktif.",
      tone: "warning",
      observerOnly: true,
    };
  }

  if (
    input.continuationStatus === "STRONG" &&
    input.structureAligned &&
    input.floatingNetProfit > 0 &&
    !input.isTargetMaxed
  ) {
    return {
      status: "EXTEND",
      title: "Continuation Kuat",
      reason: "Momentum dan struktur masih mendukung peluang perluasan target.",
      tone: "positive",
      observerOnly: true,
    };
  }

  return {
    status: "HOLD",
    title: "Pertahankan Posisi",
    reason: "Belum ada bukti yang cukup untuk proteksi, ekstensi, atau exit alert.",
    tone: "neutral",
    observerOnly: true,
  };
}