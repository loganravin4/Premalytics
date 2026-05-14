import { motion, useReducedMotion } from 'framer-motion';
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { Player } from '../../types/player';
import { PlayerAvatar } from '../common/PlayerAvatar';
import { cardSpring } from '../../styles/motion';

export interface PlayerSpotlightStripProps {
  players: Player[];
  className?: string;
}

export function PlayerSpotlightStrip({ players, className = '' }: PlayerSpotlightStripProps) {
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
          <p className="text-xs font-semibold uppercase tracking-wider text-[#ffd700]/90">Star power</p>
          <h2 className="text-lg font-bold tracking-tight text-[var(--color-text)]">Players to watch</h2>
        </div>
        <Link
          to="/players"
          className="text-xs font-medium text-[var(--color-text-muted)] underline-offset-4 transition-colors hover:text-[#ffd700] hover:underline"
        >
          Full player index
        </Link>
      </div>
      <div className="-mx-1 flex gap-3 overflow-x-auto pb-1 pt-1 [scrollbar-width:thin]">
        {players.map((p) => (
          <motion.div key={p.id} variants={itemVariants} transition={cardSpring} className="shrink-0">
            <Link
              to={`/players/${p.id}`}
              className="group flex min-w-[200px] items-center gap-3 rounded-xl border border-white/[0.06] bg-black/25 px-3 py-3 transition-colors duration-300 hover:border-[#00ff87]/35 hover:bg-[#00ff87]/5"
            >
              <motion.div whileHover={reduce ? undefined : { scale: 1.08 }} transition={cardSpring}>
                <PlayerAvatar
                  name={p.name}
                  className="h-12 w-12 border-white/10 bg-white/[0.06] text-sm shadow-lg ring-2 ring-transparent transition-[box-shadow] duration-300 group-hover:shadow-[0_0_24px_rgba(0,255,135,0.25)] group-hover:ring-[#00ff87]/30"
                />
              </motion.div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-[var(--color-text)] group-hover:text-white">{p.name}</p>
                <p className="truncate text-xs text-[var(--color-text-muted)]">{p.team}</p>
                <p className="mt-0.5 font-mono text-sm text-[#00ff87]">{p.stats.goals} goals</p>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
