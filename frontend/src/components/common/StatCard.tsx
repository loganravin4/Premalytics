import type { ReactNode } from 'react';
import { TrendingDown, TrendingUp } from 'lucide-react';
import { useReducedMotion } from 'framer-motion';
import { GlassPanel } from './GlassPanel';
import { theme } from '../../styles/theme';

export interface StatCardTrend {
  direction: 'up' | 'down';
  percent: number;
}

export interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: ReactNode;
  trend?: StatCardTrend;
  className?: string;
}

export function StatCard({ title, value, subtitle, icon, trend, className = '' }: StatCardProps) {
  const reduce = useReducedMotion();

  return (
    <GlassPanel
      className={`group relative overflow-hidden p-5 ${theme.glassHover} ${className}`}
      whileHover={reduce ? undefined : { y: -3, scale: 1.02 }}
      transition={{ type: 'spring', stiffness: 420, damping: 28 }}
    >
      <div
        className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-[#37003c]/20 blur-2xl transition-opacity duration-500 group-hover:opacity-100"
        aria-hidden
      />
      <div className="absolute right-4 top-4 text-[var(--color-text-muted)] opacity-80 transition-transform duration-300 group-hover:scale-110">
        {icon}
      </div>
      <p className="text-sm font-medium text-[var(--color-text-muted)]">{title}</p>
      <p className="mt-2 font-mono text-3xl font-bold tracking-tight text-[var(--color-text)]">{value}</p>
      {subtitle ? <p className="mt-1 text-xs text-[var(--color-text-muted)]">{subtitle}</p> : null}
      {trend ? (
        <div
          className={`mt-3 inline-flex items-center gap-1 text-xs font-semibold ${
            trend.direction === 'up' ? 'text-[#00ff87]' : 'text-[#ff4757]'
          }`}
        >
          {trend.direction === 'up' ? (
            <TrendingUp className="h-3.5 w-3.5" aria-hidden />
          ) : (
            <TrendingDown className="h-3.5 w-3.5" aria-hidden />
          )}
          <span>{trend.percent}% vs last season</span>
        </div>
      ) : null}
    </GlassPanel>
  );
}
