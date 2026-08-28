import type { ReactNode } from "react";
import { Building2, Clock3, TrendingUp, BarChart3, CalendarDays, RefreshCw, Globe, Landmark, Monitor, ChevronDown } from "lucide-react";
import type { LucideIcon } from "lucide-react";
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
  dataMode: "recent" | "full" | "loading" | "window";
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
  blue: { border: "rgba(59, 130, 246, 0.45)", bg: "rgba(239, 246, 255, 0.95)", text: "#1e40af", shadow: "rgba(59, 130, 246, 0.15)" },
  purple: { border: "rgba(139, 92, 246, 0.45)", bg: "rgba(250, 245, 255, 0.95)", text: "#6b21a8", shadow: "rgba(139, 92, 246, 0.15)" },
  cyan: { border: "rgba(6, 182, 212, 0.45)", bg: "rgba(236, 254, 255, 0.95)", text: "#0e7490", shadow: "rgba(6, 182, 212, 0.15)" },
  amber: { border: "rgba(245, 158, 11, 0.45)", bg: "rgba(254, 252, 232, 0.95)", text: "#b45309", shadow: "rgba(245, 158, 11, 0.15)" },
  emerald: { border: "rgba(16, 185, 129, 0.45)", bg: "rgba(236, 253, 245, 0.95)", text: "#047857", shadow: "rgba(16, 185, 129, 0.15)" },
  ruby: { border: "rgba(239, 68, 68, 0.45)", bg: "rgba(254, 242, 242, 0.95)", text: "#b91c1c", shadow: "rgba(239, 68, 68, 0.15)" },
};

const ACCENT_CYCLE: AccentKey[] = ["purple", "cyan", "blue", "amber", "emerald", "ruby"];

const timeframes = ["M1", "M15", "M30", "H1", "H4", "D1"];

const timezoneOptions: Array<{ value: "utc" | "broker" | "local"; label: string; icon: LucideIcon }> = [
  { value: "utc", label: "UTC", icon: Globe },
  { value: "broker", label: "Broker", icon: Landmark },
  { value: "local", label: "Local", icon: Monitor },
];

function activeButtonStyle(accent: AccentKey) {
  const c = ACCENTS[accent];
  return {
    backgroundColor: c.bg,
    borderColor: c.border,
    color: c.text,
    fontWeight: 700,
    boxShadow: `0 1px 4px ${c.shadow}`,
  };
}

