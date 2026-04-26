import { motion, useReducedMotion } from 'framer-motion';
import { getTeamAccentBoxClass } from '../../data/teamAccentClasses';

export interface TeamBadgeProps {
  teamId: string;
  name: string;
  shortLabel: string;
  className?: string;
}

export function TeamBadge({ teamId, name, shortLabel, className = '' }: TeamBadgeProps) {
  const box = getTeamAccentBoxClass(teamId);
  const reduce = useReducedMotion();

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <motion.span
        className={`flex h-9 min-w-9 items-center justify-center rounded-lg border px-2 font-mono text-sm font-bold text-[var(--color-text)] ${box}`}
        whileHover={reduce ? undefined : { scale: 1.06, y: -1 }}
        transition={{ type: 'spring', stiffness: 400, damping: 22 }}
      >
        {shortLabel}
      </motion.span>
      <span className="truncate font-semibold text-[var(--color-text)]">{name}</span>
    </div>
  );
}
