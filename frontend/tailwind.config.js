/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#e8fbff",
          100: "#d8f4f8",
          200: "#a8dce4",
          300: "#68c7d4",
          400: "#34adbf",
          500: "#18a0b8",
          600: "#108da3",
          700: "#202860",
          800: "#182048",
          900: "#111735",
        },
      },
      fontFamily: {
        sans: ["Nunito Sans", "Segoe UI", "sans-serif"],
        display: ["Manrope", "Nunito Sans", "sans-serif"],
      },
      boxShadow: {
        panel: "0 10px 30px rgba(15, 23, 42, 0.08)",
      },
    },
  },
  plugins: [],
};
