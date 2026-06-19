/**
 * SIDEBAR USAGE EXAMPLE
 * 
 * This file demonstrates how to integrate the Sidebar component
 * into your layout or pages.
 */

import Sidebar from "./Sidebar";

// Example 1: Basic Layout with Sidebar
export function LayoutWithSidebar({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex bg-[var(--bg-deepspace)]">
      {/* Sidebar renders both the sidebar itself and a spacer */}
      <Sidebar />
      
      {/* Main content area */}
      <main className="flex-1 p-8 transition-all duration-300">
        {children}
      </main>
    </div>
  );
}

// Example 2: Page with Sidebar and Custom Header
export function PageWithSidebarAndHeader() {
  return (
    <div className="min-h-screen flex bg-[var(--bg-deepspace)]">
      <Sidebar />
      
      <div className="flex-1 flex flex-col">
        {/* Custom Header */}
        <header className="glass-card m-4 p-4">
          <h1 className="text-2xl font-bold">Page Title</h1>
        </header>
        
        {/* Main Content */}
        <main className="flex-1 p-4">
          <div className="glass-card p-6">
            <p>Your content here</p>
          </div>
        </main>
      </div>
    </div>
  );
}

// Example 3: Responsive Grid Layout with Sidebar
export function DashboardWithSidebar() {
  return (
    <div className="min-h-screen flex bg-[var(--bg-deepspace)]">
      <Sidebar />
      
      <main className="flex-1 p-8">
        {/* Responsive Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="glass-card p-6">
              <h3 className="text-lg font-semibold mb-2">Card {i}</h3>
              <p className="text-[var(--text-secondary)]">Content here</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

// Example 4: Sidebar with Scrollable Content
export function ScrollableContentWithSidebar() {
  return (
    <div className="min-h-screen flex bg-[var(--bg-deepspace)]">
      <Sidebar />
      
      <main className="flex-1 overflow-y-auto">
        <div className="p-8 max-w-7xl mx-auto">
          {/* Long scrollable content */}
          {Array.from({ length: 20 }).map((_, i) => (
            <div key={i} className="glass-card p-6 mb-4">
              <h2 className="text-xl font-bold mb-2">Section {i + 1}</h2>
              <p className="text-[var(--text-secondary)]">
                Lorem ipsum dolor sit amet, consectetur adipiscing elit.
                Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
              </p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

/**
 * NOTES:
 * 
 * 1. The Sidebar component is self-contained and handles:
 *    - Fixed positioning (position: fixed)
 *    - Its own spacer to prevent content overlap
 *    - Collapse/expand state management
 *    - Responsive behavior
 * 
 * 2. You don't need to:
 *    - Add margin/padding to account for sidebar
 *    - Handle sidebar state in parent
 *    - Add media queries for responsive behavior
 * 
 * 3. The sidebar will automatically:
 *    - Collapse on mobile (<768px)
 *    - Show tooltips when collapsed
 *    - Highlight active routes
 *    - Maintain proper z-index
 * 
 * 4. Customization tips:
 *    - Modify nav items in Sidebar.tsx
 *    - Adjust colors via CSS variables in global.css
 *    - Change animation duration in transition properties
 *    - Add badges or notifications to nav items
 */
