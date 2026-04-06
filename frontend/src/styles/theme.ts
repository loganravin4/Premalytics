/**
 * Central design tokens for Premalytics.
 * Mirrors CSS variables in `index.css` for use in TS (e.g. Recharts).
 */
export const theme = {
  colors: {
    background: '#0a0e1a',
    surface: '#111827',
    surfaceElevated: '#1a2235',
    border: '#1e2d40',
    primary: '#37003c',
    green: '#00ff87',
    red: '#ff4757',
    yellow: '#ffd700',
    text: '#f1f5f9',
    muted: '#64748b',
    chartGrid: '#1e2d40',
    chartAxis: '#64748b',
  },
  transition: 'transition-all duration-200 ease-out',
  /** Legacy flat card — prefer GlassPanel for new UI */
  card:
    'rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]/90 backdrop-blur-sm shadow-lg',
  cardHover:
    'hover:scale-[1.01] hover:border-[var(--color-primary)]/60',
  /** Glass surface tokens */
  glass:
    'rounded-2xl border border-white/[0.08] bg-white/[0.04] shadow-[0_8px_40px_rgba(0,0,0,0.45)] backdrop-blur-2xl',
  glassHover:
    'transition-[transform,box-shadow,border-color] duration-300 ease-out hover:border-[#37003c]/45 hover:shadow-[0_16px_48px_rgba(55,0,60,0.25)]',
} as const;

export type ThemeColors = typeof theme.colors;
