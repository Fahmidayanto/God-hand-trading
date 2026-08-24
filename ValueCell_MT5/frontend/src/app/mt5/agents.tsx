import { useEffect, useRef, useState } from "react";
import { BarChart3, Building2, Brain, Shield, Bot, Scale } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Particles from "@tsparticles/react";
import MT5Footer from "./components/MT5Footer";

interface Agent {
  name: string;
  role: string;
  description: string;
  accuracy: number;
  signals_today: number;
  signal: string;
  confidence: number;
  icon: LucideIcon;
  color: string;
}

export default function AgentsPage() {
  const pageRef = useRef<HTMLDivElement>(null);
  const [agents, setAgents] = useState<Agent[]>([
    {
      name: "Price Action Agent",
      role: "Technical Analysis Expert",
      description:
        "Analyzes price movements, candlestick patterns, and support/resistance levels to identify high-probability trading setups. Specializes in Smart Money Concepts (SMC) and orderblock detection.",
      accuracy: 0,
      signals_today: 0,
      signal: "HOLD",
      confidence: 0,
      icon: BarChart3,
      color: "blue",
    },
    {
      name: "Market Structure Agent",
      role: "Trend & Structure Analysis",
      description:
        "Identifies market structure changes including CHoCH (Change of Character) and BoS (Break of Structure). Tracks highs, lows, and structural shifts to confirm trend direction and reversals.",
      accuracy: 0,
      signals_today: 0,
      signal: "HOLD",
      confidence: 0,
      icon: Building2,
      color: "purple",
    },
    {
      name: "ML Filter Agent",
      role: "Machine Learning Classifier",
      description:
        "Uses CatBoost ML model trained on historical data to filter low-quality signals. Analyzes 50+ features including volatility, volume, momentum, and market conditions to predict trade outcomes.",
      accuracy: 0,
      signals_today: 0,
      signal: "FILTER",
      confidence: 0,
      icon: Brain,
      color: "emerald",
    },
    {
      name: "Risk Manager",
      role: "Position & Risk Control",
      description:
        "Calculates optimal position sizes, stop-loss, and take-profit levels based on account balance, risk percentage, and market volatility. Ensures trades stay within risk management parameters.",
      accuracy: 0,
      signals_today: 0,
      signal: "ACTIVE",
      confidence: 0,
      icon: Shield,
      color: "amber",
    },
  ]);
  const [consensus, setConsensus] = useState({
    consensus: "HOLD",
    confidence: 0,
    threshold: 40,
  });

  useEffect(() => {
    loadAgentsData();
    const interval = setInterval(loadAgentsData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadAgentsData = async () => {
    if (!pageRef.current?.offsetParent) return;
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const response = await fetch(
        `${apiUrl}/trading/agents/consensus`
      );
      if (response.ok) {
        const data = await response.json();
        
        // Update agents with API data
        if (data.agents && data.agents.length > 0) {
          setAgents(prevAgents => prevAgents.map((agent, index) => ({
            ...agent,
            accuracy: data.agents[index]?.accuracy ?? agent.accuracy,
            signals_today: data.agents[index]?.signals_today ?? agent.signals_today,
            signal: data.agents[index]?.prediction ?? agent.signal,
            confidence: (data.agents[index]?.confidence ?? 0) * 100,
          })));
        }
        
        setConsensus({
          consensus: data.consensus ?? "HOLD",
          confidence: (data.confidence ?? 0) * 100,
          threshold: 40,
        });
      }
    } catch (error) {
      console.error("Error loading agents data:", error);
      console.warn('⚠️ Unable to load agents data from API');
    }
  };

  const getColorClass = (color: string) => {
    const colors: Record<string, string> = {
      blue: "border-[var(--neon-blue)] bg-[rgba(59,130,246,0.2)]",
      purple: "border-[var(--neon-purple)] bg-[rgba(139,92,246,0.2)]",
      emerald: "border-[var(--neon-emerald)] bg-[rgba(16,185,129,0.2)]",
      amber: "border-[var(--neon-amber)] bg-[rgba(251,191,36,0.2)]",
    };
    return colors[color] || colors.blue;
  };

  const getProgressColor = (color: string) => {
    const colors: Record<string, string> = {
      blue: "bg-gradient-to-r from-[var(--neon-blue)] to-[var(--neon-cyan)]",
      purple: "bg-gradient-to-r from-[var(--neon-purple)] to-[var(--neon-blue)]",
      emerald: "bg-gradient-to-r from-[var(--neon-emerald)] to-[var(--neon-cyan)]",
      amber: "bg-gradient-to-r from-[var(--neon-amber)] to-[var(--neon-ruby)]",
    };
    return colors[color] || colors.blue;
  };

  return (
    <div
      ref={pageRef}
      style={{ 
        background: "var(--bg-deepspace)",
        minHeight: "100vh",
        width: "100%",
        position: "relative",
        overflowX: "auto",
        overflowY: "auto"
      }}
    >
      <Particles
        id="tsparticles-agents"
        options={{
            background: { color: { value: "transparent" } },
            fpsLimit: 60,
            particles: {
              number: { value: 80, density: { enable: true } },
              color: { value: "#3b82f6" },
              shape: { type: "circle" },
              opacity: { value: 0.3 },
              size: { value: { min: 1, max: 3 } },
              links: {
                enable: true,
                distance: 150,
                color: "#3b82f6",
                opacity: 0.2,
                width: 1,
              },
              move: {
                enable: true,
                speed: 1,
                direction: "none",
                outModes: { default: "out" },
              },
            },
            interactivity: {
              events: {
                onHover: { enable: true, mode: "grab" },
                onClick: { enable: true, mode: "push" },
              },
              modes: {
                grab: { distance: 140, links: { opacity: 0.5 } },
                push: { quantity: 4 },
              },
            },
          }}
          className="fixed inset-0 pointer-events-none"
          style={{ zIndex: 0 }}
        />

      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          zIndex: 1,
          background:
            "radial-gradient(circle at 20% 50%, rgba(59, 130, 246, 0.15) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.15) 0%, transparent 50%), radial-gradient(circle at 50% 80%, rgba(16, 185, 129, 0.1) 0%, transparent 50%), var(--bg-deepspace)",
        }}
      />

      <div 
        className="relative z-10" 
        style={{ 
          width: "100%",
          paddingLeft: "240px", // Space for sidebar (exact sidebar width)
          minHeight: "100vh"
        }}
      >
        <div className="px-12 py-8">

        {/* Page Header */}
        <div className="flex items-center gap-4 mb-8">
          <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.08] backdrop-blur-md hover:scale-105 transition-transform duration-200 ease-out shadow-[0_0_15px_rgba(var(--neon-cyan-rgb),0.15)] select-none">
            <Bot size={26} aria-hidden="true" className="text-[var(--text-primary)]" />
          </div>
          <div>
            <h1 className="text-[36px] font-bold text-[var(--text-primary)] leading-none mb-1">
              AI Trading Agents
            </h1>
            <p className="text-[var(--text-tertiary)] text-base">
              Monitor and configure your intelligent trading agents
            </p>
          </div>
        </div>

        {/* Agents Grid */}
        <div className="grid grid-cols-2 gap-6 mb-6">
          {agents.map((agent, index) => (
            <div
              key={index}
              className={`bg-[var(--glass-secondary)] border-2 border-[var(--glass-border)] rounded-2xl p-8 transition-all duration-300 hover:-translate-y-2 hover:scale-105 hover:shadow-[0_20px_50px_rgba(0,0,0,0.5)] relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-[5px] ${
                agent.color === "blue"
                  ? "before:bg-gradient-to-r before:from-[var(--neon-blue)] before:to-[var(--neon-cyan)] hover:border-[var(--neon-blue)]"
                  : agent.color === "purple"
                  ? "before:bg-gradient-to-r before:from-[var(--neon-purple)] before:to-[var(--neon-blue)] hover:border-[var(--neon-purple)]"
                  : agent.color === "emerald"
                  ? "before:bg-gradient-to-r before:from-[var(--neon-emerald)] before:to-[var(--neon-cyan)] hover:border-[var(--neon-emerald)]"
                  : "before:bg-gradient-to-r before:from-[var(--neon-amber)] before:to-[var(--neon-ruby)] hover:border-[var(--neon-amber)]"
              }`}
            >
              {/* Agent Header */}
              <div className="flex items-center gap-5 mb-6">
                <div
                  className={`w-20 h-20 rounded-2xl flex items-center justify-center border-2 transition-all duration-300 hover:scale-110 hover:rotate-[5deg] ${getColorClass(
                    agent.color
                  )}`}
                >
                  <agent.icon size={36} strokeWidth={1.6} aria-hidden="true" />
                </div>
                <div className="flex-1">
                  <div className="text-2xl font-bold mb-2">{agent.name}</div>
                  <div className="text-sm text-[var(--text-tertiary)] mb-1">
                    {agent.role}
                  </div>
                  <span className="inline-block px-3 py-1 rounded-md text-xs font-semibold bg-[rgba(16,185,129,0.2)] text-[var(--neon-emerald)]">
                    ● ACTIVE
                  </span>
                </div>
              </div>

              {/* Description */}
              <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-6">
                {agent.description}
              </p>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-[rgba(31,41,55,0.4)] p-4 rounded-[10px]">
                  <div className="text-xs text-[var(--text-tertiary)] mb-2">
                    Accuracy
                  </div>
                  <div className="text-xl font-semibold positive mono">
                    {agent.accuracy.toFixed(1)}%
                  </div>
                </div>
                <div className="bg-[rgba(31,41,55,0.4)] p-4 rounded-[10px]">
                  <div className="text-xs text-[var(--text-tertiary)] mb-2">
                    {agent.name === "Risk Manager"
                      ? "Risk Per Trade"
                      : "Signals Today"}
                  </div>
                  <div className="text-xl font-semibold mono">
                    {agent.name === "Risk Manager"
                      ? `${agent.accuracy.toFixed(1)}%`
                      : agent.signals_today}
                  </div>
                </div>
              </div>

              {/* Progress Bar */}
              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-sm text-[var(--text-tertiary)]">
                    Performance
                  </span>
                  <span className="text-sm font-semibold">
                    {agent.confidence.toFixed(0)}%
                  </span>
                </div>
                <div className="w-full h-2 bg-[rgba(100,116,139,0.2)] rounded overflow-hidden">
                  <div
                    className={`h-full rounded transition-all duration-1000 ${getProgressColor(
                      agent.color
                    )}`}
                    style={{ width: `${agent.confidence}%` }}
                  />
                </div>
              </div>

              {/* Controls */}
              <div className="flex gap-3 mt-6">
                <button className="flex-1 px-6 py-3 rounded-[10px] border border-[var(--glass-border)] bg-[var(--glass-secondary)] text-[var(--text-primary)] text-sm font-semibold transition-all hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(59,130,246,0.3)]">
                  View Logs
                </button>
                <button className="flex-1 px-6 py-3 rounded-[10px] border border-[var(--neon-blue)] bg-[var(--neon-blue)] text-white text-sm font-semibold transition-all hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(59,130,246,0.3)]">
                  Configure
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Consensus System */}
        <div className="glass-card">
          <h2 className="mb-4 text-xl font-semibold inline-flex items-center gap-2"><Scale size={18} aria-hidden="true" /> Agent Consensus System</h2>
          <p className="text-[var(--text-secondary)] mb-6">
            The system combines signals from all agents using weighted voting. A
            minimum of 40% confidence is required for trade execution.
          </p>

          <div className="bg-[rgba(31,41,55,0.4)] p-6 rounded-xl">
            <div className="flex justify-between items-center mb-4">
              <span className="font-semibold">Current Consensus</span>
              <span className="text-2xl font-bold text-[var(--neon-amber)]">
                {consensus.consensus}
              </span>
            </div>
            <div className="w-full h-2 bg-[rgba(100,116,139,0.2)] rounded overflow-hidden">
              <div
                className="h-full rounded transition-all duration-1000 bg-gradient-to-r from-[var(--neon-amber)] to-[var(--neon-ruby)]"
                style={{ width: `${consensus.confidence}%` }}
              />
            </div>
            <div className="flex justify-between mt-2 text-sm text-[var(--text-tertiary)]">
              <span>Confidence: {consensus.confidence.toFixed(0)}%</span>
              <span>Threshold: {consensus.threshold.toFixed(0)}%</span>
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
