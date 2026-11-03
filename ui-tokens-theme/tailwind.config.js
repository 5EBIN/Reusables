/** A colour that reads a CSS variable and still takes Tailwind's opacity modifier (bg-accent/15). */
const tok = name => ({ opacityValue }) =>
  opacityValue === undefined || opacityValue === '1' ? `var(--${name})` : `color-mix(in srgb, var(--${name}) calc(${opacityValue} * 100%), transparent)`;

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx}",
    "./src/components/**/*.{js,ts,jsx,tsx}",
    "./src/pages/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        // Every colour reads a CSS variable from styles/globals.css, so a class follows the theme. No hex lives here.
        bg: tok('bg'), card: tok('card'), sunk: tok('sunk'), hover: tok('hover'), sel: tok('sel'),
        line: tok('line'), line2: tok('line2'), ctl: tok('ctl'),
        t1: tok('t1'), t2: tok('t2'), t3: tok('t3'),
        pass: tok('pass'), fail: tok('fail'), warn: tok('warn'), info: tok('info'), ai: tok('ai'), neutral: tok('neutral'), locked: tok('locked'),
        scrim: tok('scrim'),
        accent: { DEFAULT: tok('accent'), fg: tok('accent-fg'), soft: tok('accent-soft'), dark: tok('accent'), light: tok('accent') },
        // Deprecated names of the old slate/indigo palette, now aliases of the tokens above (the hex values are gone). Screens drop them as R4 restyles them.
        surface: {
          950: tok('bg'), 900: tok('sunk'), 800: tok('card'), 700: tok('line2'), 600: tok('ctl'),
          500: tok('t3'), 400: tok('t3'), 300: tok('t2'), 200: tok('t1'), 100: tok('t1'),
        },
        success: { DEFAULT: tok('pass'), light: tok('pass') },
        warning: { DEFAULT: tok('warn'), light: tok('warn') },
        danger:  { DEFAULT: tok('fail'), light: tok('fail') },
      },
      borderRadius: { r1: 'var(--r1)', r2: 'var(--r2)', r3: 'var(--r3)', r4: 'var(--r4)' },
      boxShadow: { sh1: 'var(--sh1)', sh2: 'var(--sh2)' },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.2s ease-out',
        'slide-in-right': 'slide-in-right 0.3s ease-out',
      },
      fontFamily: {
        'dm-mono': ['var(--font-dm-mono)', 'DM Mono', 'monospace'],
        'dm-sans': ['var(--font-dm-sans)', 'DM Sans', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
