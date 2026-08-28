import { useLocation } from "react-router";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import MT5Sidebar from "./components/MT5Sidebar";
import Dashboard from "./dashboard";
import Trades from "./trades";
import Rongsokan from "./rongsokan";
import Performance from "./performance";
import Agents from "./agents";
import Settings from "./settings";
import Database from "./database";
import ReplayTrades from "./replay";
import ReplayOriginal from "./replay-original";
import SimulationOfDead from "./simulation";

const pages = [
  { path: "/mt5", Component: Dashboard },
  { path: "/mt5/trades", Component: Trades },
  { path: "/mt5/rongsokan", Component: Rongsokan },
  { path: "/mt5/performance", Component: Performance },
  { path: "/mt5/agents", Component: Agents },
  { path: "/mt5/settings", Component: Settings },
  { path: "/mt5/database", Component: Database },
  { path: "/mt5/replay", Component: ReplayTrades },
  { path: "/mt5/replay-original", Component: ReplayOriginal },
  { path: "/mt5/simulation", Component: SimulationOfDead },
];

// Ultra-Smooth Micro-Fade Transition (Performance Optimized)
const pageTransition = {
  duration: 0.2,
  ease: [0.22, 1, 0.36, 1] as const,
};

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
              {location.pathname === path ? (
                <motion.div
                  key={location.pathname}
                  initial={{
                    opacity: 0,
                    y: 4,
                  }}
                  animate={{
                    opacity: 1,
                    y: 0,
                  }}
                  transition={pageTransition}
                  className="size-full"
                >
                  <Component />
                </motion.div>
              ) : (
                <Component />
              )}
            </div>
          ) : null
        )}
      </div>
    </div>
  );
}
