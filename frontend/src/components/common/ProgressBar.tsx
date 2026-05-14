import { motion, useReducedMotion } from 'framer-motion';

export type ProgressBarColorKey = 'green' | 'yellow' | 'red' | 'purple' | 'blue';

export interface ProgressBarProps {
  value: number;
  color: ProgressBarColorKey;
  label: string;
  className?: string;
}

const fillClass: Record<ProgressBarColorKey, string> = {
  green: 'fill-[#00ff87]',
  yellow: 'fill-[#ffd700]',
  red: 'fill-[#ff4757]',
  purple: 'fill-[#37003c]',
  blue: 'fill-[#6cabdd]',
};

export function ProgressBar({ value, color, label, className = '' }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));
  const reduce = useReducedMotion();

  return (
    <div className={`w-full ${className}`}>
      <div className="mb-1 flex justify-between text-xs text-[var(--color-text-muted)]">
        <span>{label}</span>
        <span className="font-mono text-[var(--color-text)]">{clamped}%</span>
      </div>
      <svg
        viewBox="0 0 100 4"
        className="h-2.5 w-full overflow-hidden rounded-full bg-white/[0.06] shadow-inner backdrop-blur-sm"
        preserveAspectRatio="none"
        aria-hidden
      >
        <rect x="0" y="0" width="100" height="4" className="fill-white/[0.03]" />
        <motion.rect
          x="0"
          y="0"
          height="4"
          className={fillClass[color]}
          initial={reduce ? false : { width: 0 }}
          animate={{ width: clamped }}
          transition={{ duration: reduce ? 0 : 0.75, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
    </div>
  );
}
