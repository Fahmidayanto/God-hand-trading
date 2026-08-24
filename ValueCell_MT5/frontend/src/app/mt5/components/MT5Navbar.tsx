import { Link, useLocation } from "react-router";
import { Home, BarChart3, TrendingUp, Bot, Settings, Bell, User, Hand, Zap } from "lucide-react";

export default function MT5Navbar() {
  const location = useLocation();

  const navLinks = [
    { path: "/mt5", label: "Dashboard", icon: Home },
    { path: "/mt5/trades", label: "Trades", icon: BarChart3 },
    { path: "/mt5/performance", label: "Performance", icon: TrendingUp },
    { path: "/mt5/agents", label: "Agents", icon: Bot },
    { path: "/mt5/settings", label: "Settings", icon: Settings },
  ];

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <nav className="glass-card !mb-8 flex justify-center items-center px-8 py-5 relative">
      {/* Logo - positioned absolutely on the left */}
      <Link
        to="/mt5"
        className="absolute left-8 text-2xl font-bold text-[var(--neon-blue)] flex items-center gap-1.5"
      >
        <span className="inline-flex items-center" aria-hidden="true">
          <Hand size={20} strokeWidth={1.8} />
          <Zap size={16} strokeWidth={1.8} />
        </span>
        God Hand
      </Link>

      {/* Nav Links - centered */}
      <ul className="flex gap-6 list-none m-0 p-0">
        {navLinks.map((link) => (
          <li key={link.path}>
            <Link
              to={link.path}
              className={`text-[var(--text-secondary)] no-underline transition-all relative py-2 hover:text-[var(--neon-blue)] hover:-translate-y-0.5 inline-flex items-center gap-1.5 ${
                isActive(link.path) ? "!text-[var(--neon-blue)]" : ""
              }`}
            >
              <link.icon size={15} aria-hidden="true" />
              {link.label}
              {isActive(link.path) && (
                <span
                  className="absolute -bottom-2 left-0 w-full h-[2px] bg-[var(--neon-blue)] animate-pulse-glow"
                  style={{
                    boxShadow: "0 0 10px var(--neon-blue)",
                  }}
                />
              )}
            </Link>
          </li>
        ))}
      </ul>

      {/* User Actions - positioned absolutely on the right */}
      <div className="absolute right-8 flex gap-4 items-center">
        <button
          className="cursor-pointer hover:scale-110 transition-transform flex items-center text-[var(--text-secondary)]"
          aria-label="Notifications"
          title="Notifications"
        >
          <Bell size={17} aria-hidden="true" />
        </button>
        <button
          className="cursor-pointer hover:scale-110 transition-transform flex items-center text-[var(--text-secondary)]"
          aria-label="Profile"
          title="Profile"
        >
          <User size={17} aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}
