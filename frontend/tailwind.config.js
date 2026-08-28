/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dbe6ff",
          400: "#5b8def",
          500: "#3366ff",
          600: "#254edb",
          700: "#1c3cb0",
          900: "#141e42",
        },
      },
    },
  },
  plugins: [],
}
