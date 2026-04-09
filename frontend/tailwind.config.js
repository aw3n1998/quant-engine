/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Share Tech Mono", "JetBrains Mono", "monospace"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      colors: {
        bg:     { primary: '#020502', secondary: '#050A05', tertiary: '#0A120A', input: '#0A110A' },
        border: { dim: '#122012', base: '#1A3A1A', bright: '#008F11' },
        text:   { primary: '#00FF41', secondary: '#008F11', muted: '#305030', highlight: '#E6FFEA' },
        accent: { cyan: '#00FFFF', violet: '#B026FF', magenta: '#C724FF', emerald: '#00FF41', amber: '#FCE803', rose: '#FF003C' },
      },
      fontSize: {
        'display': ['20px', { lineHeight: '1.2', fontWeight: '700' }],
        'heading': ['14px', { lineHeight: '1.4', fontWeight: '700' }],
        'body':    ['13px', { lineHeight: '1.5', fontWeight: '400' }],
        'caption': ['11px', { lineHeight: '1.4', fontWeight: '400' }],
        'metric':  ['24px', { lineHeight: '1', fontWeight: '700' }],
      },
      animation: {
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
        "slide-up": "slide-up 0.3s ease-out",
        "fade-in": "fade-in 0.4s ease-out",
        "scan": "scan 3s linear infinite",
      },
      keyframes: {
        "glow-pulse": {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
        "slide-up": {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "scan": {
          "0%": { left: "-100%" },
          "100%": { left: "100%" },
        },
      },
    },
  },
  plugins: [],
};
