import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        signal: {
          DEFAULT: "#00ff95",
          dark: "#00d17b",
        },
      },
    },
  },
  plugins: [],
};

export default config;
