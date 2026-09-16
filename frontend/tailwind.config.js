/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: '#F2F1ED',
        panel: '#FFFFFF',
        ink: '#1B1D1C',
        muted: '#6B7069',
        rule: '#D5D6D0',
        console: '#24485F',
        stop: '#C0342B',
        caution: '#D98B0A',
        go: '#2E7D4F',
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        readout: ['1.55rem', { lineHeight: '1.1', letterSpacing: '-0.01em' }],
      },
    },
  },
  plugins: [],
}
