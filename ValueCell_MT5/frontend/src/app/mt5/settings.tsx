import { useEffect, useState } from "react";
import Particles from "@tsparticles/react";
import MT5Footer from "./components/MT5Footer";

interface Settings {
  trading: {
    paperMode: boolean;
    riskPerTrade: number;
    maxDailyTrades: number;
    consensusThreshold: number;
    autoTrading: boolean;
  };
  mt5: {
    account: string;
    server: string;
    symbol: string;
    timeframe: string;
  };
  appearance: {
    theme: string;
    zoom: number;
    particles: boolean;
    animations: boolean;
  };
  notifications: {
    newSignals: boolean;
    tradeExecution: boolean;
    systemErrors: boolean;
    soundEffects: boolean;
  };
}

const defaultSettings: Settings = {
  trading: {
    paperMode: true,
    riskPerTrade: 1.5,
    maxDailyTrades: 10,
    consensusThreshold: 40,
    autoTrading: false,
  },
  mt5: {
    account: "108186726",
    server: "RoboForex-Pro",
    symbol: "XAUUSD",
    timeframe: "M15",
  },
  appearance: {
    theme: "dark",
    zoom: 0.67,
    particles: true,
    animations: true,
  },
  notifications: {
    newSignals: true,
    tradeExecution: true,
    systemErrors: true,
    soundEffects: false,
  },
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [activeTheme, setActiveTheme] = useState("dark");

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = () => {
    const saved = localStorage.getItem("valuecell_settings");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setSettings(parsed);
        setActiveTheme(parsed.appearance.theme);
        document.body.style.zoom = parsed.appearance.zoom.toString();
      } catch (error) {
        console.error("Error loading settings:", error);
      }
    }
  };

  const saveSettings = () => {
    localStorage.setItem("valuecell_settings", JSON.stringify(settings));
    showNotification("Settings saved successfully!", "success");
  };

  const resetSettings = () => {
    setSettings(defaultSettings);
    localStorage.setItem("valuecell_settings", JSON.stringify(defaultSettings));
    showNotification("Settings reset to defaults", "info");
    document.body.style.zoom = defaultSettings.appearance.zoom.toString();
  };

  const showNotification = (message: string, type: "success" | "error" | "info") => {
    // Simple notification (you can enhance this with a toast library)
    alert(message);
  };

  const updateSetting = (category: keyof Settings, key: string, value: any) => {
    setSettings((prev) => ({
      ...prev,
      [category]: {
        ...prev[category],
        [key]: value,
      },
    }));
  };

  const handleZoomChange = (zoom: number) => {
    updateSetting("appearance", "zoom", zoom);
    document.body.style.zoom = zoom.toString();
  };

  return (
    <div 
      style={{ 
        background: "var(--bg-deepspace)",
        minHeight: "100vh",
        width: "100%",
        position: "relative",
        overflowX: "hidden",
        overflowY: "auto"
      }}
    >
      {settings.appearance.particles && (
        <Particles
          id="tsparticles-settings"
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
      )}

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
        <div className="mb-6">
          <h1 className="text-[32px] font-bold mb-2 bg-gradient-to-r from-[var(--neon-blue)] to-[var(--neon-cyan)] bg-clip-text text-transparent">
            ⚙️ System Settings
          </h1>
          <p className="text-[var(--text-tertiary)] text-sm">
            Configure your trading system preferences and parameters
          </p>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Trading Parameters */}
          <div className="glass-card">
            <h2 className="mb-5 text-xl font-semibold">💼 Trading Parameters</h2>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="flex justify-between items-center mb-2">
                <div>
                  <div className="text-[15px] font-semibold text-[var(--text-primary)]">
                    Paper Trading Mode
                  </div>
                  <div className="text-sm text-[var(--text-tertiary)]">
                    Enable to simulate trades without real money
                  </div>
                </div>
                <label className="relative w-[50px] h-[26px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.trading.paperMode}
                    onChange={(e) =>
                      updateSetting("trading", "paperMode", e.target.checked)
                    }
                    className="opacity-0 w-0 h-0"
                  />
                  <span className="absolute top-0 left-0 right-0 bottom-0 bg-[rgba(100,116,139,0.3)] rounded-[26px] transition-all before:absolute before:content-[''] before:h-[18px] before:w-[18px] before:left-1 before:bottom-1 before:bg-white before:rounded-full before:transition-all peer-checked:bg-[var(--neon-blue)] peer-checked:before:translate-x-6" />
                </label>
              </div>
            </div>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">
                Risk Per Trade
              </div>
              <input
                type="number"
                value={settings.trading.riskPerTrade}
                onChange={(e) =>
                  updateSetting("trading", "riskPerTrade", parseFloat(e.target.value))
                }
                step="0.1"
                min="0.1"
                max="5.0"
                className="w-full px-4 py-3 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-[10px] text-[var(--text-primary)] text-sm mono transition-all focus:outline-none focus:border-[var(--neon-blue)] focus:shadow-[0_0_20px_rgba(59,130,246,0.3)]"
              />
              <div className="text-sm text-[var(--text-tertiary)] mt-2">
                Percentage of account to risk per trade (0.1% - 5.0%)
              </div>
            </div>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">
                Max Daily Trades
              </div>
              <input
                type="number"
                value={settings.trading.maxDailyTrades}
                onChange={(e) =>
                  updateSetting("trading", "maxDailyTrades", parseInt(e.target.value))
                }
                min="1"
                max="50"
                className="w-full px-4 py-3 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-[10px] text-[var(--text-primary)] text-sm mono transition-all focus:outline-none focus:border-[var(--neon-blue)]"
              />
              <div className="text-sm text-[var(--text-tertiary)] mt-2">
                Maximum number of trades per day
              </div>
            </div>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">
                Consensus Threshold
              </div>
              <input
                type="number"
                value={settings.trading.consensusThreshold}
                onChange={(e) =>
                  updateSetting("trading", "consensusThreshold", parseInt(e.target.value))
                }
                min="0"
                max="100"
                className="w-full px-4 py-3 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-[10px] text-[var(--text-primary)] text-sm mono transition-all focus:outline-none focus:border-[var(--neon-blue)]"
              />
              <div className="text-sm text-[var(--text-tertiary)] mt-2">
                Minimum confidence percentage required (0-100%)
              </div>
            </div>

            <div className="py-5">
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-[15px] font-semibold text-[var(--text-primary)]">
                    Auto Trading
                  </div>
                  <div className="text-sm text-[var(--text-tertiary)]">
                    Automatically execute trades when signals meet criteria
                  </div>
                </div>
                <label className="relative w-[50px] h-[26px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.trading.autoTrading}
                    onChange={(e) =>
                      updateSetting("trading", "autoTrading", e.target.checked)
                    }
                    className="opacity-0 w-0 h-0"
                  />
                  <span className="absolute top-0 left-0 right-0 bottom-0 bg-[rgba(100,116,139,0.3)] rounded-[26px] transition-all before:absolute before:content-[''] before:h-[18px] before:w-[18px] before:left-1 before:bottom-1 before:bg-white before:rounded-full before:transition-all peer-checked:bg-[var(--neon-blue)] peer-checked:before:translate-x-6" />
                </label>
              </div>
            </div>
          </div>

          {/* MT5 Configuration */}
          <div className="glass-card">
            <h2 className="mb-5 text-xl font-semibold">🔌 MT5 Connection</h2>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">
                Account Number
              </div>
              <input
                type="text"
                value={settings.mt5.account}
                readOnly
                className="w-full px-4 py-3 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-[10px] text-[var(--text-primary)] text-sm mono opacity-70"
              />
              <div className="text-sm text-[var(--text-tertiary)] mt-2">
                MetaTrader 5 account number
              </div>
            </div>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">
                Broker Server
              </div>
              <select
                value={settings.mt5.server}
                onChange={(e) => updateSetting("mt5", "server", e.target.value)}
                className="w-full px-4 py-3 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-[10px] text-[var(--text-primary)] text-sm cursor-pointer transition-all focus:outline-none focus:border-[var(--neon-blue)]"
              >
                <option>RoboForex-Pro</option>
                <option>RoboForex-Demo</option>
                <option>IC Markets-Live</option>
                <option>Exness-Real</option>
              </select>
            </div>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">
                Default Symbol
              </div>
              <select
                value={settings.mt5.symbol}
                onChange={(e) => updateSetting("mt5", "symbol", e.target.value)}
                className="w-full px-4 py-3 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-[10px] text-[var(--text-primary)] text-sm cursor-pointer transition-all focus:outline-none focus:border-[var(--neon-blue)]"
              >
                <option>XAUUSD (Gold)</option>
                <option>EURUSD</option>
                <option>GBPUSD</option>
                <option>USDJPY</option>
              </select>
            </div>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">
                Default Timeframe
              </div>
              <select
                value={settings.mt5.timeframe}
                onChange={(e) => updateSetting("mt5", "timeframe", e.target.value)}
                className="w-full px-4 py-3 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-[10px] text-[var(--text-primary)] text-sm cursor-pointer transition-all focus:outline-none focus:border-[var(--neon-blue)]"
              >
                <option>M1 (1 minute)</option>
                <option>M5 (5 minutes)</option>
                <option>M15 (15 minutes)</option>
                <option>M30 (30 minutes)</option>
                <option>H1 (1 hour)</option>
                <option>H4 (4 hours)</option>
                <option>D1 (Daily)</option>
              </select>
            </div>

            <div className="flex gap-3 mt-5">
              <button className="flex-1 px-6 py-3 bg-[var(--neon-blue)] border border-[var(--neon-blue)] text-white rounded-[10px] text-sm font-semibold transition-all hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(59,130,246,0.3)]">
                Test Connection
              </button>
              <button className="flex-1 px-6 py-3 bg-[var(--glass-secondary)] border border-[var(--glass-border)] text-[var(--text-primary)] rounded-[10px] text-sm font-semibold transition-all hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(59,130,246,0.3)]">
                Reconnect
              </button>
            </div>
          </div>

          {/* Appearance */}
          <div className="glass-card">
            <h2 className="mb-5 text-xl font-semibold">🎨 Appearance</h2>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">
                Theme
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { name: "Dark", value: "dark", gradient: "from-[#0a0e27] to-[#111827]" },
                  { name: "Light", value: "light", gradient: "from-[#f0f4f8] to-[#e0e7ee]" },
                  { name: "Midnight", value: "midnight", gradient: "from-[#000000] to-[#1a1a2e]" },
                ].map((theme) => (
                  <div
                    key={theme.value}
                    onClick={() => {
                      setActiveTheme(theme.value);
                      updateSetting("appearance", "theme", theme.value);
                    }}
                    className={`p-4 border-2 rounded-[10px] text-center cursor-pointer transition-all hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(0,0,0,0.3)] ${
                      activeTheme === theme.value
                        ? "border-[var(--neon-blue)] bg-[rgba(59,130,246,0.1)]"
                        : "border-[var(--glass-border)]"
                    }`}
                  >
                    <div
                      className={`w-full h-[60px] rounded-lg mb-2 bg-gradient-to-br ${theme.gradient}`}
                    />
                    <div className="text-sm font-semibold">{theme.name}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">
                UI Zoom Level
              </div>
              <select
                value={settings.appearance.zoom}
                onChange={(e) => handleZoomChange(parseFloat(e.target.value))}
                className="w-full px-4 py-3 bg-[var(--glass-secondary)] border border-[var(--glass-border)] rounded-[10px] text-[var(--text-primary)] text-sm cursor-pointer transition-all focus:outline-none focus:border-[var(--neon-blue)]"
              >
                <option value="0.5">50%</option>
                <option value="0.67">67% (Default)</option>
                <option value="0.75">75%</option>
                <option value="0.8">80%</option>
                <option value="1.0">100%</option>
              </select>
            </div>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-[15px] font-semibold text-[var(--text-primary)]">
                    3D Particles
                  </div>
                  <div className="text-sm text-[var(--text-tertiary)]">
                    Show animated background particles
                  </div>
                </div>
                <label className="relative w-[50px] h-[26px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.appearance.particles}
                    onChange={(e) =>
                      updateSetting("appearance", "particles", e.target.checked)
                    }
                    className="opacity-0 w-0 h-0"
                  />
                  <span className="absolute top-0 left-0 right-0 bottom-0 bg-[rgba(100,116,139,0.3)] rounded-[26px] transition-all before:absolute before:content-[''] before:h-[18px] before:w-[18px] before:left-1 before:bottom-1 before:bg-white before:rounded-full before:transition-all peer-checked:bg-[var(--neon-blue)] peer-checked:before:translate-x-6" />
                </label>
              </div>
            </div>

            <div className="py-5">
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-[15px] font-semibold text-[var(--text-primary)]">
                    Animations
                  </div>
                  <div className="text-sm text-[var(--text-tertiary)]">
                    Enable smooth transitions and animations
                  </div>
                </div>
                <label className="relative w-[50px] h-[26px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.appearance.animations}
                    onChange={(e) =>
                      updateSetting("appearance", "animations", e.target.checked)
                    }
                    className="opacity-0 w-0 h-0"
                  />
                  <span className="absolute top-0 left-0 right-0 bottom-0 bg-[rgba(100,116,139,0.3)] rounded-[26px] transition-all before:absolute before:content-[''] before:h-[18px] before:w-[18px] before:left-1 before:bottom-1 before:bg-white before:rounded-full before:transition-all peer-checked:bg-[var(--neon-blue)] peer-checked:before:translate-x-6" />
                </label>
              </div>
            </div>
          </div>

          {/* Notifications */}
          <div className="glass-card">
            <h2 className="mb-5 text-xl font-semibold">🔔 Notifications</h2>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-[15px] font-semibold text-[var(--text-primary)]">
                    New Signal Alerts
                  </div>
                  <div className="text-sm text-[var(--text-tertiary)]">
                    Notify when new trading signals are detected
                  </div>
                </div>
                <label className="relative w-[50px] h-[26px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notifications.newSignals}
                    onChange={(e) =>
                      updateSetting("notifications", "newSignals", e.target.checked)
                    }
                    className="opacity-0 w-0 h-0"
                  />
                  <span className="absolute top-0 left-0 right-0 bottom-0 bg-[rgba(100,116,139,0.3)] rounded-[26px] transition-all before:absolute before:content-[''] before:h-[18px] before:w-[18px] before:left-1 before:bottom-1 before:bg-white before:rounded-full before:transition-all peer-checked:bg-[var(--neon-blue)] peer-checked:before:translate-x-6" />
                </label>
              </div>
            </div>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-[15px] font-semibold text-[var(--text-primary)]">
                    Trade Execution
                  </div>
                  <div className="text-sm text-[var(--text-tertiary)]">
                    Notify when trades are opened or closed
                  </div>
                </div>
                <label className="relative w-[50px] h-[26px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notifications.tradeExecution}
                    onChange={(e) =>
                      updateSetting("notifications", "tradeExecution", e.target.checked)
                    }
                    className="opacity-0 w-0 h-0"
                  />
                  <span className="absolute top-0 left-0 right-0 bottom-0 bg-[rgba(100,116,139,0.3)] rounded-[26px] transition-all before:absolute before:content-[''] before:h-[18px] before:w-[18px] before:left-1 before:bottom-1 before:bg-white before:rounded-full before:transition-all peer-checked:bg-[var(--neon-blue)] peer-checked:before:translate-x-6" />
                </label>
              </div>
            </div>

            <div className="py-5 border-b border-[rgba(100,116,139,0.1)]">
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-[15px] font-semibold text-[var(--text-primary)]">
                    System Errors
                  </div>
                  <div className="text-sm text-[var(--text-tertiary)]">
                    Notify when system errors occur
                  </div>
                </div>
                <label className="relative w-[50px] h-[26px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notifications.systemErrors}
                    onChange={(e) =>
                      updateSetting("notifications", "systemErrors", e.target.checked)
                    }
                    className="opacity-0 w-0 h-0"
                  />
                  <span className="absolute top-0 left-0 right-0 bottom-0 bg-[rgba(100,116,139,0.3)] rounded-[26px] transition-all before:absolute before:content-[''] before:h-[18px] before:w-[18px] before:left-1 before:bottom-1 before:bg-white before:rounded-full before:transition-all peer-checked:bg-[var(--neon-blue)] peer-checked:before:translate-x-6" />
                </label>
              </div>
            </div>

            <div className="py-5">
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-[15px] font-semibold text-[var(--text-primary)]">
                    Sound Effects
                  </div>
                  <div className="text-sm text-[var(--text-tertiary)]">
                    Play sounds for important notifications
                  </div>
                </div>
                <label className="relative w-[50px] h-[26px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notifications.soundEffects}
                    onChange={(e) =>
                      updateSetting("notifications", "soundEffects", e.target.checked)
                    }
                    className="opacity-0 w-0 h-0"
                  />
                  <span className="absolute top-0 left-0 right-0 bottom-0 bg-[rgba(100,116,139,0.3)] rounded-[26px] transition-all before:absolute before:content-[''] before:h-[18px] before:w-[18px] before:left-1 before:bottom-1 before:bg-white before:rounded-full before:transition-all peer-checked:bg-[var(--neon-blue)] peer-checked:before:translate-x-6" />
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="glass-card mt-6">
          <div className="flex gap-4 justify-end">
            <button
              onClick={resetSettings}
              className="px-6 py-3 bg-[var(--glass-secondary)] border border-[var(--glass-border)] text-[var(--text-primary)] rounded-[10px] text-sm font-semibold transition-all hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(59,130,246,0.3)]"
            >
              Reset to Defaults
            </button>
            <button className="px-6 py-3 bg-[var(--glass-secondary)] border border-[var(--glass-border)] text-[var(--text-primary)] rounded-[10px] text-sm font-semibold transition-all hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(59,130,246,0.3)]">
              Cancel
            </button>
            <button
              onClick={saveSettings}
              className="px-6 py-3 bg-[var(--neon-blue)] border border-[var(--neon-blue)] text-white rounded-[10px] text-sm font-semibold transition-all hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(59,130,246,0.3)]"
            >
              Save Changes
            </button>
          </div>
        </div>

        {/* Danger Zone */}
        <div className="glass-card mt-6 !border-[rgba(239,68,68,0.3)]">
          <h2 className="mb-4 text-xl font-semibold text-[var(--neon-ruby)]">
            ⚠️ Danger Zone
          </h2>
          <div className="flex justify-between items-center">
            <div>
              <div className="font-semibold mb-1">Reset All Settings</div>
              <div className="text-sm text-[var(--text-tertiary)]">
                Clear all configuration and restore defaults
              </div>
            </div>
            <button
              onClick={resetSettings}
              className="px-6 py-3 bg-[var(--neon-ruby)] border border-[var(--neon-ruby)] text-white rounded-[10px] text-sm font-semibold transition-all hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(239,68,68,0.3)]"
            >
              Reset System
            </button>
          </div>
        </div>

        {/* Footer */}
        <MT5Footer />
        </div>
      </div>
    </div>
  );
}
