/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["JetBrains Mono", "monospace"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      colors: {
        hacker: {
          dark: "#020502",
          bg: "#050A05",
          panel: "#0A120A",
          border: "#122012",
          primary: "#00FF41",
          secondary: "#008F11",
          highlight: "#E6FFEA",
          error: "#FF003C",
          warning: "#FCE803",
          cyan: "#00FFFF"
        },
        surface: {
          50: "#E6FFEA",
          100: "#B8E6C2",
          200: "#8ACD9A",
          300: "#5DB472",
          400: "#309B49",
          500: "#00FF41",
          600: "#008F11",
          700: "#122012",
          800: "#0A120A",
          900: "#050A05",
          950: "#020502",
        },
        accent: {
          cyan: "#00FFFF",
          violet: "#B026FF",
          emerald: "#00FF41",
          amber: "#FCE803",
          rose: "#FF003C",
        },
      },
      animation: {
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
        "slide-up": "slide-up 0.3s ease-out",
        "fade-in": "fade-in 0.4s ease-out",
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
      },
    },
  },
  plugins: [],
};
