# Sidebar Advanced Customization Guide

## Table of Contents
1. [Adding Badge Notifications](#adding-badge-notifications)
2. [Nested Sub-Menus](#nested-sub-menus)
3. [Keyboard Shortcuts](#keyboard-shortcuts)
4. [LocalStorage Persistence](#localstorage-persistence)
5. [Theme Integration](#theme-integration)
6. [Animation Variants](#animation-variants)
7. [Custom Icons](#custom-icons)

---

## Adding Badge Notifications

Add notification badges to navigation items:

```tsx
interface NavItem {
  path: string;
  label: string;
  icon: string;
  badge?: number; // Add badge property
  badgeColor?: string; // Optional badge color
}

const mainNavItems: NavItem[] = [
  { path: "/mt5", label: "Dashboard", icon: "🏠" },
  { 
    path: "/mt5/notifications", 
    label: "Notifications", 
    icon: "🔔",
    badge: 5, // 5 unread notifications
    badgeColor: "var(--neon-ruby)" 
  },
];

// In the render:
<Link to={item.path} className="nav-item">
  <span>{item.icon}</span>
  {isExpanded && (
    <span className="flex-1">{item.label}</span>
  )}
  {item.badge && item.badge > 0 && (
    <span
      style={{
        background: item.badgeColor || "var(--neon-ruby)",
        color: "white",
        borderRadius: "10px",
        padding: "2px 6px",
        fontSize: "11px",
        fontWeight: 600,
        minWidth: "20px",
        textAlign: "center",
      }}
    >
      {item.badge > 99 ? "99+" : item.badge}
    </span>
  )}
</Link>
```

---

## Nested Sub-Menus

Add expandable sub-menus:

```tsx
interface NavItem {
  path: string;
  label: string;
  icon: string;
  subItems?: NavItem[]; // Add sub-items
}

const mainNavItems: NavItem[] = [
  { path: "/mt5", label: "Dashboard", icon: "🏠" },
  {
    path: "/mt5/trades",
    label: "Trades",
    icon: "📊",
    subItems: [
      { path: "/mt5/trades/active", label: "Active", icon: "🟢" },
      { path: "/mt5/trades/history", label: "History", icon: "📜" },
      { path: "/mt5/trades/pending", label: "Pending", icon: "⏳" },
    ],
  },
];

// In component state:
const [expandedItems, setExpandedItems] = useState<string[]>([]);

const toggleSubMenu = (path: string) => {
  setExpandedItems(prev =>
    prev.includes(path)
      ? prev.filter(p => p !== path)
      : [...prev, path]
  );
};

// In render:
<li key={item.path}>
  <div
    onClick={() => item.subItems && toggleSubMenu(item.path)}
    className="nav-item"
  >
    <span>{item.icon}</span>
    {isExpanded && (
      <>
        <span className="flex-1">{item.label}</span>
        {item.subItems && (
          <span>{expandedItems.includes(item.path) ? "▼" : "▶"}</span>
        )}
      </>
    )}
  </div>
  
  {/* Sub-items */}
  {item.subItems && expandedItems.includes(item.path) && (
    <ul style={{ paddingLeft: "20px" }}>
      {item.subItems.map(subItem => (
        <li key={subItem.path}>
          <Link to={subItem.path} className="nav-item">
            <span>{subItem.icon}</span>
            {isExpanded && <span>{subItem.label}</span>}
          </Link>
        </li>
      ))}
    </ul>
  )}
</li>
```

---

## Keyboard Shortcuts

Add keyboard shortcut to toggle sidebar:

```tsx
useEffect(() => {
  const handleKeyPress = (e: KeyboardEvent) => {
    // Ctrl+B or Cmd+B to toggle sidebar
    if ((e.ctrlKey || e.metaKey) && e.key === "b") {
      e.preventDefault();
      setIsExpanded(prev => !prev);
    }
  };

  window.addEventListener("keydown", handleKeyPress);
  return () => window.removeEventListener("keydown", handleKeyPress);
}, []);
```

Add visual hint:

```tsx
<button onClick={() => setIsExpanded(!isExpanded)} title="Toggle Sidebar (Ctrl+B)">
  <span>{isExpanded ? "◀" : "▶"}</span>
  {isExpanded && (
    <span className="flex items-center gap-2">
      Collapse
      <kbd className="text-xs px-1 py-0.5 bg-[var(--glass-primary)] rounded">
        Ctrl+B
      </kbd>
    </span>
  )}
</button>
```

---

## LocalStorage Persistence

Persist sidebar state across sessions:

```tsx
const [isExpanded, setIsExpanded] = useState(() => {
  // Load from localStorage on mount
  const saved = localStorage.getItem("sidebar-expanded");
  return saved ? JSON.parse(saved) : true;
});

useEffect(() => {
  // Save to localStorage on change
  localStorage.setItem("sidebar-expanded", JSON.stringify(isExpanded));
}, [isExpanded]);
```

---

## Theme Integration

Integrate with theme switcher:

```tsx
import { useTheme } from "next-themes";

export default function Sidebar() {
  const { theme, setTheme } = useTheme();

  return (
    <aside className="sidebar">
      {/* ... navigation ... */}
      
      {/* Theme Switcher in bottom section */}
      <div className="border-t border-[var(--glass-border)] p-4">
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="nav-item w-full"
        >
          <span>{theme === "dark" ? "🌙" : "☀️"}</span>
          {isExpanded && <span>Theme: {theme}</span>}
        </button>
      </div>
    </aside>
  );
}
```

---

## Animation Variants

### Framer Motion Integration

```tsx
import { motion, AnimatePresence } from "framer-motion";

<motion.aside
  initial={false}
  animate={{
    width: isExpanded ? "240px" : "64px",
  }}
  transition={{
    duration: 0.3,
    ease: "easeInOut",
  }}
  className="sidebar"
>
  {/* Content */}
</motion.aside>

// Animate nav items
{mainNavItems.map((item) => (
  <motion.li
    key={item.path}
    initial={{ opacity: 0, x: -20 }}
    animate={{ opacity: 1, x: 0 }}
    transition={{ duration: 0.2 }}
  >
    <Link to={item.path} className="nav-item">
      {/* ... */}
    </Link>
  </motion.li>
))}
```

### Staggered Children Animation

```tsx
<motion.ul
  initial="hidden"
  animate="visible"
  variants={{
    visible: {
      transition: {
        staggerChildren: 0.05,
      },
    },
  }}
>
  {mainNavItems.map((item) => (
    <motion.li
      key={item.path}
      variants={{
        hidden: { opacity: 0, x: -20 },
        visible: { opacity: 1, x: 0 },
      }}
    >
      {/* Nav item */}
    </motion.li>
  ))}
</motion.ul>
```

---

## Custom Icons

### Using Lucide React Icons

```tsx
import { Home, BarChart3, TrendingUp, Bot, Settings } from "lucide-react";

const mainNavItems = [
  { path: "/mt5", label: "Dashboard", Icon: Home },
  { path: "/mt5/trades", label: "Trades", Icon: BarChart3 },
  { path: "/mt5/performance", label: "Performance", Icon: TrendingUp },
  { path: "/mt5/agents", label: "Agents", Icon: Bot },
  { path: "/mt5/settings", label: "Settings", Icon: Settings },
];

// In render:
<Link to={item.path} className="nav-item">
  <item.Icon 
    size={20} 
    className={isActive(item.path) ? "text-[var(--neon-blue)]" : ""} 
  />
  {isExpanded && <span>{item.label}</span>}
</Link>
```

### SVG Icons with Glow Effect

```tsx
<svg
  width="20"
  height="20"
  viewBox="0 0 24 24"
  fill="none"
  className="nav-icon"
  style={{
    filter: isActive(item.path) 
      ? "drop-shadow(0 0 8px var(--neon-blue))" 
      : "none",
  }}
>
  <path d="..." fill="currentColor" />
</svg>
```

---

## Advanced Styling

### Gradient Border on Active

```tsx
.nav-item-active {
  position: relative;
  background: rgba(59, 130, 246, 0.15);
}

.nav-item-active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 60%;
  background: linear-gradient(180deg, 
    var(--neon-blue), 
    var(--neon-purple), 
    var(--neon-cyan)
  );
  border-radius: 0 4px 4px 0;
  box-shadow: 0 0 12px var(--neon-blue);
  animation: pulse-glow 2s infinite;
}
```

### Hover Lift Effect

```css
.nav-item:hover {
  transform: translateX(4px);
  box-shadow: 
    -4px 0 8px rgba(59, 130, 246, 0.2),
    0 0 20px rgba(59, 130, 246, 0.15);
}
```

### Progress Indicator

```tsx
// Add to nav item for loading state
{item.isLoading && (
  <div
    style={{
      position: "absolute",
      bottom: 0,
      left: 0,
      right: 0,
      height: "2px",
      background: "var(--glass-border)",
      overflow: "hidden",
    }}
  >
    <div
      className="progress-bar-animation"
      style={{
        height: "100%",
        background: "linear-gradient(90deg, var(--neon-blue), var(--neon-purple))",
        animation: "progress 1s ease-in-out infinite",
      }}
    />
  </div>
)}

<style>{`
  @keyframes progress {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
`}</style>
```

---

## Performance Optimization

### Memoize Navigation Items

```tsx
const mainNavItems = useMemo(() => [
  { path: "/mt5", label: "Dashboard", icon: "🏠" },
  // ... other items
], []);
```

### Debounce Window Resize

```tsx
import { useState, useEffect } from "react";

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
}

// In component:
const [windowWidth, setWindowWidth] = useState(window.innerWidth);
const debouncedWidth = useDebounce(windowWidth, 200);

useEffect(() => {
  const handleResize = () => setWindowWidth(window.innerWidth);
  window.addEventListener("resize", handleResize);
  return () => window.removeEventListener("resize", handleResize);
}, []);

useEffect(() => {
  setIsMobile(debouncedWidth < 768);
}, [debouncedWidth]);
```

---

## Accessibility Enhancements

### Screen Reader Support

```tsx
<nav aria-label="Main navigation">
  <ul role="list">
    {mainNavItems.map((item) => (
      <li key={item.path}>
        <Link
          to={item.path}
          aria-current={isActive(item.path) ? "page" : undefined}
          aria-label={`Navigate to ${item.label}`}
        >
          <span aria-hidden="true">{item.icon}</span>
          {isExpanded && <span>{item.label}</span>}
        </Link>
      </li>
    ))}
  </ul>
</nav>
```

### Focus Management

```css
.nav-item:focus-visible {
  outline: 2px solid var(--neon-blue);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2);
}
```

---

## Testing

### Component Test Example

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import Sidebar from "./Sidebar";

describe("Sidebar", () => {
  it("toggles expand/collapse on button click", () => {
    render(
      <BrowserRouter>
        <Sidebar />
      </BrowserRouter>
    );

    const toggleButton = screen.getByText(/collapse/i);
    expect(toggleButton).toBeInTheDocument();

    fireEvent.click(toggleButton);
    expect(screen.getByText(/expand/i)).toBeInTheDocument();
  });

  it("highlights active route", () => {
    window.history.pushState({}, "", "/mt5/trades");
    render(
      <BrowserRouter>
        <Sidebar />
      </BrowserRouter>
    );

    const tradesLink = screen.getByText("Trades");
    expect(tradesLink.closest("a")).toHaveClass("nav-item-active");
  });
});
```

---

## Conclusion

These advanced patterns allow you to:
- Add rich interactions (badges, sub-menus)
- Improve UX (keyboard shortcuts, persistence)
- Enhance visuals (custom icons, animations)
- Optimize performance (memoization, debouncing)
- Ensure accessibility (ARIA, focus management)

Mix and match these techniques based on your requirements!
