import { useLocation } from "react-router";
import { useState, useEffect } from "react";
import MT5Sidebar from "./components/MT5Sidebar";
import Dashboard from "./dashboard";
import Trades from "./trades";
import Performance from "./performance";
import Agents from "./agents";
import Settings from "./settings";

const pages = [
  { path: "/mt5", Component: Dashboard },
  { path: "/mt5/trades", Component: Trades },
  { path: "/mt5/performance", Component: Performance },
  { path: "/mt5/agents", Component: Agents },
  { path: "/mt5/settings", Component: Settings },
];

export default function MT5Layout() {
  const location = useLocation();
  const [mounted, setMounted] = useState(new Set(["/mt5"]));

  useEffect(() => {
    setMounted(prev => new Set(prev).add(location.pathname));
  }, [location.pathname]);

  return (
    <div className="flex size-full overflow-hidden">
      <MT5Sidebar />
      <div className="relative flex-1">
        {pages.map(({ path, Component }) =>
          mounted.has(path) ? (
            <div
              key={path}
              className="size-full overflow-auto"
              style={{ display: location.pathname === path ? "" : "none" }}
            >
              <Component />
            </div>
          ) : null
        )}
      </div>
    </div>
  );
}
