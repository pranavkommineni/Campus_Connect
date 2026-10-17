export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: { fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], display: ["'Plus Jakarta Sans'", "Inter", "sans-serif"] },
    colors: { ink: { 950: "#070b1f", 900: "#0b1030", 800: "#131a45", 700: "#1c2560" } } } },
  safelist: ["text-indigo-300","text-emerald-300","text-amber-300","text-sky-300","text-rose-300"],
  plugins: [],
};
