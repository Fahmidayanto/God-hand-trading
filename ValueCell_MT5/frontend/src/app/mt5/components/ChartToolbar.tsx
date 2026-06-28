import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface ChartToolbarProps {
  activeTimeframe: string;
  onTimeframeChange: (tf: string) => void;

  selectedYear: string;
  onYearChange: (year: string) => void;

  selectedMonth: string;
  onMonthChange: (month: string) => void;

  availableYears: string[];
  availableMonths: Array<{ value: string; label: string }>;

  chartTimezone: { display_mode: string; broker_offset_hours: number };
  onTimezoneChange: (mode: "utc" | "broker" | "local") => void;

  showStructure: boolean;
  onToggleStructure: () => void;

  showSessions: boolean;
  onToggleSessions: () => void;

  showEMA200: boolean;
  onToggleEMA200: () => void;

  showTrades: boolean;
  onToggleTrades: () => void;

  structureLines?: { total_points?: number } | null;
  sessionZonesData?: { total_zones?: number } | null;
  backtestTradesData?: { total_trades?: number } | null;

  isFullHistoryLoaded: boolean;
  dataMode: "recent" | "full" | "loading";
  candlesCount: number;

  onRefresh: () => void;
  onLoadFullHistory: () => void;

  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetZoom: () => void;

  isJumping?: boolean;

  title?: ReactNode;
}

type AccentKey = "blue" | "purple" | "cyan" | "amber" | "emerald" | "ruby";

const ACCENTS: Record<AccentKey, { border: string; bg: string; text: string; shadow: string }> = {
  blue: { border: "var(--neon-blue)", bg: "rgba(59,130,246,0.2)", text: "#93c5fd", shadow: "rgba(59,130,246,0.25)" },
  purple: { border: "var(--neon-purple)", bg: "rgba(139,92,246,0.2)", text: "#c4b5fd", shadow: "rgba(139,92,246,0.25)" },
  cyan: { border: "var(--neon-cyan)", bg: "rgba(6,182,212,0.15)", text: "#67e8f9", shadow: "rgba(6,182,212,0.2)" },
  amber: { border: "var(--neon-amber)", bg: "rgba(251,191,36,0.15)", text: "#fcd34d", shadow: "rgba(251,191,36,0.2)" },
  emerald: { border: "var(--neon-emerald)", bg: "rgba(16,185,129,0.15)", text: "#6ee7b7", shadow: "rgba(16,185,129,0.2)" },
  ruby: { border: "var(--neon-ruby)", bg: "rgba(239,68,68,0.15)", text: "#fca5a5", shadow: "rgba(239,68,68,0.2)" },
};

const ACCENT_CYCLE: AccentKey[] = ["purple", "cyan", "blue", "amber", "emerald", "ruby"];

const timeframes = ["M15", "M30", "H1", "H4", "D1"];

const timezoneOptions: Array<{ value: "utc" | "broker" | "local"; label: string; icon: string }> = [
  { value: "utc", label: "UTC", icon: "🌐" },
  { value: "broker", label: "Broker", icon: "🏦" },
  { value: "local", label: "Local", icon: "🖥️" },
];

function activeButtonStyle(accent: AccentKey) {
  const c = ACCENTS[accent];
  return {
    backgroundColor: c.bg,
    borderColor: c.border,
    color: "#fff",
    boxShadow: `0 0 12px ${c.shadow}`,
  };
}

function activeItemStyle(accent: AccentKey) {
  const c = ACCENTS[accent];
  return {
    backgroundColor: c.bg,
    borderColor: c.border,
    color: c.text,
    boxShadow: `0 0 12px ${c.shadow}`,
  };
}