function activeItemStyle(accent: AccentKey) {
  const c = ACCENTS[accent];
  return {
    backgroundColor: c.bg,
    borderColor: c.border,
    color: c.text,
    fontWeight: 700,
    boxShadow: `0 1px 4px ${c.shadow}`,
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
    "inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-lg text-xs font-bold text-[var(--text-secondary)] transition-all hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] cursor-pointer whitespace-nowrap shadow-sm";

  const SectionLabel = ({ children }: { children: ReactNode }) => (
    <span className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)] mr-1">{children}</span>
  );

  const Divider = () => <div className="w-px h-5 bg-slate-400/25 mx-1" />;

  return (
    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 flex-wrap">
      {/* Left: timeframe + zoom */}
      <div className="flex flex-wrap items-center gap-2 justify-between md:justify-start md:flex-shrink-0">
        <SectionLabel>Timeframe</SectionLabel>
        <div className="inline-flex items-center p-0.5 sm:p-1 bg-sky-100/40 border border-sky-200/80 rounded-xl shadow-sm gap-1">
          {timeframes.map((tf) => (
            <button
              key={tf}
              onClick={() => onTimeframeChange(tf)}
              className={cn(
                "px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-lg text-xs font-bold transition-all duration-150 active:scale-95 cursor-pointer",
                tf === activeTimeframe
                  ? "bg-sky-600 text-white shadow-sm border border-sky-600"
                  : "text-slate-600 hover:text-slate-900 hover:bg-white/80"
              )}
            >
              {tf}
            </button>
          ))}
        </div>

        <Divider />

        <div className="inline-flex items-center gap-1 p-0.5 sm:p-1 bg-sky-100/40 border border-sky-200/80 rounded-xl shadow-sm">
          <button
            onClick={onZoomIn}
            title="Zoom in"
            className="flex items-center justify-center min-w-[28px] px-2 py-1 rounded-lg font-bold text-xs transition-all duration-150 active:scale-95 cursor-pointer text-slate-600 hover:text-slate-900 hover:bg-white/80"
          >
            +
          </button>
          <button
            onClick={onResetZoom}
            title="Reset zoom"
            className="flex items-center justify-center min-w-[28px] px-2 py-1 rounded-lg font-bold text-xs transition-all duration-150 active:scale-95 cursor-pointer text-slate-600 hover:text-slate-900 hover:bg-white/80"
          >
            ⟲
          </button>
          <button
            onClick={onZoomOut}
            title="Zoom out"
            className="flex items-center justify-center min-w-[28px] px-2 py-1 rounded-lg font-bold text-xs transition-all duration-150 active:scale-95 cursor-pointer text-slate-600 hover:text-slate-900 hover:bg-white/80"
          >
            −
          </button>
        </div>
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
            {selectedYear} <ChevronDown size={12} className="ml-0.5 opacity-80" />
          </button>
          <div className="hidden group-hover:block absolute top-[calc(100%+6px)] right-0 min-w-[180px] bg-white border border-slate-200/90 rounded-[10px] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.15)] z-50 before:content-[''] before:absolute before:-top-[6px] before:left-0 before:right-0 before:h-[6px]">
            {availableYears.map((year, idx) => {
              const accent = ACCENT_CYCLE[idx % ACCENT_CYCLE.length];
              const active = year === selectedYear;
              return (
                <div
                  key={year}
                  onClick={() => onYearChange(year)}
                  className={cn(
                    "px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                    active ? "font-semibold" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
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
            {selectedMonthLabel} <ChevronDown size={12} className="ml-0.5 opacity-80" />
          </button>
          <div className="hidden group-hover:block absolute top-[calc(100%+6px)] right-0 min-w-[180px] bg-white border border-slate-200/90 rounded-[10px] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.15)] z-50 before:content-[''] before:absolute before:-top-[6px] before:left-0 before:right-0 before:h-[6px]">
            {availableMonths.map((month, idx) => {
              const accent = ACCENT_CYCLE[idx % ACCENT_CYCLE.length];
              const active = month.value === selectedMonth;
              return (
                <div
                  key={month.value}
                  onClick={() => onMonthChange(month.value)}
                  className={cn(
                    "px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                    active ? "font-semibold" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
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
            <activeTimezoneLabel.icon size={13} aria-hidden="true" />
            <span>{activeTimezoneLabel.label}</span>
            <ChevronDown size={12} className="ml-0.5 opacity-80" />
          </button>
          <div className="hidden group-hover:block absolute top-[calc(100%+6px)] right-0 min-w-[180px] bg-white border border-slate-200/90 rounded-[10px] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.15)] z-50 before:content-[''] before:absolute before:-top-[6px] before:left-0 before:right-0 before:h-[6px]">
            {timezoneOptions.map((tz, idx) => {
              const accent = ACCENT_CYCLE[idx % ACCENT_CYCLE.length];
              const active = tz.value === chartTimezone.display_mode;
              return (
                <div
                  key={tz.value}
                  onClick={() => onTimezoneChange(tz.value)}
                  className={cn(
                    "flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                    active ? "font-semibold" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  )}
                  style={active ? activeItemStyle(accent) : undefined}
                  data-accent={accent}
                >
                  <tz.icon size={13} aria-hidden="true" />
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
          <div className="hidden group-hover:block absolute top-[calc(100%+6px)] right-0 min-w-[220px] bg-white border border-slate-200/90 rounded-[10px] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.15)] z-50 before:content-[''] before:absolute before:-top-[6px] before:left-0 before:right-0 before:h-[6px]">
            {/* Toggle items */}
            <div
              onClick={onToggleStructure}
              className={cn(
                "flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                showStructure ? "font-semibold" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              )}
              style={showStructure ? activeItemStyle("purple") : undefined}
              data-accent="purple"
            >
              <Building2 size={13} aria-hidden="true" />
              <span>Structure</span>
              {structureLines?.total_points != null && (
                <span className={cn("text-[10px] font-semibold ml-auto", showStructure ? "text-purple-600" : "text-slate-400")}>
                  ({structureLines.total_points})
                </span>
              )}
            </div>

            <div
              onClick={onToggleSessions}
              className={cn(
                "flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                showSessions ? "font-semibold" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              )}
              style={showSessions ? activeItemStyle("cyan") : undefined}
              data-accent="cyan"
            >
              <Clock3 size={13} aria-hidden="true" />
              <span>Sessions</span>
              {sessionZonesData?.total_zones != null && (
                <span className={cn("text-[10px] font-semibold ml-auto", showSessions ? "text-cyan-700" : "text-slate-400")}>
                  ({sessionZonesData.total_zones})
                </span>
              )}
            </div>

            <div
              onClick={onToggleEMA200}
              className={cn(
                "flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                showEMA200 ? "font-semibold" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              )}
              style={showEMA200 ? activeItemStyle("amber") : undefined}
              data-accent="amber"
            >
              <TrendingUp size={13} aria-hidden="true" />
              <span>EMA 200</span>
            </div>

            <div
              onClick={onToggleTrades}
              className={cn(
                "flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs transition-all cursor-pointer",
                showTrades ? "font-semibold" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              )}
              style={showTrades ? activeItemStyle("blue") : undefined}
              data-accent="blue"
            >
              <BarChart3 size={13} aria-hidden="true" />
              <span>Trades</span>
              {backtestTradesData?.total_trades != null && (
                <span className={cn("text-[10px] font-semibold ml-auto", showTrades ? "text-blue-600" : "text-slate-400")}>
                  ({backtestTradesData.total_trades})
                </span>
              )}
            </div>

            <div className="h-px bg-slate-200 my-1.5" />

            {/* Refresh data */}
            <div
              onClick={onRefresh}
              className="flex items-center gap-2 px-2.5 py-2 rounded-md border border-transparent text-xs text-slate-600 transition-all cursor-pointer hover:bg-slate-100 hover:text-slate-900"
              data-accent="emerald"
            >
              <RefreshCw size={13} aria-hidden="true" />
              <span>Refresh data</span>
            </div>

            {/* Load full history */}
            <div
              onClick={onLoadFullHistory}
              className={cn(
                "flex items-center gap-2 px-2.5 py-2 rounded-md border text-xs transition-all cursor-pointer",
                isFullHistoryLoaded
                  ? "text-cyan-700 border-cyan-300 bg-cyan-50 font-semibold shadow-sm"
                  : "border-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              )}
              data-accent="ruby"
            >
              <CalendarDays size={13} aria-hidden="true" />
              <span>Load full history</span>
              {isFullHistoryLoaded && (
                <span className="ml-auto text-[10px] font-semibold text-cyan-600 uppercase tracking-wider">Aktif</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
