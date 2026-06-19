import { Link, useLocation } from "react-router";

export default function MT5Sidebar() {
  const location = useLocation();

  const navLinks = [
    { path: "/mt5", label: "Dashboard", icon: "🏠" },
    { path: "/mt5/trades", label: "Trades", icon: "📊" },
    { path: "/mt5/performance", label: "Performance", icon: "📈" },
    { path: "/mt5/agents", label: "Agents", icon: "🤖" },
    { path: "/mt5/settings", label: "Settings", icon: "⚙️" },
  ];

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <aside 
      className="glass-card fixed z-50 flex flex-col hover:border-[rgba(59,130,246,0.4)] hover:shadow-[0_8px_32px_rgba(59,130,246,0.2)] transition-all"
      style={{
        left: 5,
        top: 5,
        bottom: 0,
        width: "240px",
        height: "148vh",
        overflowY: "auto",
        padding: "24px 16px"
      }}
    >
      {/* Logo */}
      <Link
        to="/mt5"
        className="mb-8 text-xl font-bold bg-gradient-to-r from-[var(--neon-blue)] to-[var(--neon-purple)] bg-clip-text text-transparent text-center block"
      >
        ✋⚡ God Hand
      </Link>

      {/* Nav Links - vertical, fills available space */}
      <nav className="flex-1 flex flex-col">
        <ul className="flex flex-col gap-2 list-none m-0 p-0">
          {navLinks.map((link) => (
            <li key={link.path}>
              <Link
                to={link.path}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg text-[var(--text-secondary)] no-underline transition-all hover:bg-[rgba(59,130,246,0.1)] hover:text-[var(--neon-blue)] hover:translate-x-1 ${
                  isActive(link.path) 
                    ? "!text-[var(--neon-blue)] !bg-[rgba(59,130,246,0.15)] border-l-2 border-[var(--neon-blue)]" 
                    : ""
                }`}
                style={{
                  borderLeft: isActive(link.path) ? "" : "2px solid transparent"
                }}
              >
                <span className="text-xl">{link.icon}</span>
                <span className="text-sm font-medium">{link.label}</span>
              </Link>
            </li>
          ))}
        </ul>
        
        {/* Spacer to push user actions to bottom */}
        <div className="flex-1"></div>
      </nav>

      {/* User Actions - bottom */}
      <div className="mt-6 pt-6 border-t border-[rgba(100,116,139,0.2)] flex justify-around items-center flex-shrink-0">
        <button 
          className="text-2xl cursor-pointer hover:scale-110 transition-transform"
          title="Notifications"
        >
          🔔
        </button>
        <button 
          className="text-2xl cursor-pointer hover:scale-110 transition-transform"
          title="Profile"
        >
          👤
        </button>
      </div>
    </aside>
  );
}
