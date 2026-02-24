import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Plus Jakarta Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        heading: ["Outfit", "Plus Jakarta Sans", "ui-sans-serif", "system-ui", "sans-serif"]
      },
      colors: {
        surface: {
          50: "#f2f6fb",
          100: "#e2eaf4",
          200: "#c3d2e5",
          300: "#9db5d0",
          400: "#7192b8",
          500: "#4e729a",
          600: "#35567c",
          700: "#203f62",
          800: "#17314e",
          900: "#0f2238"
        },
        accent: {
          50: "#fffde8",
          100: "#fff8bf",
          200: "#fff08a",
          300: "#ffe052",
          400: "#ffd124",
          500: "#f8c20d",
          600: "#d89f05",
          700: "#af7909",
          800: "#8f5f0f",
          900: "#764f11"
        },
        mint: {
          50: "#ecfff3",
          100: "#d2f9df",
          300: "#7fe79d",
          500: "#27c25c",
          700: "#14823f",
          900: "#0f5e30"
        },
        cobalt: {
          100: "#d9e7ff",
          300: "#8fb4ff",
          500: "#497cf2",
          700: "#274fb3"
        }
      },
      boxShadow: {
        soft: "0 10px 28px rgba(15, 34, 56, 0.11)",
        glow: "0 0 0 1px rgba(39,194,92,0.2), 0 10px 34px rgba(39,194,92,0.24)"
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" }
        },
        "page-enter": {
          "0%": { opacity: "0", transform: "translateY(14px) scale(0.995)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" }
        },
        aurora: {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1)" },
          "50%": { transform: "translate3d(0,-2%,0) scale(1.03)" }
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-8px)" }
        },
        pulseGlow: {
          "0%, 100%": { opacity: "0.45" },
          "50%": { opacity: "0.85" }
        },
        shimmer: {
          "0%": { backgroundPosition: "-180% 0" },
          "100%": { backgroundPosition: "180% 0" }
        }
      },
      animation: {
        "fade-up": "fade-up 350ms ease-out both",
        "page-enter": "page-enter 420ms cubic-bezier(0.22, 1, 0.36, 1) both",
        aurora: "aurora 12s ease-in-out infinite",
        "float-slow": "float 4.8s ease-in-out infinite",
        "float-mid": "float 3.6s ease-in-out infinite",
        "pulse-glow": "pulseGlow 3s ease-in-out infinite",
        shimmer: "shimmer 1.9s linear infinite"
      }
    }
  },
  plugins: []
};

export default config;
