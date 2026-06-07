import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
        success: "hsl(var(--success))",
        danger: "hsl(var(--danger))",
        warning: "hsl(var(--warning))",
        info: "hsl(var(--info))",
        up: "hsl(var(--up))",
        down: "hsl(var(--down))",
        surface: {
          1: "hsl(var(--surface-1))",
          3: "hsl(var(--surface-3))",
        },
        accent: {
          cyan: "hsl(var(--accent-cyan))",
          emerald: "hsl(var(--accent-emerald))",
          rose: "hsl(var(--accent-rose))",
          violet: "hsl(var(--accent-violet))",
          amber: "hsl(var(--accent-amber))",
        },
      },
      fontFamily: {
        // Fallback stack ordered by metric compatibility with Fira Sans:
        // -apple-system (San Francisco) has similar x-height and width
        // Segoe UI matches well on Windows
        sans: [
          "Fira Sans",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
          "Apple Color Emoji",
          "Segoe UI Emoji",
        ],
        // Fallback stack ordered by metric compatibility with Fira Code:
        // ui-monospace picks SF Mono on macOS/iOS; Cascadia Code on Windows Terminal
        // Menlo/Consolas are good mid-width fallbacks
        mono: [
          "Fira Code",
          "ui-monospace",
          "SF Mono",
          "Cascadia Code",
          "Menlo",
          "Consolas",
          "DejaVu Sans Mono",
          "monospace",
        ],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(-4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-down": {
          "0%": { opacity: "0", transform: "translateY(-8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(8px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "slide-in-left": {
          "0%": { opacity: "0", transform: "translateX(-8px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.96)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out",
        "fade-in-up": "fade-in-up 0.3s ease-out",
        "fade-in-down": "fade-in-down 0.2s ease-out",
        "slide-in-right": "slide-in-right 0.2s ease-out",
        "slide-in-left": "slide-in-left 0.2s ease-out",
        "scale-in": "scale-in 0.2s ease-out",
        shimmer: "shimmer 2s infinite linear",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
} satisfies Config;
