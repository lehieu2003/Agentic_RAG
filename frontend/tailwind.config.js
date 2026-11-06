const SHADES = ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900', '950'];

/** Palette whose shades resolve to CSS variables swapped by [data-theme] (see index.css). */
const themed = (name) =>
  Object.fromEntries(SHADES.map((s) => [s, `rgb(var(--c-${name}-${s}) / <alpha-value>)`]));

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        zinc: themed('zinc'),
        sky: themed('sky'),
        emerald: themed('emerald'),
        rose: themed('rose'),
        amber: themed('amber'),
        violet: themed('violet'),
        white: 'rgb(var(--c-white) / <alpha-value>)',
        canvas: 'rgb(var(--c-canvas) / <alpha-value>)',
        surface: {
          DEFAULT: '#121215',
          elevated: '#18181b',
          subtle: '#222227',
        },
        'surface-elevated': '#18181b',
        'surface-subtle': '#222227',
        brand: {
          DEFAULT: '#38bdf8',
          sky: '#38bdf8',
          emerald: '#10b981',
          violet: '#a855f7',
        },
        'brand-sky': '#38bdf8',
        'brand-emerald': '#10b981',
        'brand-violet': '#a855f7',
        obsidian: {
          DEFAULT: '#0d1117',
          bg: '#0d1117',
          surface: '#161b22',
          subtle: '#21262d',
          border: '#30363d',
          accent: '#238636',
          'accent-blue': '#58a6ff',
          text: '#c9d1d9',
          'text-muted': '#8b949e',
        },
      },
    },
  },
  plugins: [],
};
