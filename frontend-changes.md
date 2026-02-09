# Frontend Changes: Dark/Light Theme Toggle

## Overview
Added a toggle button that allows users to switch between dark and light themes. The user's preference is persisted in `localStorage`.

## Files Changed

### `frontend/index.html`
- Added a `<button class="theme-toggle" id="themeToggle">` element positioned fixed in the top-right corner
- The button contains two SVG icons: a sun icon (visible in dark mode) and a moon icon (visible in light mode)
- Includes `aria-label` and `title` attributes for accessibility
- Bumped cache-bust version from `?v=9` to `?v=10` on CSS and JS includes

### `frontend/style.css`
- Added `[data-theme="light"]` rule with a full set of light theme CSS variables:
  - Light backgrounds (`#f8fafc`, `#ffffff`)
  - Dark text for contrast (`#0f172a`, `#475569`)
  - Adjusted border, surface-hover, and shadow colors
  - Added `--code-bg` variable for code block backgrounds (used in both themes)
- Added `.theme-toggle` button styles:
  - Fixed position, top-right corner, circular shape, `z-index: 100`
  - Hover scale effect, focus ring, active press effect
  - Sun/moon icon transition: opacity and rotation animations (0.3s ease)
  - In dark mode the sun icon is visible; in light mode the moon icon is visible
- Added `transition: background-color 0.3s ease, color 0.3s ease` to `body` for smooth theme switching
- Added transitions to `.sidebar`, `.message-content`, and `.chat-input-container` for smooth color changes
- Replaced hardcoded `rgba(0, 0, 0, 0.2)` on `.message-content code` and `.message-content pre` with `var(--code-bg)`
- Added responsive sizing for the toggle button at `max-width: 1024px`

### `frontend/script.js`
- Added `initTheme()` function: reads saved theme from `localStorage` and applies it to `document.body` via `data-theme` attribute
- Added `toggleTheme()` function: toggles between `dark` and `light` themes, saves to `localStorage`
- `initTheme()` is called immediately (before `DOMContentLoaded`) to prevent a flash of the wrong theme
- Toggle button click listener registered inside `DOMContentLoaded`

## How It Works
1. Theme state is stored as a `data-theme` attribute on `<body>` (`"light"` or `"dark"`)
2. CSS variables are overridden via `[data-theme="light"]` selector
3. All themed elements use CSS variables, so switching the attribute cascades the color change
4. Smooth transitions (0.3s) on key elements prevent jarring color switches
5. The toggle button icon animates between sun and moon with rotation + opacity transitions
6. `localStorage` persists the preference across page reloads and sessions
