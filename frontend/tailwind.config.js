/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef3ff",
          100: "#dbe6ff",
          200: "#b8ccff",
          300: "#8da8f7",
          400: "#6586e8",
          500: "#4569d1",
          600: "#294bab",
          700: "#1c357d",
          800: "#13295f",
          900: "#0b1c42",
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
