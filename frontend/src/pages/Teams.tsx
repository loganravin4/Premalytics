/**
 * Teams listing page (`/teams`).
 *
 * Renders all clubs in a responsive grid. Cards are sorted **alphabetically** for quick lookup;
 * each card shows **league position** (by points, then goal difference) via `positionForTeam`.
 * Data is loaded with `useTeams` (mock today; swap the hook’s implementation for `fetch` later).
 */
import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import { useMemo } from 'react';
import { useTeams } from '../hooks/useTeams';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { FormChart } from '../components/charts/FormChart';
import { TeamBadge } from '../components/common/TeamBadge';
import { GlassPanel } from '../components/common/GlassPanel';
import type { Team } from '../types/team';
import { staggerContainer, staggerItem } from '../styles/motion';

/** 1-based league rank: points descending, then goal difference descending. */
function positionForTeam(teams: Team[], id: string): number {
  const sorted = [...teams].sort((a, b) => {
    const pts = b.stats.points - a.stats.points;
    if (pts !== 0) return pts;
    return b.stats.goalsFor - b.stats.goalsAgainst - (a.stats.goalsFor - a.stats.goalsAgainst);
  });
  return sorted.findIndex((t) => t.id === id) + 1;
}

export function Teams() {
  const { data: teams, loading } = useTeams();
  /** When true, skip staggered and hover motion (accessibility: prefers-reduced-motion). */
  const reduce = useReducedMotion();

  /** Alphabetical list — grid order is independent of league table order. */
  const ordered = useMemo(() => {
    if (!teams) return [];
    return [...teams].sort((a, b) => a.name.localeCompare(b.name));
  }, [teams]);

  /** No-op variants when reduced motion so we don’t animate layout from hidden state. */
  const containerVariants = reduce
    ? { hidden: { opacity: 1 }, show: { opacity: 1 } }
    : staggerContainer;

  const itemVariants = reduce ? { hidden: { opacity: 1 }, show: { opacity: 1 } } : staggerItem;

  if (loading || !teams) {
    return <LoadingSpinner label="Loading teams" />;
  }

  return (
    <div className="space-y-6">
      {/* Page heading: single fade/slide, not part of the staggered grid */}
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        <h1 className="text-3xl font-bold tracking-tight text-[var(--color-text)] sm:text-4xl">Teams</h1>
        <p className="mt-1 max-w-2xl text-[var(--color-text-muted)]">
          Tap a card to explore form, squad depth, and season trends. Hover on desktop for glass lift.
        </p>
      </motion.div>

      {/* Grid: each card links to `/teams/:id` for full profile */}
      <motion.div
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        {ordered.map((t) => {
          const pos = positionForTeam(teams, t.id);
          return (
            <motion.div key={t.id} variants={itemVariants} className="min-h-[100%]">
              <Link to={`/teams/${t.id}`} className="block h-full">
                <GlassPanel
                  className="flex h-full flex-col p-5"
                  elevated
                  whileHover={reduce ? undefined : { y: -6, scale: 1.01 }}
                  transition={{ type: 'spring', stiffness: 380, damping: 28 }}
                >
                  <TeamBadge teamId={t.id} name={t.name} shortLabel={t.shortName} />
                  <div className="mt-4 flex items-end justify-between gap-4">
                    <div>
                      <p className="text-xs text-[var(--color-text-muted)]">Points</p>
                      <p className="font-mono text-2xl font-bold text-[var(--color-text)]">{t.stats.points}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-[var(--color-text-muted)]">Position</p>
                      <p className="font-mono text-2xl font-bold text-[#ffd700]">{pos}</p>
                    </div>
                  </div>
                  <div className="mt-4">
                    <p className="mb-2 text-xs font-medium text-[var(--color-text-muted)]">Last 5</p>
                    {/* Last five W/D/L dots; green / gold / red */}
                    <FormChart results={t.form} maxVisible={5} />
                  </div>
                  <div className="mt-4 flex justify-between text-sm">
                    <span className="text-[var(--color-text-muted)]">GF</span>
                    <span className="font-mono font-semibold text-[#00ff87]">{t.stats.goalsFor}</span>
                    <span className="text-[var(--color-text-muted)]">GA</span>
                    <span className="font-mono font-semibold text-[#ff4757]">{t.stats.goalsAgainst}</span>
                  </div>
                </GlassPanel>
              </Link>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}
