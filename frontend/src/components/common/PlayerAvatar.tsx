import { motion, useReducedMotion } from 'framer-motion';

export interface PlayerAvatarProps {
  name: string;
  className?: string;
}

function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function PlayerAvatar({ name, className = '' }: PlayerAvatarProps) {
  const label = initials(name);
  const reduce = useReducedMotion();

  return (
    <motion.div
      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/15 bg-white/[0.06] font-mono text-xs font-bold text-[var(--color-text)] shadow-inner backdrop-blur-sm ${className}`}
      aria-hidden
      whileHover={reduce ? undefined : { scale: 1.06 }}
      whileTap={reduce ? undefined : { scale: 0.96 }}
      transition={{ type: 'spring', stiffness: 420, damping: 24 }}
    >
      {label}
    </motion.div>
  );
}
