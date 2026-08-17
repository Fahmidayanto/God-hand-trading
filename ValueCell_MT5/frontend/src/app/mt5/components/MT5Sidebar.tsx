import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router";
import { ChevronLeft, ChevronRight, Zap } from "lucide-react";

export default function MT5Sidebar() {
  const location = useLocation();

  // Load initial collapsed state from localStorage
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("mt5_sidebar_collapsed") === "true";
    }
    return false;
  });

  // Sync collapsed state with CSS Variables and localStorage
  useEffect(() => {
    const sidebarWidth = collapsed ? "70px" : "240px";
    const sidebarOffset = collapsed ? "80px" : "250px";

    document.documentElement.style.setProperty("--sidebar-w", sidebarWidth);
    document.documentElement.style.setProperty("--sidebar-offset", sidebarOffset);
    localStorage.setItem("mt5_sidebar_collapsed", String(collapsed));

    // Dispatch resize event so charts can re-fit container width
    window.dispatchEvent(new Event("resize"));
  }, [collapsed]);

  const navLinks = [
    { path: "/mt5", label: "Dashboard", icon: "🏠" },
    { path: "/mt5/trades", label: "Trades", icon: "📊" },
    { path: "/mt5/rongsokan", label: "Rongsokan", icon: "🔋" },
    { path: "/mt5/performance", label: "Performance", icon: "📈" },
    { path: "/mt5/agents", label: "Agents", icon: "🤖" },
    { path: "/mt5/settings", label: "Settings", icon: "⚙️" },
    { path: "/mt5/database", label: "DB Inspector", icon: "💾" },
    { path: "/mt5/replay", label: "Replay Trades", icon: "🎬" },
    { path: "/mt5/replay-original", label: "Replay Original", icon: "📜" },
    { path: "/mt5/simulation", label: "Ghost Engine", icon: "👻" },
  ];

  const isActive = (path: string) => location.pathname === path;

  return (
    <aside
      className="glass-card fixed z-50 flex flex-col mt5-sidebar transition-all duration-300 [transition-timing-function:cubic-bezier(0.22,1,0.36,1)]"
      style={{
        left: 5,
        top: 5,
        bottom: 0,
        width: collapsed ? "70px" : "240px",
        overflowY: "auto",
        padding: collapsed ? "20px 8px" : "24px 16px",
      }}
    >
      {/* Header Bar with Logo and Toggle Button */}
      {collapsed ? (
        <div className="flex flex-col items-center gap-3 mb-6 pb-4 border-b border-slate-800/80">
          <Link
            to="/mt5"
            className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500/20 via-amber-500/10 to-amber-950/40 border border-amber-500/30 flex items-center justify-center shadow-[0_0_15px_rgba(245,158,11,0.2)] hover:border-amber-400/60 hover:shadow-[0_0_20px_rgba(245,158,11,0.4)] hover:scale-105 active:scale-95 transition-all duration-200 relative group"
            title="God Hand Trading Bot"
          >
            <Zap className="w-5 h-5 text-amber-400 fill-amber-400/40 drop-shadow-[0_0_8px_rgba(245,158,11,0.6)] group-hover:scale-115 transition-transform duration-200" />
            <span className="absolute -bottom-0.5 -right-0.5 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500 border border-slate-950" />
            </span>
          </Link>

          {/* Toggle Expand Button */}
          <button
            onClick={() => setCollapsed(false)}
            className="w-7 h-7 rounded-lg bg-slate-900/80 hover:bg-slate-800 text-slate-400 hover:text-amber-300 border border-slate-700/60 hover:border-slate-600 hover:scale-110 active:scale-90 hover:rotate-6 transition-all duration-200 cursor-pointer flex items-center justify-center shadow-sm"
            title="Expand Sidebar"
            aria-label="Expand Sidebar"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      ) : (
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-800/80">
          <Link
            to="/mt5"
            className="flex items-center gap-3 no-underline group min-w-0"
            title="God Hand Trading Bot"
          >
            {/* Glass Logo Emblem */}
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-500/20 via-amber-500/10 to-amber-950/40 border border-amber-500/30 flex items-center justify-center flex-shrink-0 shadow-[0_0_15px_rgba(245,158,11,0.2)] group-hover:border-amber-400/60 group-hover:shadow-[0_0_20px_rgba(245,158,11,0.35)] group-hover:scale-105 active:scale-95 transition-all duration-200">
              <Zap className="w-5 h-5 text-amber-400 fill-amber-400/40 drop-shadow-[0_0_8px_rgba(245,158,11,0.6)] group-hover:scale-115 transition-transform duration-200" />
            </div>

            {/* Typography */}
            <div className="flex flex-col min-w-0 animate-sidebar-fade">
              <span className="font-black text-sm tracking-wider bg-gradient-to-r from-amber-200 via-amber-400 to-amber-500 bg-clip-text text-transparent group-hover:brightness-110 transition-all font-sans uppercase">
                GOD HAND
              </span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="flex h-1.5 w-1.5 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500 shadow-[0_0_6px_rgba(52,211,153,0.8)]" />
                </span>
                <span className="text-[9px] font-mono tracking-widest text-amber-400/80 uppercase font-semibold">
                  MT5 ALGO
                </span>
              </div>
            </div>
          </Link>

          {/* Toggle Collapse Button */}
          <button
            onClick={() => setCollapsed(true)}
            className="p-1.5 rounded-lg bg-slate-900/80 hover:bg-slate-800 text-slate-400 hover:text-amber-300 border border-slate-700/60 hover:border-slate-600 hover:scale-110 active:scale-90 hover:-rotate-6 transition-all duration-200 cursor-pointer flex items-center justify-center shadow-sm flex-shrink-0"
            title="Collapse Sidebar"
            aria-label="Collapse Sidebar"
          >
            <ChevronLeft size={15} />
          </button>
        </div>
      )}

      {/* Nav Links */}
      <nav className="flex-1 flex flex-col">
        <ul className="flex flex-col gap-2 list-none m-0 p-0">
          {navLinks.map((link) => {
            const active = isActive(link.path);
            return (
              <li key={link.path}>
                <Link
                  to={link.path}
                  title={collapsed ? link.label : undefined}
                  className={`group flex items-center gap-3 py-3 rounded-lg text-[var(--text-secondary)] no-underline transition-all duration-200 [transition-timing-function:cubic-bezier(0.22,1,0.36,1)] hover:bg-[rgba(var(--neon-blue-rgb),0.1)] hover:text-[var(--neon-blue)] active:scale-[0.98] ${
                    collapsed ? "justify-center px-0" : "px-4 hover:translate-x-1.5"
                  } ${
                    active
                      ? "!text-[var(--neon-blue)] !bg-[rgba(var(--neon-blue-rgb),0.15)] border-l-2 border-[var(--neon-blue)] shadow-[inset_0_0_12px_rgba(245,158,11,0.08)]"
                      : ""
                  }`}
                  style={{
                    borderLeft: active ? "" : "2px solid transparent",
                  }}
                >
                  <span className="text-xl flex-shrink-0 group-hover:scale-115 group-active:scale-90 transition-transform duration-200 ease-out">
                    {link.icon}
                  </span>
                  {!collapsed && (
                    <span className="text-sm font-medium whitespace-nowrap overflow-hidden text-ellipsis animate-sidebar-fade">
                      {link.label}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>

        {/* Spacer */}
        <div className="flex-1"></div>
      </nav>

      {/* User Actions */}
      <div
        className={`mt-4 pt-4 border-t border-[rgba(100,116,139,0.2)] flex items-center flex-shrink-0 ${
          collapsed ? "flex-col gap-3" : "justify-around"
        }`}
      >
        <button
          className="text-xl cursor-pointer hover:scale-125 hover:-translate-y-0.5 active:scale-90 transition-all duration-200 ease-out"
          title="Notifications"
        >
          🔔
        </button>
        <button
          className="text-xl cursor-pointer hover:scale-125 hover:-translate-y-0.5 active:scale-90 transition-all duration-200 ease-out"
          title="Profile"
        >
          👤
        </button>
      </div>
    </aside>
  );
}
