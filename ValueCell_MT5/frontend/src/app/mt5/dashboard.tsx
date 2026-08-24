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
          paddingLeft: "240px", // Space for sidebar (exact sidebar width)
          minHeight: "100vh"
        }}
      >
        <div className="px-12 py-8">
          <div className="container">
          {/* Status Bar */}
        <div className="status-bar">
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

        {/* Metrics Grid */}
        <div className="metrics-grid">
          {/* Balance Card */}
          <div className="metric-card">
            <div className="metric-icon"><Wallet size={20} aria-hidden="true" /></div>
            <div className="metric-label">Balance</div>
            <div className="metric-value">${(stats?.balance ?? 1000).toFixed(2)}</div>
            <div className="metric-change positive">Equity: {((stats?.equity ?? stats?.balance ?? 1000) / (stats?.balance || 1000) * 100).toFixed(0)}%</div>
          </div>

          {/* Open Positions Card */}
          <div className="metric-card">
            <div className="metric-icon"><BarChart3 size={20} aria-hidden="true" /></div>
            <div className="metric-label">Open Positions</div>
            <div className="metric-value">{positions?.length ?? 0}</div>
            <div className="metric-change">Margin: 0%</div>
          </div>

          {/* Today P&L Card */}
          <div className="metric-card">
            <div className="metric-icon"><TrendingUp size={20} aria-hidden="true" /></div>
            <div className="metric-label">Today P&L</div>
            <div className="metric-value">${(stats?.profit ?? 0).toFixed(2)}</div>
            <div className={`metric-change ${(stats?.profit ?? 0) >= 0 ? 'positive' : 'negative'}`}>
              {((stats?.profit ?? 0) / (stats?.balance || 1000) * 100).toFixed(2)}%
            </div>
          </div>

          {/* System Health Card */}
          <div className="metric-card">
            <div className="metric-icon"><Zap size={20} aria-hidden="true" /></div>
            <div className="metric-label">System Health</div>
            <div className={`metric-value ${(systemStatus?.system_health_percent ?? 0) >= 90 ? 'positive' : (systemStatus?.system_health_percent ?? 0) >= 50 ? 'neutral' : 'negative'}`}>
              {systemStatus?.system_health_percent.toFixed(0) ?? '0'}%
            </div>
            <div className={`metric-change ${systemStatus?.mt5_connected ? 'positive' : 'negative'}`}>
              {systemStatus?.mt5_connected ? 'All systems operational' : 'MT5 disconnected'}
            </div>
          </div>
        </div>

        {/* Current Signal */}
        <div className="glass-card signal-card">
          <div className="signal-header">
            <h2 style={{ fontSize: '20px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}><Target size={18} aria-hidden="true" /> Current Market Signal</h2>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-tertiary)' }}>XAUUSD • M15</span>
              <span className={`signal-badge badge-${(signal?.signal || 'HOLD').toLowerCase()}`}>
                {signal?.signal || 'HOLD'}
              </span>
            </div>
          </div>
          
          {signalLoading ? (
            <p style={{ color: 'var(--text-secondary)' }}>Loading signal...</p>
          ) : signal ? (
            <>
              <div style={{ padding: '20px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '12px', margin: '16px 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <span style={{ fontSize: '14px', color: 'var(--text-tertiary)' }}>Signal Type</span>
                  <span style={{ fontWeight: 600 }}>{signal.signal}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <span style={{ fontSize: '14px', color: 'var(--text-tertiary)' }}>Entry Price</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
                    {signal.entry_price > 0 ? signal.entry_price.toFixed(2) : 'N/A'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '14px', color: 'var(--text-tertiary)' }}>Confidence</span>
                  <span style={{ fontWeight: 600 }}>{((signal.confidence ?? 0) * 100).toFixed(0)}%</span>
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '14px', color: 'var(--text-tertiary)' }}>Confidence Level</span>
                  <span style={{ fontSize: '14px', fontWeight: 600 }}>{((signal.confidence ?? 0) * 100).toFixed(0)}%</span>
                </div>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${(signal.confidence ?? 0) * 100}%` }}></div>
                </div>
                <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '12px' }}>
                  <MessageSquare size={14} style={{ verticalAlign: '-2px', marginRight: '6px' }} aria-hidden="true" />
                  {signal.stop_loss > 0 && signal.take_profit > 0
                    ? `SL: ${signal.stop_loss.toFixed(2)} | TP: ${signal.take_profit.toFixed(2)}`
                    : 'Waiting for market structure confirmation (BoS + trend alignment)...'}
                </p>
              </div>
            </>
          ) : (
            <p style={{ color: 'var(--text-secondary)' }}>No signal data available</p>
          )}
        </div>

        {/* Two Column: Agent Consensus & Performance Charts */}
        <div className="two-column">
          {/* Agent Consensus */}
          <div className="glass-card">
            <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}><Bot size={18} aria-hidden="true" /> Agent Consensus</h2>
            
            {consensusLoading ? (
              <p style={{ color: 'var(--text-secondary)' }}>Loading consensus...</p>
            ) : consensus && consensus.agents ? (
              <>
                {consensus.agents.slice(0, 4).map((agent, idx) => {
                  const icons = [BarChart3, Building2, Brain, Shield];
                  const colors = [
                    { bg: 'rgba(59, 130, 246, 0.2)', border: 'var(--neon-blue)' },
                    { bg: 'rgba(139, 92, 246, 0.2)', border: 'var(--neon-purple)' },
                    { bg: 'rgba(16, 185, 129, 0.2)', border: 'var(--neon-emerald)' },
                    { bg: 'rgba(251, 191, 36, 0.2)', border: 'var(--neon-amber)' },
                  ];
                  const color = colors[idx];
                  const names = ['Price Action Agent', 'Market Structure Agent', 'ML Filter Agent', 'Risk Manager'];
                  const AgentIcon = icons[idx];

                  return (
                    <div key={idx} className="agent-row">
                      <div className="agent-info">
                        <div className="agent-icon" style={{ background: color.bg, borderColor: color.border }}>
                          <AgentIcon size={16} aria-hidden="true" />
                        </div>
                        <div className="agent-details">
                          <div className="agent-name">{agent.agent_name || names[idx]}</div>
                          <div className="agent-signal">
                            Signal: <span className="neon-text">{agent.prediction || 'HOLD'}</span>
                            {(agent.agent_name === 'Sentiment Agent' || names[idx] === 'Sentiment Agent' || idx === 2) && (
                              <span style={{ marginLeft: '8px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)', color: '#34d399', fontSize: '10px', fontWeight: 600 }}>
                                <Newspaper size={10} style={{ verticalAlign: '-1px', marginRight: '4px' }} aria-hidden="true" />LLM News
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div style={{ minWidth: '100px' }}>
                        <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>
                          Confidence
                        </div>
                        <div className="progress-bar" style={{ width: '100px' }}>
                          <div className="progress-fill" style={{ width: `${(agent.confidence ?? 0) * 100}%` }}></div>
                        </div>
                      </div>
                    </div>
                  );
                })}

                {/* Consensus Summary */}
                <div style={{ marginTop: '20px', padding: '16px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600 }}>Overall Consensus</span>
                    <span style={{ fontSize: '18px', fontWeight: 700, color: 'var(--neon-amber)' }}>
                      {consensus.consensus || 'HOLD'}
                    </span>
                  </div>
                  <div className="progress-bar" style={{ marginTop: '12px' }}>
                    <div 
                      className="progress-fill" 
                      style={{ 
                        width: `${(consensus.confidence ?? 0) * 100}%`,
                        background: 'linear-gradient(90deg, var(--neon-amber), var(--neon-ruby))'
                      }}
                    ></div>
                  </div>
                </div>
              </>
            ) : (
              <p style={{ color: 'var(--text-secondary)' }}>No consensus data available</p>
            )}
          </div>

          {/* Performance Charts */}
          <div className="glass-card">
            <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}><TrendingUp size={18} aria-hidden="true" /> Performance Overview</h2>
            
            {/* Mini Chart Placeholder */}
            <div style={{ background: 'rgba(31, 41, 55, 0.3)', borderRadius: '12px', padding: '20px', marginBottom: '16px' }}>
              <div style={{ textAlign: 'center', color: 'var(--text-tertiary)', padding: '40px 0' }}>
                <BarChart3 size={44} strokeWidth={1.3} style={{ marginBottom: '12px' }} aria-hidden="true" className="mx-auto opacity-60" />
                <div style={{ fontSize: '14px' }}>Equity Curve Chart</div>
                <div style={{ fontSize: '12px', marginTop: '4px' }}>(Live chart will render here)</div>
              </div>
            </div>

            {/* Performance Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ padding: '12px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>Win Rate</div>
                <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--neon-emerald)' }}>
                  {performanceStats ? `${performanceStats.win_rate.toFixed(1)}%` : '0%'}
                </div>
              </div>
              <div style={{ padding: '12px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>Profit Factor</div>
                <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--neon-cyan)' }}>
                  {performanceStats ? performanceStats.profit_factor.toFixed(2) : '0.00'}
                </div>
              </div>
              <div style={{ padding: '12px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>Sharpe Ratio</div>
                <div style={{ fontSize: '20px', fontWeight: 600 }}>
                  {performanceStats?.sharpe_ratio ? performanceStats.sharpe_ratio.toFixed(2) : 'N/A'}
                </div>
              </div>
              <div style={{ padding: '12px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>Max DD</div>
                <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-muted)' }}>
                  {performanceStats ? `${performanceStats.max_drawdown.toFixed(1)}%` : '0%'}
                </div>
              </div>
            </div>

            {/* System Resources */}
            <div style={{ marginTop: '20px', padding: '16px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '12px' }}>
              <div style={{ fontWeight: 600, marginBottom: '12px' }}>System Resources</div>
              
              <div style={{ marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>CPU Usage</span>
                  <span>{systemStatus?.resources?.cpu_usage_percent.toFixed(1) ?? '0'}%</span>
                </div>
                <div className="progress-bar">
                  <div 
                    className="progress-fill" 
                    style={{ 
                      width: `${systemStatus?.resources?.cpu_usage_percent ?? 0}%`,
                      background: 'linear-gradient(90deg, var(--neon-cyan), var(--neon-blue))'
                    }}
                  ></div>
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>Memory Usage</span>
                  <span>{systemStatus?.resources?.memory_usage_mb.toFixed(0) ?? '0'} MB</span>
                </div>
                <div className="progress-bar">
                  <div 
                    className="progress-fill" 
                    style={{ 
                      width: `${systemStatus?.resources?.memory_usage_percent ?? 0}%`,
                      background: 'linear-gradient(90deg, var(--neon-emerald), var(--neon-cyan))'
                    }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Market Structure State */}
        <div className="glass-card" style={{ marginBottom: '24px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}><Building2 size={18} aria-hidden="true" /> Market Structure State</h2>
          
          {structureLoading ? (
            <p style={{ color: 'var(--text-secondary)' }}>Loading market structure...</p>
          ) : marketStructure ? (
            <>
              {/* Phase and Direction */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
                <div style={{ padding: '16px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '12px' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '8px' }}>Current Phase</div>
                  <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--neon-cyan)' }}>
                    {marketStructure.phase_name}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                    Phase {marketStructure.phase}
                  </div>
                </div>
                
                <div style={{ padding: '16px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '12px' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '8px' }}>Direction</div>
                  <div style={{ 
                    fontSize: '24px', 
                    fontWeight: 700,
                    color: marketStructure.direction === 'BULLISH' ? 'var(--neon-emerald)' : 
                           marketStructure.direction === 'BEARISH' ? 'var(--neon-ruby)' : 
                           'var(--text-tertiary)'
                  }}>
                    {marketStructure.direction === 'BULLISH' ? (<span className="inline-flex items-center gap-1"><TrendingUp size={20} aria-hidden="true" /> BULLISH</span>) :
                     marketStructure.direction === 'BEARISH' ? (<span className="inline-flex items-center gap-1"><TrendingDown size={20} aria-hidden="true" /> BEARISH</span>) :
                     (<span className="inline-flex items-center gap-1"><MoveRight size={20} aria-hidden="true" /> NEUTRAL</span>)}
                  </div>
                </div>
              </div>

              {/* Entry Validity Badge */}
              <div style={{ 
                padding: '12px 16px', 
                background: marketStructure.is_entry_valid 
                  ? 'rgba(16, 185, 129, 0.2)' 
                  : 'rgba(107, 114, 128, 0.2)',
                border: `1px solid ${marketStructure.is_entry_valid ? 'var(--neon-emerald)' : 'var(--border-color)'}`,
                borderRadius: '8px',
                marginBottom: '20px',
                textAlign: 'center'
              }}>
                <div style={{ fontWeight: 600, fontSize: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                  {marketStructure.is_entry_valid ? (<><CheckCircle2 size={18} aria-hidden="true" /> ENTRY ZONE ACTIVE</>) : (<><PauseCircle size={18} aria-hidden="true" /> NO VALID ENTRY</>)}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                  {marketStructure.is_entry_valid 
                    ? 'BoS confirmed and H1 trend aligned' 
                    : 'Waiting for BoS confirmation or trend alignment'}
                </div>
              </div>

              {/* BoS Information */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', color: 'var(--neon-amber)' }}>
                  <MapPin size={14} style={{ verticalAlign: '-2px', marginRight: '6px' }} aria-hidden="true" />Break of Structure (BoS)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div style={{ padding: '12px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>BoS Price</div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
                      {marketStructure.bos_price > 0 ? marketStructure.bos_price.toFixed(2) : 'N/A'}
                    </div>
                  </div>
                  <div style={{ padding: '12px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>BoS Direction</div>
                    <div style={{ fontWeight: 600 }}>
                      {marketStructure.bos_direction === 'BULLISH' ? (<span className="inline-flex items-center"><StatusDot color="#10B981" /> BULLISH</span>) :
                       marketStructure.bos_direction === 'BEARISH' ? (<span className="inline-flex items-center"><StatusDot color="#EF4444" /> BEARISH</span>) :
                       (<span className="inline-flex items-center"><StatusDot color="#94A3B8" /> NEUTRAL</span>)}
                    </div>
                  </div>
                  <div style={{ padding: '12px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>Bars Since BoS</div>
                    <div style={{ fontWeight: 600 }}>{marketStructure.bars_since_bos}</div>
                  </div>
                  <div style={{ padding: '12px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>BoS Chain</div>
                    <div style={{ fontWeight: 600 }}>{marketStructure.bos_chain_count || 0} BoS</div>
                  </div>
                </div>
              </div>

              {/* CHoCH Information */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', color: 'var(--neon-purple)' }}>
                  <RefreshCw size={14} style={{ verticalAlign: '-2px', marginRight: '6px' }} aria-hidden="true" />Change of Character (CHoCH)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div style={{ padding: '12px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>CHoCH Price</div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
                      {marketStructure.choch_price > 0 ? marketStructure.choch_price.toFixed(2) : 'N/A'}
                    </div>
                  </div>
                  <div style={{ padding: '12px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>CHoCH Direction</div>
                    <div style={{ fontWeight: 600 }}>
                      {marketStructure.choch_direction === 'BULLISH' ? (<span className="inline-flex items-center"><StatusDot color="#10B981" /> BULLISH</span>) :
                       marketStructure.choch_direction === 'BEARISH' ? (<span className="inline-flex items-center"><StatusDot color="#EF4444" /> BEARISH</span>) :
                       (<span className="inline-flex items-center"><StatusDot color="#94A3B8" /> NEUTRAL</span>)}
                    </div>
                  </div>
                </div>
              </div>

              {/* H1 Trend Context */}
              <div style={{ padding: '16px', background: 'rgba(31, 41, 55, 0.3)', borderRadius: '12px' }}>
                <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}><BarChart3 size={14} aria-hidden="true" /> H1 Trend Context</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-tertiary)' }}>Price vs EMA200</span>
                  <span style={{ fontWeight: 600 }}>
                    {marketStructure.h1_above_ema200 ? (<span className="inline-flex items-center"><StatusDot color="#10B981" /> Above</span>) : (<span className="inline-flex items-center"><StatusDot color="#EF4444" /> Below</span>)}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-tertiary)' }}>Trend Aligned</span>
                  <span style={{ fontWeight: 600 }}>
                    {marketStructure.h1_trend_aligned ? (<span className="inline-flex items-center gap-1"><CheckCircle2 size={13} color="#10B981" aria-hidden="true" /> Aligned</span>) : (<span className="inline-flex items-center gap-1"><XCircle size={13} color="#EF4444" aria-hidden="true" /> Not Aligned</span>)}
                  </span>
                </div>
              </div>
            </>
          ) : (
            <p style={{ color: 'var(--text-secondary)' }}>No market structure data available</p>
          )}
        </div>

        {/* Activity Log */}
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}><ClipboardList size={18} aria-hidden="true" /> Live Activity Stream</h2>
            {activityLogs && activityLogs.logs && activityLogs.logs.length > 0 && (
              <span style={{
                fontSize: '11px',
                color: 'var(--neon-cyan)',
                background: 'rgba(6, 182, 212, 0.1)',
                border: '1px solid rgba(6, 182, 212, 0.25)',
                borderRadius: '20px',
                padding: '4px 12px',
                fontFamily: "'JetBrains Mono', monospace",
                letterSpacing: '0.5px',
              }}>
                {activityLogs.logs.length} events
              </span>
            )}
          </div>
          
          <div className="activity-log">
            {activityLogsLoading ? (
              <div className="log-entry">
                <div className="log-message" style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>
                  Loading activity logs...
                </div>
              </div>
            ) : activityLogsError ? (
              <div className="log-entry">
                <div className="log-icon log-error"><XCircle size={14} aria-hidden="true" /></div>
                <div className="log-message">
                  <div style={{ fontWeight: 600 }}>Failed to Load Activity Logs</div>
                  <div style={{ color: 'var(--text-tertiary)', fontSize: '13px' }}>
                    Unable to fetch activity logs from the server. Please check your connection.
                  </div>
                </div>
              </div>
            ) : activityLogs && activityLogs.logs && activityLogs.logs.length > 0 ? (
              activityLogs.logs.map((log) => {
                const icon = EVENT_TYPE_ICONS[log.event_type];
                const FallbackIcon = icon || FileText;
                const severityClass = SEVERITY_CLASSES[log.severity] || 'log-info';
                const logDate = new Date(log.timestamp);
                const dateStr = logDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                const timeStr = logDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

                return (
                  <div key={log.id} className="log-entry">
                    <div className="log-time">
                      <div>{dateStr}</div>
                      <div style={{ opacity: 0.65, fontSize: '10px' }}>{timeStr}</div>
                    </div>
                    <div className={`log-icon ${severityClass}`}><FallbackIcon size={14} aria-hidden="true" /></div>
                    <div className="log-message">
                      <div style={{ fontWeight: 600 }}>{log.title}</div>
                      <div style={{ color: 'var(--text-tertiary)', fontSize: '13px' }}>
                        {log.message}
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="log-entry">
                <div className="log-icon log-info"><Info size={14} aria-hidden="true" /></div>
                <div className="log-message">
                  <div style={{ fontWeight: 600 }}>No Activity Logs</div>
                  <div style={{ color: 'var(--text-tertiary)', fontSize: '13px' }}>
                    No recent activity to display. Start trading to see activity logs.
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <MT5Footer />
          </div>
        </div>
      </div>
    </div>
  );
}
