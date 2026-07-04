/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#142847',
        accent: '#22d3ee',
      },
      fontFamily: {
        sans: ['Rubik', 'Noto Sans Hebrew', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
