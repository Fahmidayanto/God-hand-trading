# Sidebar Component Documentation

## Overview
A modern, collapsible left sidebar navigation component with glassmorphism design and neon hover effects for the ValueCell MT5 platform.

## Features
- ✅ **Collapsible/Expandable** - Smooth 300ms animation between 64px (collapsed) and 240px (expanded)
- ✅ **Glassmorphism Design** - Dark glass effect with blur backdrop matching design system
- ✅ **Neon Hover Effects** - Blue/purple gradient glow on hover
- ✅ **Active State** - Left border glow + background highlight for current route
- ✅ **Responsive** - Auto-collapse on mobile (<768px)
- ✅ **Tooltips** - Show labels when collapsed on hover
- ✅ **Smooth Transitions** - All animations use 300ms ease-in-out
- ✅ **Z-index Management** - Fixed at z-index: 1000 for proper layering

## Installation

The component is already created at:
```
frontend/src/components/Sidebar.tsx
```

It's already integrated in the layout:
```
frontend/src/app/mt5/_layout.tsx
```

## Usage

### Basic Usage (Already Implemented)

```tsx
import Sidebar from "@/components/Sidebar";

export default function MT5Layout() {
  return (
    <div className="min-h-screen flex bg-[var(--bg-deepspace)]">
      <Sidebar />
      <main className="flex-1 transition-all duration-300">
        {/* Your content here */}
      </main>
    </div>
  );
}
```

### Navigation Structure

**Logo Section (Top):**
- ✋⚡ God Hand (icon + text)

**Main Navigation:**
- 🏠 Dashboard (`/mt5`)
- 📊 Trades (`/mt5/trades`)
- 📈 Performance (`/mt5/performance`)
- 🤖 Agents (`/mt5/agents`)
- ⚙️ Settings (`/mt5/settings`)

**Bottom Section:**
- 🔔 Notifications (`/mt5/notifications`)
- 👤 Profile (`/mt5/profile`)
- Toggle Button (Collapse/Expand)

## Component Props

The component currently has no external props. All configuration is internal.

### Internal State:
- `isExpanded`: Boolean controlling sidebar width
- `isMobile`: Boolean for responsive behavior

## Styling

### CSS Variables Used:
```css
--bg-deepspace: #0a0e27
--glass-secondary: rgba(31, 41, 55, 0.5)
--glass-border: rgba(59, 130, 246, 0.2)
--neon-blue: #3b82f6
--neon-purple: #8b5cf6
--text-primary: #f8fafc
--text-secondary: #cbd5e1
```

### Dimensions:
- **Collapsed Width**: 64px
- **Expanded Width**: 240px
- **Height**: 100vh (full viewport)
- **Position**: Fixed left
- **Z-index**: 1000

## Responsive Behavior

### Desktop (≥768px):
- Default: Expanded (240px)
- User can toggle collapse/expand

### Mobile (<768px):
- Default: Collapsed (64px)
- Auto-collapses on window resize

## Customization

### Adding New Navigation Items

Edit the `mainNavItems` or `bottomItems` arrays:

```tsx
const mainNavItems: NavItem[] = [
  { path: "/mt5", label: "Dashboard", icon: "🏠" },
  { path: "/mt5/new-page", label: "New Page", icon: "🆕" }, // Add new item
  // ... other items
];
```

### Changing Animations

Modify transition duration in inline styles:

```tsx
style={{
  transition: "width 500ms ease-in-out", // Change from 300ms to 500ms
}}
```

### Changing Colors

Update hover effects in the `<style>` tag at the bottom:

```css
.nav-item:hover {
  background: rgba(59, 130, 246, 0.1); /* Change hover background */
  color: var(--neon-blue); /* Change hover text color */
  box-shadow: 0 0 20px rgba(59, 130, 246, 0.15); /* Change glow */
}
```

## Active Route Detection

The component uses React Router's `useLocation()` hook:

```tsx
const location = useLocation();

const isActive = (path: string) => {
  return location.pathname === path;
};
```

Active routes get:
- Left border glow (4px blue/purple gradient)
- Background highlight (rgba(59, 130, 246, 0.15))
- Enhanced box shadow

## Browser Compatibility

- ✅ Chrome/Edge (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ✅ All modern browsers supporting CSS backdrop-filter

## Performance

- Smooth 60fps animations
- No layout thrashing
- Efficient hover effects
- Minimal re-renders (internal state only)

## Accessibility

- Semantic HTML (`<nav>`, `<ul>`, `<li>`)
- Keyboard navigable (native links)
- Tooltip titles for collapsed state
- Screen reader friendly

## Troubleshooting

### Sidebar not showing:
- Check z-index conflicts
- Verify CSS variables are defined in global.css

### Tooltips not appearing:
- Ensure sidebar is in collapsed state
- Check browser supports CSS `::after` pseudo-elements

### Animation jerky:
- Check for layout shifts in parent container
- Ensure GPU acceleration is enabled

## Future Enhancements

Potential additions:
- [ ] Keyboard shortcut to toggle (Ctrl+B)
- [ ] Nested sub-menus
- [ ] Badge notifications on nav items
- [ ] Theme switcher integration
- [ ] Persist expanded/collapsed state in localStorage
- [ ] Animation preferences (reduced motion)

## Example: Adding a Badge

```tsx
<Link to={item.path} className="nav-item">
  <span>{item.icon}</span>
  {isExpanded && (
    <>
      <span>{item.label}</span>
      {item.badge && (
        <span className="badge">{item.badge}</span>
      )}
    </>
  )}
</Link>
```

## Related Files

- Component: `frontend/src/components/Sidebar.tsx`
- Layout: `frontend/src/app/mt5/_layout.tsx`
- Styles: `frontend/src/global.css`
- Routes: `frontend/src/routes.ts`

## Support

For issues or feature requests, contact the development team.
