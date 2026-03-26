/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        brand: {
          50:  "#f0f9ff",
          100: "#e0f2fe",
          500: "#0ea5e9",
          600: "#0284c7",
          700: "#0369a1",
          900: "#0c4a6e",
        },
      },
      typography: {
        DEFAULT: {
          css: {
            maxWidth: "none",
            color: "inherit",
            a: { color: "#0ea5e9", "&:hover": { color: "#0369a1" } },
            "h1,h2,h3,h4": { color: "inherit", fontWeight: "700" },
            code: { color: "#e879f9", background: "rgba(232,121,249,0.1)", borderRadius: "0.25rem", padding: "0.1rem 0.3rem" },
            "pre code": { color: "inherit", background: "transparent", padding: 0 },
          },
        },
      },
    },
  },
  plugins: [],
};
