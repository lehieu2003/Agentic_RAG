/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
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
