---
name: tailwind
description: Use when composing Tailwind utilities, building responsive or dark-mode layouts, defining component variants with cva, resolving conflicting classes with tailwind-merge, or configuring a custom theme.
---

# Tailwind CSS Patterns

Utility-first CSS with Tailwind v3/v4, component variants, and the cn() pattern.

## When to Activate

- Composing utilities for layout (flex, grid, spacing, sizing)
- Responsive design with breakpoint prefixes
- Dark mode with `dark:` variants
- Building component variants with `cva` (class-variance-authority)
- Deduplicating conflicting classes with `tailwind-merge`
- Configuring custom colors, fonts, or spacing in `tailwind.config`
- Animating with `transition`, `animate-*`, or custom keyframes

---

## Core Utility Patterns

### Spacing and sizing

```tsx
// Padding / margin — p-{n}, m-{n}, px-{n}, py-{n}, pt/pr/pb/pl
<div className="p-4 mt-2 px-6 py-3">          {/* p=16px, mt=8px, px=24px, py=12px */}

// Width / height
<div className="w-full max-w-lg h-screen min-h-0">
<div className="w-[340px] h-[calc(100vh-64px)]">  {/* arbitrary values */}

// Margin auto (centering)
<div className="mx-auto max-w-2xl">
```

### Flexbox

```tsx
<div className="flex items-center justify-between gap-4">
<div className="flex flex-col gap-2">
<div className="flex flex-wrap gap-2">
<div className="flex items-start justify-center">

// Flex children
<div className="flex-1 min-w-0">          {/* grow, allow shrinking below content size */}
<div className="flex-none w-16">          {/* fixed width */}
<div className="flex-shrink-0">           {/* don't shrink */}
```

### Grid

```tsx
<div className="grid grid-cols-3 gap-6">
<div className="grid grid-cols-[1fr_2fr_1fr] gap-4">    {/* arbitrary template */}
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

{/* Spanning */}
<div className="col-span-2">
<div className="col-start-2 col-end-4">
```

### Typography

```tsx
<h1 className="text-3xl font-bold tracking-tight text-gray-900">
<p  className="text-base text-gray-600 leading-relaxed">
<span className="text-sm font-medium text-blue-600 uppercase tracking-wide">

// Truncate long text
<p className="truncate">                    {/* single line ellipsis */}
<p className="line-clamp-3">               {/* clamp to 3 lines */}
```

---

## Responsive Design

Tailwind is **mobile-first** — unprefixed utilities apply to all sizes, prefixes override at that breakpoint and up.

```tsx
// Breakpoints: sm(640px), md(768px), lg(1024px), xl(1280px), 2xl(1536px)
<div className="
  grid
  grid-cols-1           {/* mobile: 1 column */}
  sm:grid-cols-2        {/* sm+: 2 columns */}
  lg:grid-cols-3        {/* lg+: 3 columns */}
">

// Hide/show
<div className="hidden md:block">      {/* hidden on mobile, visible md+ */}
<div className="block md:hidden">      {/* visible on mobile, hidden md+ */}

// Text size changes per breakpoint
<h1 className="text-xl md:text-3xl lg:text-5xl font-bold">
```

---

## Dark Mode

```tsx
// tailwind.config — use 'class' strategy (toggle via class on <html>)
darkMode: 'class'

// Next.js — use next-themes
<html className={theme === 'dark' ? 'dark' : ''}>

// In components
<div className="bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
<button className="bg-blue-600 dark:bg-blue-500 hover:bg-blue-700 dark:hover:bg-blue-400">
```

---

## State Variants

```tsx
// Hover, focus, active
<button className="
  bg-blue-600
  hover:bg-blue-700
  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
  active:bg-blue-800
  disabled:opacity-50 disabled:cursor-not-allowed
">

// Group hover — parent hover affects children
<div className="group">
  <div className="opacity-0 group-hover:opacity-100 transition-opacity">
    Shows on parent hover
  </div>
</div>

// Peer — sibling state
<input className="peer" />
<p className="hidden peer-focus:block">Focused hint</p>
<p className="hidden peer-invalid:block text-red-500">Invalid input</p>
```

---

## The `cn()` Helper

`cn()` merges class names and resolves Tailwind conflicts (last one wins with `tailwind-merge`).

```bash
npm install clsx tailwind-merge
```

```tsx
// lib/utils.ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Usage — conditional classes, no conflicts
<div className={cn(
  "rounded-lg border p-4",
  isActive && "border-blue-500 bg-blue-50",
  isError && "border-red-500 bg-red-50",
  className,    // external overrides win
)}>

// Conflict resolution — twMerge picks the last conflicting utility
cn("px-4 px-6")         // → "px-6"
cn("text-red-500", "text-blue-500")  // → "text-blue-500"
```

---

## Component Variants with `cva`

`cva` (class-variance-authority) defines components with typed variant props.

```bash
npm install class-variance-authority
```

```tsx
// components/ui/button.tsx
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  // Base styles — always applied
  "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:     "bg-blue-600 text-white hover:bg-blue-700",
        destructive: "bg-red-600 text-white hover:bg-red-700",
        outline:     "border border-gray-300 bg-white hover:bg-gray-50",
        ghost:       "hover:bg-gray-100 hover:text-gray-900",
        link:        "text-blue-600 underline-offset-4 hover:underline",
      },
      size: {
        sm:      "h-8 px-3 text-sm",
        default: "h-10 px-4 py-2",
        lg:      "h-12 px-8 text-lg",
        icon:    "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
)

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

// Usage
<Button>Default</Button>
<Button variant="destructive" size="lg">Delete</Button>
<Button variant="outline" size="sm">Cancel</Button>
```

