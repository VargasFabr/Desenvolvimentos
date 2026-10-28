/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#0f172a",
          foreground: "#f8fafc",
        },
        accent: {
          DEFAULT: "#047857",
          foreground: "#ecfdf5",
        },
        muted: {
          DEFAULT: "#f1f5f9",
          foreground: "#64748b",
        },
        border: "#e2e8f0",
        ring: "#0f172a",
      },
      borderRadius: {
        DEFAULT: "0.375rem",
        lg: "0.5rem",
      },
    },
  },
  plugins: [],
};
