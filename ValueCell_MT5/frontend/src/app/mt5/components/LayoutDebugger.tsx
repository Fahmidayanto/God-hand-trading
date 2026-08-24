import { useState } from "react";
import { Search } from "lucide-react";

export default function LayoutDebugger() {
  const [isEnabled, setIsEnabled] = useState(true);

  if (!isEnabled) return null;

  return (
    <>
      {/* Toggle Button */}
      <button
        onClick={() => setIsEnabled(!isEnabled)}
        className="fixed top-4 right-4 z-[100] px-4 py-2 bg-purple-600 text-white rounded-lg shadow-lg hover:bg-purple-700 transition-all text-sm font-semibold"
        title="Toggle Layout Debugger"
      >
         <Search size={13} className="inline mr-1.5 -mt-0.5" aria-hidden="true" />Layout Debug
      </button>

      {/* CSS for visual debugging */}
      <style>{`
        /* Debug borders and labels */
        .debug-overlay {
          position: relative;
        }
        
        .debug-overlay::before {
          content: attr(data-label);
          position: absolute;
          top: 0;
          left: 0;
          background: rgba(139, 92, 246, 0.9);
          color: white;
          padding: 4px 8px;
          font-size: 11px;
          font-weight: 600;
          border-radius: 4px;
          z-index: 999;
          pointer-events: none;
          white-space: nowrap;
          box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        
        .debug-overlay:hover::before {
          background: rgba(168, 85, 247, 1);
          transform: scale(1.1);
        }
        
        /* Sidebar debug */
        .debug-sidebar {
          outline: 3px solid rgba(59, 130, 246, 0.8) !important;
          outline-offset: -3px;
        }
        
        /* Main container debug */
        .debug-main-container {
          outline: 3px solid rgba(16, 185, 129, 0.8) !important;
          outline-offset: -3px;
        }
        
        /* Content wrapper debug */
        .debug-content-wrapper {
          outline: 3px solid rgba(251, 191, 36, 0.8) !important;
          outline-offset: -3px;
        }
        
        /* Header debug */
        .debug-header {
          outline: 2px solid rgba(139, 92, 246, 0.7) !important;
          outline-offset: -2px;
        }
        
        /* Stats grid debug */
        .debug-stats-grid {
          outline: 2px solid rgba(236, 72, 153, 0.7) !important;
          outline-offset: -2px;
        }
        
        /* Stats card debug */
        .debug-stats-card {
          outline: 2px dashed rgba(236, 72, 153, 0.5) !important;
          outline-offset: -2px;
        }
        
        /* Chart section debug */
        .debug-chart-section {
          outline: 2px solid rgba(34, 197, 94, 0.7) !important;
          outline-offset: -2px;
        }
        
        /* Table section debug */
        .debug-table-section {
          outline: 2px solid rgba(249, 115, 22, 0.7) !important;
          outline-offset: -2px;
        }
        
        /* Footer debug */
        .debug-footer {
          outline: 2px solid rgba(239, 68, 68, 0.7) !important;
          outline-offset: -2px;
        }
        
        /* Particles debug */
        .debug-particles {
          outline: 2px dashed rgba(100, 116, 139, 0.5) !important;
          outline-offset: -2px;
        }
        
        /* Gradient overlay debug */
        .debug-gradient {
          outline: 2px dashed rgba(100, 116, 139, 0.5) !important;
          outline-offset: -2px;
        }
      `}</style>
    </>
  );
}

// Hook to add debug classes
export function useDebugLayout() {
  return {
    sidebar: "debug-sidebar debug-overlay",
    mainContainer: "debug-main-container debug-overlay",
    contentWrapper: "debug-content-wrapper debug-overlay",
    header: "debug-header debug-overlay",
    statsGrid: "debug-stats-grid debug-overlay",
    statsCard: "debug-stats-card debug-overlay",
    chartSection: "debug-chart-section debug-overlay",
    tableSection: "debug-table-section debug-overlay",
    footer: "debug-footer debug-overlay",
    particles: "debug-particles debug-overlay",
    gradient: "debug-gradient debug-overlay",
  };
}
