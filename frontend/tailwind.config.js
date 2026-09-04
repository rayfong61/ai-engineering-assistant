export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#1d4ed8',
          700: '#1e40af',
          800: '#1e3a8a',
          900: '#172554',
        },
      },
      borderRadius: {
        card: '0.75rem',
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.06)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.06)',
      },
      fontFamily: {
        // Explicit CJK-aware stack — no webfont (most don't cover CJK
        // glyphs, and this UI is almost entirely Traditional Chinese).
        sans: [
          'ui-sans-serif',
          '"PingFang TC"',
          '"Microsoft JhengHei"',
          '"Noto Sans TC"',
          'system-ui',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
}
