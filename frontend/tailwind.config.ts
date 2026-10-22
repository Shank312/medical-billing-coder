import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Primary navy.
        brand: {
          50: '#eef4f9',
          100: '#d8e6f1',
          200: '#b2cde4',
          300: '#7ea9cc',
          400: '#4b80ad',
          500: '#2b5f8c',
          600: '#1b4166',
          700: '#12304A',
          800: '#0e2639',
          900: '#0a1b29',
        },
        // Accent teal.
        accent: {
          50: '#ecf7f5',
          100: '#d0ece7',
          200: '#a4d9cf',
          300: '#74c3b3',
          400: '#45a896',
          500: '#238a7b',
          600: '#0F766E',
          700: '#0d5f59',
          800: '#0b4b47',
          900: '#083a37',
        },
        // Semantic neutrals.
        ink: {
          DEFAULT: '#172B3A',
          muted: '#5B6B7A',
          faint: '#8494A3',
        },
        surface: '#F5F8FC',
        line: '#DCE5EF',
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(18 48 74 / 0.05), 0 1px 3px 0 rgb(18 48 74 / 0.08)',
        raised: '0 2px 8px -2px rgb(18 48 74 / 0.10), 0 1px 2px 0 rgb(18 48 74 / 0.06)',
      },
      borderRadius: {
        '2xl': '0.9rem',
      },
    },
  },
  plugins: [],
};

export default config;
