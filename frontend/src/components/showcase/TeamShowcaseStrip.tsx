import { motion, useReducedMotion } from 'framer-motion';
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { Team } from '../../types/team';
import { cardSpring } from '../../styles/motion';

export interface TeamShowcaseStripProps {
  teams: Team[];
  className?: string;
}

export function TeamShowcaseStrip({ teams, className = '' }: TeamShowcaseStripProps) {
  const reduce = useReducedMotion();

  const containerVariants = useMemo(
    () => ({
      hidden: { opacity: 0 },
      show: {
        opacity: 1,
        transition: { staggerChildren: reduce ? 0 : 0.07, delayChildren: reduce ? 0 : 0.04 },
      },
    }),
    [reduce],
  );

  const itemVariants = useMemo(
    () => ({
      hidden: { opacity: 0, y: 10 },
      show: { opacity: 1, y: 0 },
    }),
    [],
  );

  return (
    <motion.div
      className={`relative overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl sm:p-5 ${className}`}
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#00ff87]/90">League spotlight</p>
          <h2 className="text-lg font-bold tracking-tight text-[var(--color-text)]">Top clubs by points</h2>
        </div>
        <Link
          to="/teams"
          className="text-xs font-medium text-[var(--color-text-muted)] underline-offset-4 transition-colors hover:text-[#00ff87] hover:underline"
        >
          View all teams
        </Link>
      </div>
      <div className="-mx-1 flex gap-2 overflow-x-auto pb-1 pt-1 [scrollbar-width:thin]">
        {teams.map((t) => (
          <motion.div key={t.id} variants={itemVariants} transition={cardSpring} className="shrink-0">
            <Link
              to={`/teams/${t.id}`}
              className="group flex min-w-[140px] flex-col gap-2 rounded-xl border border-white/[0.06] bg-black/20 px-4 py-3 transition-colors duration-300 hover:border-[#37003c]/50 hover:bg-[#37003c]/15"
            >
              <motion.span
                className="text-3xl leading-none"
                whileHover={reduce ? undefined : { scale: 1.12, rotate: [0, -4, 4, 0] }}
                transition={{ type: 'spring', stiffness: 400, damping: 18 }}
                aria-hidden
              >
                {t.badge}
              </motion.span>
              <span className="truncate text-sm font-semibold text-[var(--color-text)] group-hover:text-white">
                {t.shortName}
              </span>
              <span className="font-mono text-xs text-[var(--color-text-muted)]">
                <span className="text-[#ffd700]">{t.stats.points}</span> pts
              </span>
            </Link>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
