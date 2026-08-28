import { useMemo } from "react";
import {
  Wallet, BarChart3, TrendingUp, TrendingDown, MoveRight, Zap, Target, MessageSquare,
  Bot, Building2, Brain, Shield, Newspaper, CheckCircle2, PauseCircle, MapPin,
  RefreshCw, XCircle, Info, FileText, ClipboardList,
} from "lucide-react";
import Particles from "@tsparticles/react";
import { useDashboardStats, usePerformanceStats, useSystemStatus } from "@/api/dashboard";
import { usePositions, useTradingSignal } from "@/api/trading";
import { useAgentConsensus, useMarketStructure } from "@/api/mt5_agents";
import { useActivityLogs, EVENT_TYPE_ICONS, SEVERITY_CLASSES } from "@/api/activity-logs";
import { cn } from "@/lib/utils";
import MT5Footer from "./components/MT5Footer";

const StatusDot = ({ color }: { color: string }) => (
  <span
    aria-hidden="true"
    style={{ display: "inline-block", width: "8px", height: "8px", borderRadius: "50%", background: color, marginRight: "6px" }}
  />
);

export default function MT5Dashboard() {
  const { data: stats } = useDashboardStats();
  const { data: performanceStats } = usePerformanceStats(180);
  const { data: systemStatus } = useSystemStatus();
  const { data: positions } = usePositions();
  const { data: signal, isLoading: signalLoading } = useTradingSignal();
  const { data: consensus, isLoading: consensusLoading } = useAgentConsensus();
  const { data: marketStructure, isLoading: structureLoading } = useMarketStructure();
  const { data: activityLogs, isLoading: activityLogsLoading, isError: activityLogsError } = useActivityLogs({ limit: 10 });

  const particlesOptions = useMemo(
    () => ({
      background: {
        color: {
          value: "transparent",
        },
      },
      fpsLimit: 60,
      particles: {
        color: {
          value: "#3b82f6",
        },
        links: {
          color: "#3b82f6",
          distance: 150,
          enable: true,
          opacity: 0.2,
          width: 1,
        },
        move: {
          enable: true,
          speed: 1,
          random: true,
          outModes: "out",
        },
        number: {
          density: {
            enable: true,
            area: 800,
          },
          value: 80,
        },
        opacity: {
          value: 0.3,
          random: true,
        },
        shape: {
          type: "circle",
        },
        size: {
          value: { min: 1, max: 3 },
          random: true,
        },
      },
      interactivity: {
        detectsOn: "canvas",
        events: {
          onHover: {
            enable: true,
            mode: "grab",
          },
          onClick: {
            enable: true,
            mode: "push",
          },
        },
        modes: {
          grab: {
            distance: 140,
            links: {
              opacity: 0.5,
            },
          },
          push: {
            quantity: 4,
          },
        },
      },
      detectRetina: true,
    } as any),
    []
  );

  return (
    <div 
      style={{ 
        background: "var(--bg-deepspace)",
        minHeight: "100vh",
        width: "100%",
        position: "relative",
        overflowX: "auto",
        overflowY: "auto"
      }}
    >
      {/* Particles Background - fixed position */}
      <div id="particles-js">
        <Particles
          id="tsparticles-dashboard"
          options={particlesOptions}
        />
      </div>

      {/* Animated Background Gradient - fixed position */}
      <div className="bg-animated" />

      {/* Main Content Container */}
      <div 
        className="relative z-10" 
        style={{ 
          width: "100%",
          paddingLeft: "var(--sidebar-offset, 250px)",
          transition: "padding-left 0.3s cubic-bezier(0.22, 1, 0.36, 1)",
          minHeight: "100vh"
        }}
      >
        <div className="w-full px-4 sm:px-6 md:px-8 xl:px-12 py-6 max-w-[1920px] mx-auto">
          {/* Status Bar */}
          <div className="status-bar mb-6">
            <div className="status-live">
              <div className="pulse-dot"></div>
              <span>{systemStatus?.mt5_connected ? 'LIVE' : 'OFFLINE'}</span>
            </div>
            <span>•</span>
            <span>Uptime: <strong>{systemStatus?.uptime_seconds ? `${Math.floor(systemStatus.uptime_seconds / 3600)}h ${Math.floor((systemStatus.uptime_seconds % 3600) / 60)}m` : '0h 0m'}</strong></span>
            <span>•</span>
            <span>Last Update: <strong>{new Date().toLocaleTimeString()}</strong></span>
            <span>•</span>
            <span>Account: <strong>{systemStatus?.account_number ?? 'N/A'}</strong></span>
          </div>

          {/* Institutional Split (Preset 04): Left Side Telemetry (xl:col-span-4) + Right Main Canvas (xl:col-span-8) */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 mb-6">

            {/* ======================================================== */}
            {/* LEFT SIDE TELEMETRY COLUMN (xl:col-span-4 / 33%)        */}
            {/* ======================================================== */}
            <div className="xl:col-span-4 flex flex-col gap-6">

              {/* 4 Cards (2x2 Grid) - Theme 09 Sapphire Platinum Sovereign */}
              <section className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {/* Balance Card */}
                <div className="relative flex flex-col justify-between gap-2 p-4 rounded-[20px] border border-blue-200/80 bg-gradient-to-br from-white via-sky-50/40 to-blue-50/60 shadow-[0_10px_25px_-10px_rgba(37,99,235,0.08)] hover:shadow-[0_20px_45px_-15px_rgba(37,99,235,0.18)] hover:-translate-y-0.5 transition-all duration-200">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Account Balance</span>
                    <span className="font-mono text-[9px] font-bold px-1.5 py-0.5 rounded bg-white border border-blue-200/80 text-slate-700 shadow-xs uppercase flex items-center gap-1">
                      <Wallet size={10} className="text-blue-500" />
                      <span>USD</span>
                    </span>
                  </div>
                  <div className="font-sans text-xl sm:text-2xl font-black tracking-tight text-slate-900">
                    ${(stats?.balance ?? 1000).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div className="text-[11px] text-slate-500 font-medium flex items-center gap-1 truncate">
                    <span>Equity:</span>
                    <strong className="text-emerald-600 font-bold">${(stats?.equity ?? stats?.balance ?? 1000).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
                  </div>
                </div>

                {/* Open Positions Card */}
                <div className="relative flex flex-col justify-between gap-2 p-4 rounded-[20px] border border-blue-200/80 bg-gradient-to-br from-white via-sky-50/40 to-blue-50/60 shadow-[0_10px_25px_-10px_rgba(37,99,235,0.08)] hover:shadow-[0_20px_45px_-15px_rgba(37,99,235,0.18)] hover:-translate-y-0.5 transition-all duration-200">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Open Positions</span>
                    <span className="font-mono text-[9px] font-bold px-1.5 py-0.5 rounded bg-white border border-blue-200/80 text-slate-700 shadow-xs uppercase flex items-center gap-1">
                      <BarChart3 size={10} className="text-sky-500" />
                      <span>LIVE</span>
                    </span>
                  </div>
                  <div className="font-sans text-xl sm:text-2xl font-black tracking-tight text-slate-900">
                    {positions?.length ?? 0}
                  </div>
                  <div className="text-[11px] text-slate-500 font-medium truncate">
                    {positions && positions.length > 0 ? `${positions.length} active trade${positions.length > 1 ? "s" : ""}` : "Margin 0%"}
                  </div>
                </div>

                {/* Today P&L Card */}
                <div className="relative flex flex-col justify-between gap-2 p-4 rounded-[20px] border border-blue-200/80 bg-gradient-to-br from-white via-sky-50/40 to-blue-50/60 shadow-[0_10px_25px_-10px_rgba(37,99,235,0.08)] hover:shadow-[0_20px_45px_-15px_rgba(37,99,235,0.18)] hover:-translate-y-0.5 transition-all duration-200">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Today P&L</span>
                    <span className="font-mono text-[9px] font-bold px-1.5 py-0.5 rounded bg-white border border-blue-200/80 text-slate-700 shadow-xs uppercase flex items-center gap-1">
                      <TrendingUp size={10} className={(stats?.profit ?? 0) >= 0 ? "text-emerald-500" : "text-rose-500"} />
                      <span>REALTIME</span>
                    </span>
                  </div>
                  <div className={cn("font-sans text-xl sm:text-2xl font-black tracking-tight", (stats?.profit ?? 0) >= 0 ? "text-slate-900" : "text-rose-600")}>
                    {(stats?.profit ?? 0) >= 0 ? `+$${(stats?.profit ?? 0).toFixed(2)}` : `-$${Math.abs(stats?.profit ?? 0).toFixed(2)}`}
                  </div>
                  <div className="text-[11px] text-slate-500 font-medium truncate">
                    <span className={(stats?.profit ?? 0) >= 0 ? "text-emerald-600 font-bold" : "text-rose-600 font-bold"}>
                      {(stats?.profit ?? 0) >= 0 ? "+" : ""}{((stats?.profit ?? 0) / (stats?.balance || 1000) * 100).toFixed(2)}%
                    </span>
                  </div>
                </div>

                {/* System Health Card */}
                <div className="relative flex flex-col justify-between gap-2 p-4 rounded-[20px] border border-blue-200/80 bg-gradient-to-br from-white via-sky-50/40 to-blue-50/60 shadow-[0_10px_25px_-10px_rgba(37,99,235,0.08)] hover:shadow-[0_20px_45px_-15px_rgba(37,99,235,0.18)] hover:-translate-y-0.5 transition-all duration-200">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">System Health</span>
                    <span className="font-mono text-[9px] font-bold px-1.5 py-0.5 rounded bg-white border border-blue-200/80 text-slate-700 shadow-xs uppercase flex items-center gap-1">
                      <Zap size={10} className={systemStatus?.mt5_connected ? "text-emerald-500" : "text-rose-500"} />
                      <span>{systemStatus?.mt5_connected ? "CONNECTED" : "OFFLINE"}</span>
                    </span>
                  </div>
                  <div className="font-sans text-xl sm:text-2xl font-black tracking-tight text-slate-900">
                    {systemStatus?.system_health_percent.toFixed(0) ?? "100"}%
                  </div>
                  <div className="text-[11px] text-slate-500 font-medium truncate">
                    <span className={systemStatus?.mt5_connected ? "text-emerald-600 font-bold" : "text-rose-600 font-bold"}>
                      {systemStatus?.mt5_connected ? "Operational" : "Disconnected"}
                    </span>
                  </div>
                </div>
              </section>

              {/* Current Signal Card */}
              <div className="glass-card p-5 sm:p-6 flex flex-col justify-between relative overflow-hidden">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
                      <Target size={18} aria-hidden="true" />
                    </div>
                    <div>
                      <h2 className="text-base font-bold text-slate-900 leading-tight">Current Market Signal</h2>
                      <p className="text-[11px] text-slate-500 font-medium">XAUUSD &bull; Timeframe M15</p>
                    </div>
                  </div>
                  <span className={cn(
                    "px-3 py-1 rounded-xl font-bold text-xs font-mono border uppercase",
                    (signal?.signal || 'HOLD') === 'BUY' ? "bg-emerald-50 text-emerald-800 border-emerald-300" :
                    (signal?.signal || 'HOLD') === 'SELL' ? "bg-rose-50 text-rose-800 border-rose-300" :
                    "bg-amber-50 text-amber-800 border-amber-300"
                  )}>
                    {signal?.signal || 'HOLD'}
                  </span>
                </div>
                
                {signalLoading ? (
                  <p className="text-xs text-slate-500 py-4">Loading signal...</p>
                ) : signal ? (
                  <>
                    {/* Signal Key Metrics 3-Grid */}
                    <div className="grid grid-cols-3 gap-2 p-3 rounded-2xl bg-blue-50/60 border border-blue-200/70 mb-4 text-center">
                      <div>
                        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Signal Type</span>
                        <div className="font-bold text-sm text-slate-900 mt-0.5">{signal.signal}</div>
                      </div>
                      <div className="border-x border-blue-200/80 px-1">
                        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Entry Price</span>
                        <div className="font-mono font-bold text-sm text-blue-700 mt-0.5">
                          {signal.entry_price > 0 ? signal.entry_price.toFixed(2) : 'N/A'}
                        </div>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Confidence</span>
                        <div className="font-bold text-sm text-emerald-600 mt-0.5">
                          {((signal.confidence ?? 0) * 100).toFixed(0)}%
                        </div>
                      </div>
                    </div>

                    {/* Confidence Barometer */}
                    <div className="space-y-1.5 mb-4">
                      <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
                        <span>Signal Confidence Barometer</span>
                        <span className="text-blue-600 font-mono font-bold">{((signal.confidence ?? 0) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="w-full bg-slate-200/80 rounded-full h-2 overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 rounded-full transition-all duration-500" style={{ width: `${(signal.confidence ?? 0) * 100}%` }}></div>
                      </div>
                    </div>

                    {/* SL & TP Target Card */}
                    <div className="p-2.5 rounded-xl bg-slate-100/90 border border-slate-200 text-[11px] text-slate-600 flex items-center justify-between">
                      <span className="flex items-center gap-1.5 truncate">
                        <Shield size={13} className="text-blue-500 shrink-0" />
                        <span>{signal.stop_loss > 0 && signal.take_profit > 0 ? `SL: ${signal.stop_loss.toFixed(2)} | TP: ${signal.take_profit.toFixed(2)}` : 'Waiting for structure confirmation'}</span>
                      </span>
                      {signal.stop_loss > 0 && signal.take_profit > 0 && (
                        <span className="text-emerald-700 font-bold text-[10px] shrink-0">RR 1:3.1</span>
                      )}
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-slate-500 py-4">No signal data available</p>
                )}
              </div>

              {/* Multi-Agent Consensus Card */}
              <div className="glass-card p-5 sm:p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center font-bold">
                      <Bot size={18} aria-hidden="true" />
                    </div>
                    <div>
                      <h2 className="text-base font-bold text-slate-900 leading-tight">Multi-Agent Consensus</h2>
                      <p className="text-[11px] text-slate-500 font-medium">4 AI Sub-Agents Realtime Voting</p>
                    </div>
                  </div>
                  <span className="px-2.5 py-0.5 rounded-lg bg-purple-50 text-purple-700 border border-purple-200 font-mono text-[11px] font-bold">
                    4/4 ONLINE
                  </span>
                </div>
                
                {consensusLoading ? (
                  <p className="text-xs text-slate-500 py-4">Loading consensus...</p>
                ) : consensus && consensus.agents ? (
                  <>
                    <div className="space-y-2.5 mb-3.5">
                      {consensus.agents.slice(0, 4).map((agent, idx) => {
                        const icons = [BarChart3, Building2, Brain, Shield];
                        const colorStyles = [
                          { bg: 'bg-blue-50 text-blue-600 border-blue-200' },
                          { bg: 'bg-purple-50 text-purple-600 border-purple-200' },
                          { bg: 'bg-emerald-50 text-emerald-600 border-emerald-200' },
                          { bg: 'bg-amber-50 text-amber-600 border-amber-200' },
                        ];
                        const style = colorStyles[idx];
                        const names = ['Price Action Agent', 'Market Structure Agent', 'ML Filter Agent', 'Risk Manager'];
                        const AgentIcon = icons[idx];

                        return (
                          <div key={idx} className="p-2.5 rounded-xl bg-white/90 border border-slate-200/80 flex items-center justify-between shadow-xs">
                            <div className="flex items-center gap-2.5">
                              <div className={cn("w-7 h-7 rounded-lg flex items-center justify-center border", style.bg)}>
                                <AgentIcon size={14} aria-hidden="true" />
                              </div>
                              <div>
                                <div className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                                  <span>{agent.agent_name || names[idx]}</span>
                                  {(agent.agent_name === 'Sentiment Agent' || names[idx] === 'Sentiment Agent' || idx === 2) && (
                                    <span className="text-[9px] font-bold px-1.5 py-0.2 bg-emerald-100 text-emerald-800 rounded border border-emerald-200">
                                      LLM News
                                    </span>
                                  )}
                                </div>
                                <div className="text-[10px] text-slate-500">
                                  Signal: <span className="font-semibold text-slate-700">{agent.prediction || 'HOLD'}</span>
                                </div>
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="text-[10px] text-slate-500 mb-0.5">{((agent.confidence ?? 0) * 100).toFixed(0)}%</div>
                              <div className="w-16 bg-slate-200/80 rounded-full h-1.5 overflow-hidden">
                                <div className="h-full bg-blue-600 rounded-full" style={{ width: `${(agent.confidence ?? 0) * 100}%` }}></div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Overall Consensus Summary Gauge */}
                    <div className="p-3.5 rounded-2xl bg-gradient-to-r from-blue-50 via-sky-50 to-indigo-50 border border-blue-200/80">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-bold text-slate-800">Overall AI Consensus:</span>
                        <span className="text-xs font-black text-blue-700 uppercase font-mono">{consensus.consensus || 'HOLD'}</span>
                      </div>
                      <div className="w-full bg-blue-200/60 rounded-full h-2 overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-blue-600 to-indigo-600 rounded-full" 
                          style={{ width: `${(consensus.confidence ?? 0) * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-slate-500 py-4">No consensus data available</p>
                )}
              </div>

            </div>

            {/* ======================================================== */}
            {/* RIGHT MAIN ANALYTICAL CANVAS COLUMN (xl:col-span-8 / 67%)*/}
            {/* ======================================================== */}
            <div className="xl:col-span-8 flex flex-col gap-6">

              {/* Market Structure State Card */}
              <div className="glass-card p-5 sm:p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold">
                      <Building2 size={18} aria-hidden="true" />
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-slate-900 leading-tight">Market Structure State</h2>
                      <p className="text-[11px] text-slate-500 font-medium">Smart Money Concepts (SMC) Telemetry</p>
                    </div>
                  </div>
                  <span className={cn(
                    "px-3 py-1 rounded-xl font-bold text-xs flex items-center gap-1.5 border",
                    marketStructure?.is_entry_valid
                      ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                      : "bg-slate-100 text-slate-600 border-slate-300"
                  )}>
                    {marketStructure?.is_entry_valid ? <CheckCircle2 size={14} className="text-emerald-600" /> : <PauseCircle size={14} className="text-slate-500" />}
                    <span>{marketStructure?.is_entry_valid ? "ENTRY ZONE ACTIVE" : "NO VALID ENTRY"}</span>
                  </span>
                </div>
                
                {structureLoading ? (
                  <p className="text-xs text-slate-500 py-4">Loading market structure...</p>
                ) : marketStructure ? (
                  <>
                    {/* Phase and Direction 2-Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 mb-4">
                      <div className="p-3.5 rounded-2xl bg-white/90 border border-blue-200/80 shadow-xs">
                        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Current Phase</span>
                        <div className="text-lg font-black text-blue-700 mt-0.5">{marketStructure.phase_name}</div>
                        <div className="text-[11px] text-slate-500">Phase {marketStructure.phase} &bull; Liquidity sweep</div>
                      </div>
                      
                      <div className="p-3.5 rounded-2xl bg-white/90 border border-blue-200/80 shadow-xs">
                        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Structure Direction</span>
                        <div className={cn(
                          "text-lg font-black mt-0.5 flex items-center gap-1.5",
                          marketStructure.direction === 'BULLISH' ? 'text-emerald-600' : 
                          marketStructure.direction === 'BEARISH' ? 'text-rose-600' : 
                          'text-slate-700'
                        )}>
                          {marketStructure.direction === 'BULLISH' ? (<><TrendingUp size={18} aria-hidden="true" /> BULLISH</>) :
                           marketStructure.direction === 'BEARISH' ? (<><TrendingDown size={18} aria-hidden="true" /> BEARISH</>) :
                           (<><MoveRight size={18} aria-hidden="true" /> NEUTRAL</>)}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {marketStructure.direction === 'BULLISH' ? 'Higher High sequence intact' : 'Structural alignment'}
                        </div>
                      </div>
                    </div>

                    {/* BoS & CHoCH Analytics 4-Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-4">
                      <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                        <span className="text-[10px] text-slate-500 font-bold uppercase">BoS Price</span>
                        <div className="font-mono font-bold text-xs text-slate-900 mt-0.5">
                          {marketStructure.bos_price > 0 ? marketStructure.bos_price.toFixed(2) : 'N/A'}
                        </div>
                      </div>
                      <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                        <span className="text-[10px] text-slate-500 font-bold uppercase">BoS Direction</span>
                        <div className="font-bold text-xs text-emerald-600 mt-0.5">
                          {marketStructure.bos_direction}
                        </div>
                      </div>
                      <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                        <span className="text-[10px] text-slate-500 font-bold uppercase">CHoCH Price</span>
                        <div className="font-mono font-bold text-xs text-slate-900 mt-0.5">
                          {marketStructure.choch_price > 0 ? marketStructure.choch_price.toFixed(2) : 'N/A'}
                        </div>
                      </div>
                      <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                        <span className="text-[10px] text-slate-500 font-bold uppercase">BoS Chain</span>
                        <div className="font-bold text-xs text-blue-700 mt-0.5">
                          {marketStructure.bos_chain_count || 0} Consecutive
                        </div>
                      </div>
                    </div>

                    {/* H1 Trend Context Bar */}
                    <div className="p-3 rounded-xl bg-blue-50/70 border border-blue-200/80 flex items-center justify-between text-xs">
                      <span className="flex items-center gap-2 text-slate-700 font-medium">
                        <BarChart3 size={15} className="text-blue-600" />
                        <span>H1 Context: <strong>{marketStructure.h1_above_ema200 ? 'Above EMA 200 (Bullish)' : 'Below EMA 200 (Bearish)'}</strong></span>
                      </span>
                      <span className={cn(
                        "px-2.5 py-0.5 rounded-md font-bold text-[10px] border",
                        marketStructure.h1_trend_aligned ? "bg-emerald-100 text-emerald-800 border-emerald-300" : "bg-rose-100 text-rose-800 border-rose-300"
                      )}>
                        {marketStructure.h1_trend_aligned ? "TREND ALIGNED" : "NOT ALIGNED"}
                      </span>
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-slate-500 py-4">No market structure data available</p>
                )}
              </div>

              {/* Performance & Health Card (Integrated KPIs + System Resources) */}
              <div className="glass-card p-5 sm:p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold">
                      <TrendingUp size={18} aria-hidden="true" />
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-slate-900 leading-tight">Performance & Health</h2>
                      <p className="text-[11px] text-slate-500 font-medium">Historical KPIs & Server Telemetry</p>
                    </div>
                  </div>
                  <span className="text-xs font-mono font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-lg border border-emerald-200">
                    PROFITABLE
                  </span>
                </div>
                
                {/* Mini SVG Equity Curve */}
                <div className="p-3.5 rounded-2xl bg-blue-50/50 border border-blue-200/60 mb-4">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-700 mb-2">
                    <span>Equity Growth Curve</span>
                    <span className="text-emerald-600 font-mono font-bold">
                      {(stats?.profit ?? 0) >= 0 ? `+$${(stats?.profit ?? 0).toFixed(2)} Net` : `-$${Math.abs(stats?.profit ?? 0).toFixed(2)} Net`}
                    </span>
                  </div>
                  <svg viewBox="0 0 400 70" className="w-full h-16 stroke-blue-600 fill-blue-500/10">
                    <path d="M 0 55 Q 40 50, 80 42 T 160 35 T 240 22 T 320 18 T 400 8 L 400 70 L 0 70 Z" strokeWidth="2" />
                    <path d="M 0 55 Q 40 50, 80 42 T 160 35 T 240 22 T 320 18 T 400 8" fill="none" strokeWidth="2.5" stroke="#0284c7" />
                  </svg>
                </div>

                {/* 4 Performance Metric Badges */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  <div className="p-3 rounded-xl bg-white/90 border border-slate-200 text-center shadow-xs">
                    <span className="text-[10px] text-slate-500 font-bold uppercase">Win Rate</span>
                    <div className="text-lg font-black text-emerald-600 mt-0.5">
                      {performanceStats ? `${performanceStats.win_rate.toFixed(1)}%` : '0%'}
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-white/90 border border-slate-200 text-center shadow-xs">
                    <span className="text-[10px] text-slate-500 font-bold uppercase">Profit Factor</span>
                    <div className="text-lg font-black text-blue-600 mt-0.5">
                      {performanceStats ? performanceStats.profit_factor.toFixed(2) : '0.00'}
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-white/90 border border-slate-200 text-center shadow-xs">
                    <span className="text-[10px] text-slate-500 font-bold uppercase">Sharpe Ratio</span>
                    <div className="text-lg font-black text-slate-800 mt-0.5">
                      {performanceStats?.sharpe_ratio ? performanceStats.sharpe_ratio.toFixed(2) : 'N/A'}
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-white/90 border border-slate-200 text-center shadow-xs">
                    <span className="text-[10px] text-slate-500 font-bold uppercase">Max DD</span>
                    <div className="text-lg font-black text-slate-700 mt-0.5">
                      {performanceStats ? `${performanceStats.max_drawdown.toFixed(1)}%` : '0%'}
                    </div>
                  </div>
                </div>

                {/* Integrated System Resources (CPU & RAM) */}
                <div className="mt-4 pt-3.5 border-t border-slate-200/80 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <div className="flex items-center justify-between text-[11px] mb-1">
                      <span className="text-slate-600 font-medium">CPU Load (Python Server):</span>
                      <span className="font-mono font-bold text-slate-800">{systemStatus?.resources?.cpu_usage_percent.toFixed(1) ?? '0'}%</span>
                    </div>
                    <div className="w-full bg-slate-200/80 rounded-full h-1.5 overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full" style={{ width: `${systemStatus?.resources?.cpu_usage_percent ?? 0}%` }}></div>
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between text-[11px] mb-1">
                      <span className="text-slate-600 font-medium">Memory Usage (RAM):</span>
                      <span className="font-mono font-bold text-slate-800">
                        {systemStatus?.resources?.memory_usage_mb.toFixed(0) ?? '0'} MB ({systemStatus?.resources?.memory_usage_percent.toFixed(0) ?? '0'}%)
                      </span>
                    </div>
                    <div className="w-full bg-slate-200/80 rounded-full h-1.5 overflow-hidden">
                      <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${systemStatus?.resources?.memory_usage_percent ?? 0}%` }}></div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Live Activity Stream Card */}
              <div className="glass-card p-5 sm:p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-sky-100 text-sky-700 flex items-center justify-center font-bold">
                      <ClipboardList size={18} aria-hidden="true" />
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-slate-900 leading-tight">Live Activity Stream</h2>
                      <p className="text-[11px] text-slate-500 font-medium">Realtime Transaction & Telemetry Events</p>
                    </div>
                  </div>
                  {activityLogs && activityLogs.logs && activityLogs.logs.length > 0 && (
                    <span className="px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-700 font-mono text-[10px] font-bold border border-blue-200">
                      {activityLogs.logs.length} EVENTS
                    </span>
                  )}
                </div>
                
                <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                  {activityLogsLoading ? (
                    <div className="p-4 text-center text-xs text-slate-400">Loading activity logs...</div>
                  ) : activityLogsError ? (
                    <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center gap-2">
                      <XCircle size={15} /> Failed to fetch activity logs
                    </div>
                  ) : activityLogs && activityLogs.logs && activityLogs.logs.length > 0 ? (
                    activityLogs.logs.map((log) => {
                      const logDate = new Date(log.timestamp);
                      const timeStr = logDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                      const isSuccess = log.severity === 'success';

                      return (
                        <div key={log.id} className="p-3 rounded-xl bg-white/90 border border-slate-200/80 flex items-start gap-3 shadow-xs hover:border-blue-300 transition-colors">
                          <div className="text-[10px] font-mono font-bold text-slate-400 mt-0.5 w-14 shrink-0">{timeStr}</div>
                          <div className={cn("w-2 h-2 rounded-full mt-1.5 shrink-0", isSuccess ? "bg-emerald-500" : "bg-blue-500")}></div>
                          <div className="flex-1">
                            <div className="text-xs font-bold text-slate-800 leading-tight">{log.title}</div>
                            <div className="text-[11px] text-slate-500 mt-0.5 leading-snug">{log.message}</div>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="p-4 text-center text-xs text-slate-400">No activity logs recorded</div>
                  )}
                </div>
              </div>

            </div>

          </div>

          {/* Footer */}
          <MT5Footer />
        </div>
      </div>
    </div>
  );
}