---

## Custom Theme Config

```js
// tailwind.config.ts
import type { Config } from "tailwindcss"

export default {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#eff6ff",
          500: "#3b82f6",
          900: "#1e3a5f",
        },
        // CSS variable-based (works with shadcn/ui)
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        "spin-slow": {
          to: { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "fade-in":   "fade-in 0.2s ease-out",
        "spin-slow": "spin-slow 3s linear infinite",
      },
    },
  },
} satisfies Config
```

---

## Animations and Transitions

```tsx
// Transitions — apply to base element, variants add what changes
<button className="
  transition-colors duration-200 ease-in-out
  bg-blue-600 hover:bg-blue-700
">

// All properties
<div className="transition-all duration-300">

// Transform
<div className="transition-transform hover:scale-105 hover:-translate-y-1">
<div className="hover:rotate-3 transition-transform duration-200">

// Opacity fade
<div className={cn(
  "transition-opacity duration-300",
  isVisible ? "opacity-100" : "opacity-0",
)}>

// Built-in animations
<div className="animate-spin">       {/* loading spinner */}
<div className="animate-pulse">      {/* skeleton loading */}
<div className="animate-bounce">
<div className="animate-fade-in">    {/* custom from config */}
```

---

## Common Component Patterns

### Card

```tsx
<div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-950">
  <div className="p-6">
    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Title</h3>
    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">Description</p>
  </div>
  <div className="border-t border-gray-200 px-6 py-4 dark:border-gray-800">
    <Button>Action</Button>
  </div>
</div>
```

### Input

```tsx
<input className="
  w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm
  placeholder:text-gray-400
  focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500
  disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500
  dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100
" />
```

### Badge

```tsx
const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "bg-gray-100 text-gray-800",
        success: "bg-green-100 text-green-800",
        warning: "bg-yellow-100 text-yellow-800",
        error:   "bg-red-100 text-red-800",
        info:    "bg-blue-100 text-blue-800",
      },
    },
    defaultVariants: { variant: "default" },
  },
)
```

### Modal overlay

```tsx
{/* Backdrop */}
<div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm" onClick={onClose} />

{/* Panel */}
<div className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2
  rounded-xl bg-white p-6 shadow-xl dark:bg-gray-900">
  ...
</div>
```

---

## Tailwind v4 (New in 2025)

```css
/* No tailwind.config — configure in CSS */
@import "tailwindcss";

@theme {
  --color-brand-500: #3b82f6;
  --font-sans: "Inter", sans-serif;
  --radius-lg: 0.75rem;
}

/* Dark mode via media query by default (no class strategy needed) */
/* Use @variant dark { ... } for custom dark styles */
```

v4 changes: config moves to CSS `@theme`, faster build, no PostCSS required, native cascade layers.

---

## Red Flags

- **String template literals for conditional classes** — `` `bg-${color} p-4` `` generates class names at runtime that Tailwind's static scanner never sees and therefore never includes in the output CSS; use only complete class names from the source, with `cn()` for conditions
- **Conflicting utilities without `tailwind-merge`** — `className="px-4 px-6"` applies both; the last rule in the stylesheet wins (not the last in the string), which is unpredictable; `twMerge` resolves conflicts correctly by keeping only the last conflicting utility
- **Repeating variant logic in `if/else` strings** — `className={isActive ? "bg-blue-600 text-white rounded-lg px-4" : "bg-gray-100 text-gray-900 rounded-lg px-4"}` duplicates base classes; use `cva` to declare base + variant styles separately
- **Arbitrary values that are repeated** — `w-[340px]` appearing in five components belongs in `theme.extend` as a named token; arbitrary values are for one-offs only
- **Missing `dark:` variants on color utilities** — adding `bg-white text-gray-900` without corresponding `dark:bg-gray-900 dark:text-gray-100` makes dark mode look broken; pair every color with its dark-mode variant at the same time
- **No `focus-visible:ring` on interactive elements** — keyboard users navigating with Tab have no visible indicator when focus styles are absent; every button and link needs a `focus-visible:ring-*` class for WCAG AA compliance
- **Importing Tailwind classes from JS variables** — storing class names in a variable and spreading them defeats the static content scanner; Tailwind purges any class it cannot find as a complete string in the source at build time

## Checklist

- [ ] `cn()` used instead of string concatenation for conditional classes
- [ ] `cva` used for components with multiple variants (not `if/else` strings)
- [ ] Responsive classes ordered mobile-first (base → sm: → md: → lg:)
- [ ] `group` / `peer` used for parent/sibling state instead of JS state
- [ ] `dark:` variants added alongside every color utility
- [ ] `transition-colors` / `transition-all` on interactive elements
- [ ] `focus-visible:ring` on all interactive elements for keyboard accessibility
- [ ] Arbitrary values (`w-[340px]`) used sparingly — extend theme for repeated values
- [ ] `disabled:` variants on form elements to style disabled state
