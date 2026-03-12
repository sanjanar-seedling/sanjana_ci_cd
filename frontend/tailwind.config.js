/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        sidebar: '#1B3A5C',
        accent: '#2E75B6',
      },
    },
  },
  plugins: [],
};
