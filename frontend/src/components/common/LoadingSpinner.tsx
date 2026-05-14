import { motion, useReducedMotion } from 'framer-motion';

export interface LoadingSpinnerProps {
  label?: string;
  className?: string;
}

export function LoadingSpinner({ label = 'Loading', className = '' }: LoadingSpinnerProps) {
  const reduce = useReducedMotion();

  return (
    <div
      className={`flex flex-col items-center justify-center gap-4 py-20 text-[var(--color-text-muted)] ${className}`}
      role="status"
      aria-live="polite"
    >
      <motion.div
        className="h-11 w-11 rounded-full border-2 border-white/10 border-t-[#00ff87] shadow-[0_0_20px_rgba(0,255,135,0.25)]"
        aria-hidden
        animate={reduce ? undefined : { rotate: 360 }}
        transition={reduce ? undefined : { repeat: Infinity, duration: 0.85, ease: 'linear' }}
      />
      <motion.span
        className="text-sm tracking-wide"
        animate={reduce ? undefined : { opacity: [0.55, 1, 0.55] }}
        transition={reduce ? undefined : { repeat: Infinity, duration: 1.8, ease: 'easeInOut' }}
      >
        {label}
      </motion.span>
    </div>
  );
}