export default function ChartToolbar({
  activeTimeframe,
  onTimeframeChange,
  selectedYear,
  onYearChange,
  selectedMonth,
  onMonthChange,
  availableYears,
  availableMonths,
  chartTimezone,
  onTimezoneChange,
  showStructure,
  onToggleStructure,
  showSessions,
  onToggleSessions,
  showEMA200,
  onToggleEMA200,
  showTrades,
  onToggleTrades,
  structureLines,
  sessionZonesData,
  backtestTradesData,
  isFullHistoryLoaded,
  dataMode,
  candlesCount,
  onRefresh,
  onLoadFullHistory,
  onZoomIn,
  onZoomOut,
  onResetZoom,
  isJumping = false,
  title,
}: ChartToolbarProps) {
  const selectedMonthLabel = availableMonths.find((m) => m.value === selectedMonth)?.label ?? selectedMonth;
  const activeTimezoneLabel = timezoneOptions.find((t) => t.value === chartTimezone.display_mode) ?? timezoneOptions[0];

  const baseBtn =
    "inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-lg text-xs font-medium text-[var(--text-secondary)] transition-all hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] cursor-pointer whitespace-nowrap";

  const SectionLabel = ({ children }: { children: ReactNode }) => (
    <span className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)] mr-1">{children}</span>
  );

  const Divider = () => <div className="w-px h-5 bg-slate-400/25 mx-1" />;

  return (
    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 flex-wrap">
      {/* Left: timeframe + zoom */}
      <div className="flex flex-wrap items-center gap-2 justify-between md:justify-start md:flex-shrink-0">
        <SectionLabel>Timeframe</SectionLabel>
        <div className="inline-flex bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-lg overflow-hidden">
          {timeframes.map((tf) => (
            <button
              key={tf}
              onClick={() => onTimeframeChange(tf)}
              className={cn(
                "bg-transparent border-0 border-r border-[var(--glass-border)] last:border-r-0 px-3 py-1.5 text-xs font-medium transition-all hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]",
                tf === activeTimeframe
                  ? "!bg-[var(--neon-blue)] !text-white"
                  : "text-[var(--text-secondary)]"
              )}
            >
              {tf}
            </button>
          ))}
        </div>

        <Divider />

        <button onClick={onZoomIn} className={baseBtn} title="Zoom in">
          +
        </button>
        <button onClick={onResetZoom} className={baseBtn} title="Reset zoom">
          ⟲
        </button>
        <button onClick={onZoomOut} className={baseBtn} title="Zoom out">
          −
        </button>
      </div>

      {/* Center: chart title */}
      {title && (
        <div className="flex items-center justify-center flex-1 min-w-0 order-first md:order-none">
          {title}
        </div>
      )}

      {/* Right: data actions */}
      <div className="flex flex-wrap items-center gap-2 justify-between md:justify-start md:flex-shrink-0">
        <SectionLabel>Data</SectionLabel>

        {/* Year dropdown */}
        <div className={cn("relative group", isJumping && "pointer-events-none opacity-60")}>
          <button
            className={baseBtn}
            style={activeButtonStyle("blue")}
            data-accent="blue"
          >
            {selectedYear} <span className="ml-0.5">▾</span>
          </button>
          <div className="hidden group-hover:block absolute top-[calc(100%+6px)] right-0 min-w-[180px] bg-[var(--bg-surface)] border border-[var(--glass-border)] rounded-[10px] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.5)] z-50">
            {availableYears.map((year, idx) => {
              const accent = ACCENT_CYCLE[idx % ACCENT_CYCLE.length];
              const active = year === selectedYear;
              return (
                <div
                  key={year}
                  onClick={() => onYearChange(year)}
                  className={cn(
                    "px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                    active ? "text-white" : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                  )}
                  style={active ? activeItemStyle(accent) : undefined}
                  data-accent={accent}
                >
                  {year}
                </div>
              );
            })}
          </div>
        </div>

        {/* Month dropdown */}
        <div className={cn("relative group", isJumping && "pointer-events-none opacity-60")}>
          <button
            className={baseBtn}
            style={activeButtonStyle("purple")}
            data-accent="purple"
          >
            {selectedMonthLabel} <span className="ml-0.5">▾</span>
          </button>
          <div className="hidden group-hover:block absolute top-[calc(100%+6px)] right-0 min-w-[180px] bg-[var(--bg-surface)] border border-[var(--glass-border)] rounded-[10px] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.5)] z-50">
            {availableMonths.map((month, idx) => {
              const accent = ACCENT_CYCLE[idx % ACCENT_CYCLE.length];
              const active = month.value === selectedMonth;
              return (
                <div
                  key={month.value}
                  onClick={() => onMonthChange(month.value)}
                  className={cn(
                    "px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                    active ? "text-white" : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                  )}
                  style={active ? activeItemStyle(accent) : undefined}
                  data-accent={accent}
                >
                  {month.label}
                </div>
              );
            })}
          </div>
        </div>

        {/* Timezone dropdown */}
        <div className="relative group">
          <button
            className={baseBtn}
            style={activeButtonStyle("blue")}
            data-accent="blue"
          >
            <span>{activeTimezoneLabel.icon}</span>
            <span>{activeTimezoneLabel.label}</span>
            <span className="ml-0.5">▾</span>
          </button>
          <div className="hidden group-hover:block absolute top-[calc(100%+6px)] right-0 min-w-[180px] bg-[var(--bg-surface)] border border-[var(--glass-border)] rounded-[10px] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.5)] z-50">
            {timezoneOptions.map((tz, idx) => {
              const accent = ACCENT_CYCLE[idx % ACCENT_CYCLE.length];
              const active = tz.value === chartTimezone.display_mode;
              return (
                <div
                  key={tz.value}
                  onClick={() => onTimezoneChange(tz.value)}
                  className={cn(
                    "flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                    active ? "text-white" : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                  )}
                  style={active ? activeItemStyle(accent) : undefined}
                  data-accent={accent}
                >
                  <span>{tz.icon}</span>
                  <span>{tz.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        <Divider />

        {/* Actions dropdown */}
        <div className="relative group">
          <button
            className={baseBtn}
            style={activeButtonStyle("cyan")}
            data-accent="cyan"
          >
            Actions <span className="ml-0.5">▾</span>
          </button>
          <div className="hidden group-hover:block absolute top-[calc(100%+6px)] right-0 min-w-[220px] bg-[var(--bg-surface)] border border-[var(--glass-border)] rounded-[10px] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.5)] z-50">
            {/* Toggle items */}
            <div
              onClick={onToggleStructure}
              className={cn(
                "flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                showStructure ? "text-white" : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
              )}
              style={showStructure ? activeItemStyle("purple") : undefined}
              data-accent="purple"
            >
              <span>🏗️</span>
              <span>Structure</span>
              {structureLines?.total_points != null && (
                <span className={cn("text-[10px] font-semibold ml-auto", showStructure ? "text-white/70" : "text-[var(--text-tertiary)]")}>
                  ({structureLines.total_points})
                </span>
              )}
            </div>

            <div
              onClick={onToggleSessions}
              className={cn(
                "flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                showSessions ? "text-white" : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
              )}
              style={showSessions ? activeItemStyle("cyan") : undefined}
              data-accent="cyan"
            >
              <span>🕒</span>
              <span>Sessions</span>
              {sessionZonesData?.total_zones != null && (
                <span className={cn("text-[10px] font-semibold ml-auto", showSessions ? "text-white/70" : "text-[var(--text-tertiary)]")}>
                  ({sessionZonesData.total_zones})
                </span>
              )}
            </div>

            <div
              onClick={onToggleEMA200}
              className={cn(
                "flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                showEMA200 ? "text-white" : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
              )}
              style={showEMA200 ? activeItemStyle("amber") : undefined}
              data-accent="amber"
            >
              <span>📈</span>
              <span>EMA 200</span>
            </div>

            <div
              onClick={onToggleTrades}
              className={cn(
                "flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                showTrades ? "text-white" : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
              )}
              style={showTrades ? activeItemStyle("blue") : undefined}
              data-accent="blue"
            >
              <span>📊</span>
              <span>Trades</span>
              {backtestTradesData?.total_trades != null && (
                <span className={cn("text-[10px] font-semibold ml-auto", showTrades ? "text-white/70" : "text-[var(--text-tertiary)]")}>
                  ({backtestTradesData.total_trades})
                </span>
              )}
            </div>

            <div className="h-px bg-slate-400/20 my-1.5" />

            {/* Refresh data */}
            <div
              onClick={onRefresh}
              className="flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs text-[var(--text-secondary)] transition-all cursor-pointer hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
              data-accent="emerald"
            >
              <span>🔄</span>
              <span>Refresh data</span>
            </div>

            {/* Load full history */}
            <div
              onClick={onLoadFullHistory}
              className="flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs text-[var(--text-secondary)] transition-all cursor-pointer hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
              data-accent="ruby"
            >
              <span>📅</span>
              <span>Load full history</span>
            </div>
          </div>
        </div>

        {/* Status chip */}
        {dataMode === "loading" && (
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border animate-pulse" style={{ color: "var(--neon-amber)", borderColor: "rgba(251,191,36,0.3)", backgroundColor: "rgba(251,191,36,0.1)" }}>
            <span>⏳</span>
            <span>Loading history…</span>
          </div>
        )}

        {dataMode !== "loading" && isFullHistoryLoaded && (
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border" style={{ color: "var(--neon-emerald)", borderColor: "rgba(16,185,129,0.3)", backgroundColor: "rgba(16,185,129,0.1)" }}>
            <span>✅</span>
            <span>Full History Cached</span>
            {candlesCount > 0 && (
              <span className="text-[10px] opacity-70">({candlesCount.toLocaleString()} candles)</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
