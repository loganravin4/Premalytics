/**
 * Frosted “glass” panel: semi-transparent fill, blur, soft border, optional stronger shadow.
 * Implemented as `motion.div` so callers can pass Framer Motion props (`whileHover`, `layout`, …).
 */
import type { HTMLMotionProps } from 'framer-motion';
import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

export interface GlassPanelProps extends Omit<HTMLMotionProps<'div'>, 'children'> {
  children: ReactNode;
  /** Stronger border + shadow for primary cards / modals */
  elevated?: boolean;
  className?: string;
}

/** Default glass: light edge highlight (inset) + backdrop blur */
const base =
  'rounded-2xl border border-white/[0.08] bg-white/[0.04] shadow-[0_8px_40px_rgba(0,0,0,0.45),inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-2xl';
/** Slightly more contrast — use for hero cards or elevated sections */
const elevated =
  'border-white/[0.12] bg-white/[0.06] shadow-[0_12px_48px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.08)]';

export function GlassPanel({ children, elevated: isElevated, className = '', ...rest }: GlassPanelProps) {
  return (
    <motion.div
      className={`${base} ${isElevated ? elevated : ''} ${className}`}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
