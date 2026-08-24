import { useState, useEffect, useRef } from "react";
import { RotateCcw, MousePointer2 } from "lucide-react";
import GridLayout, { Layout } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

interface DraggableLayoutProps {
  children: React.ReactNode[];
  layoutKey?: string;
}

const defaultLayouts: Layout[] = [
  { i: "chart", x: 0, y: 0, w: 8, h: 6, minW: 4, minH: 4 },
  { i: "trades", x: 8, y: 0, w: 4, h: 6, minW: 3, minH: 4 },
];

export default function DraggableLayout({ 
  children, 
  layoutKey = "mt5-trades-layout" 
}: DraggableLayoutProps) {
  const [layouts, setLayouts] = useState<Layout[]>(defaultLayouts);
  const [isDraggable, setIsDraggable] = useState(false);
  const [width, setWidth] = useState(1200);
  const containerRef = useRef<HTMLDivElement>(null);

  // Measure container width
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setWidth(containerRef.current.offsetWidth);
      }
    };
    
    updateWidth();
    window.addEventListener("resize", updateWidth);
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  // Load saved layout
  useEffect(() => {
    const saved = localStorage.getItem(layoutKey);
    if (saved) {
      try {
        setLayouts(JSON.parse(saved));
      } catch (error) {
        console.error("Failed to load layout:", error);
      }
    }
  }, [layoutKey]);

  // Save layout
  const handleLayoutChange = (newLayout: Layout[]) => {
    if (isDraggable) {
      setLayouts(newLayout);
      localStorage.setItem(layoutKey, JSON.stringify(newLayout));
    }
  };

  // Reset layout
  const resetLayout = () => {
    setLayouts(defaultLayouts);
    localStorage.removeItem(layoutKey);
  };

  return (
    <div ref={containerRef} className="relative w-full">
      {/* Control Panel */}
      <div className="fixed top-20 right-6 z-[60] flex gap-2">
        <button
          onClick={() => setIsDraggable(!isDraggable)}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all shadow-lg ${
            isDraggable
              ? "bg-[var(--neon-blue)] text-white shadow-[0_0_20px_rgba(59,130,246,0.4)]"
              : "bg-[var(--glass-secondary)] text-[var(--text-primary)] border border-[var(--glass-border)]"
          }`}
        >
          {isDraggable ? "Edit Mode" : "Lock Layout"}
        </button>
        
        {isDraggable && (
          <button
            onClick={resetLayout}
            className="px-4 py-2 bg-[var(--neon-ruby)] text-white rounded-lg text-sm font-semibold transition-all"
          >
            <RotateCcw size={13} className="inline mr-1 -mt-px" aria-hidden="true" />Reset
          </button>
        )}
      </div>

      {/* Drag Hint */}
      {isDraggable && (
        <div className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 pointer-events-none z-[55]">
          <div className="bg-[rgba(59,130,246,0.95)] text-white px-6 py-3 rounded-lg shadow-2xl animate-pulse text-center">
            <div className="text-lg font-semibold mb-1"><MousePointer2 size={16} className="inline mr-1.5 -mt-0.5" aria-hidden="true" />Edit Mode Active</div>
            <div className="text-sm">Drag headers (⋮⋮) to rearrange • Drag corners to resize</div>
          </div>
        </div>
      )}

      {/* Grid Layout */}
      <GridLayout
        className="layout"
        layout={layouts}
        cols={12}
        rowHeight={80}
        width={width}
        isDraggable={isDraggable}
        isResizable={isDraggable}
        onLayoutChange={handleLayoutChange}
        draggableHandle=".drag-handle"
        compactType={null}
        preventCollision={false}
        margin={[24, 24]}
        containerPadding={[0, 0]}
      >
        {children}
      </GridLayout>

      {/* Styles */}
      <style>{`
        .react-grid-layout {
          position: relative;
        }
        
        .react-grid-item {
          transition: all 200ms ease;
          transition-property: left, top, width, height;
        }
        
        .react-grid-item.cssTransforms {
          transition-property: transform, width, height;
        }
        
        .react-grid-item.react-grid-placeholder {
          background: rgba(59, 130, 246, 0.3);
          border: 2px dashed var(--neon-blue);
          border-radius: 16px;
          z-index: 2;
          opacity: 0.5;
        }
        
        .react-grid-item > .react-resizable-handle {
          position: absolute;
          width: 20px;
          height: 20px;
        }
        
        .react-grid-item > .react-resizable-handle::after {
          content: "⋰";
          position: absolute;
          right: 3px;
          bottom: 3px;
          width: 16px;
          height: 16px;
          color: var(--neon-blue);
          font-size: 20px;
          font-weight: bold;
        }
        
        .react-grid-item.react-draggable-dragging {
          z-index: 100;
          opacity: 0.8;
          box-shadow: 0 12px 32px rgba(59, 130, 246, 0.5) !important;
        }
        
        .react-grid-item.resizing {
          opacity: 0.9;
          z-index: 100;
        }
        
        .drag-handle {
          cursor: move !important;
          user-select: none;
        }
        
        .drag-handle:hover {
          background: rgba(59, 130, 246, 0.1);
        }
        
        .drag-handle:active {
          cursor: grabbing !important;
        }
      `}</style>
    </div>
  );
}
