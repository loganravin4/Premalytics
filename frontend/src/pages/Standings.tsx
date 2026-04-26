import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import { useTeams } from '../hooks/useTeams';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { FormChart } from '../components/charts/FormChart';
import { TeamBadge } from '../components/common/TeamBadge';
import { GlassPanel } from '../components/common/GlassPanel';
import type { Team } from '../types/team';
import type { Standing } from '../types/standing';

function buildStandings(teams: Team[]): Standing[] {
  const sorted = [...teams].sort((a, b) => {
    const pts = b.stats.points - a.stats.points;
    if (pts !== 0) return pts;
    const gdA = a.stats.goalsFor - a.stats.goalsAgainst;
    const gdB = b.stats.goalsFor - b.stats.goalsAgainst;
    return gdB - gdA;
  });
  return sorted.map((t, i) => ({
    position: i + 1,
    teamId: t.id,
    played: t.stats.played,
    wins: t.stats.wins,
    draws: t.stats.draws,
    losses: t.stats.losses,
    goalsFor: t.stats.goalsFor,
    goalsAgainst: t.stats.goalsAgainst,
    goalDifference: t.stats.goalsFor - t.stats.goalsAgainst,
    points: t.stats.points,
    form: t.form.slice(-5),
  }));
}

function rowAccent(position: number, total: number): string {
  if (position <= 4) return 'border-l-4 border-l-[#00ff87]/70';
  if (position === 5) return 'border-l-4 border-l-[#ffd700]/80';
  if (position > total - 3) return 'border-l-4 border-l-[#ff4757]/80';
  return 'border-l-4 border-l-transparent';
}

export function Standings() {
  const { data: teams, loading } = useTeams();
  const reduce = useReducedMotion();

  const table = useMemo(() => (teams ? buildStandings(teams) : []), [teams]);
  const teamMap = useMemo(() => {
    const m = new Map<string, Team>();
    teams?.forEach((t) => m.set(t.id, t));
    return m;
  }, [teams]);

  if (loading || !teams) {
    return <LoadingSpinner label="Loading standings" />;
  }

  const total = table.length;

  return (
    <div className="space-y-6">
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      >
        <h1 className="text-3xl font-bold tracking-tight text-[var(--color-text)] sm:text-4xl">Standings</h1>
        <p className="mt-1 text-[var(--color-text-muted)]">Live table order from mock season data.</p>
      </motion.div>

      <GlassPanel className="overflow-x-auto p-0" elevated>
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-[var(--color-border)] bg-[var(--color-surface-elevated)]/80 text-xs uppercase tracking-wide text-[var(--color-text-muted)]">
            <tr>
              <th className="px-3 py-3 font-semibold">Pos</th>
              <th className="px-3 py-3 font-semibold">Team</th>
              <th className="px-3 py-3 font-semibold">Pld</th>
              <th className="px-3 py-3 font-semibold">W</th>
              <th className="px-3 py-3 font-semibold">D</th>
              <th className="px-3 py-3 font-semibold">L</th>
              <th className="px-3 py-3 font-semibold">GF</th>
              <th className="px-3 py-3 font-semibold">GA</th>
              <th className="px-3 py-3 font-semibold">GD</th>
              <th className="px-3 py-3 font-semibold">Pts</th>
              <th className="px-3 py-3 font-semibold">Form</th>
            </tr>
          </thead>
          <tbody>
            {table.map((row, i) => {
              const t = teamMap.get(row.teamId);
              if (!t) return null;
              return (
                <motion.tr
                  key={row.teamId}
                  initial={reduce ? false : { opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: reduce ? 0 : 0.015 * i }}
                  className={`border-b border-white/[0.06] transition-colors duration-200 hover:bg-white/[0.04] ${rowAccent(row.position, total)}`}
                >
                  <td className="px-3 py-3 font-mono font-bold text-[var(--color-text)]">{row.position}</td>
                  <td className="px-3 py-3">
                    <Link to={`/teams/${t.id}`} className="block hover:opacity-90">
                      <TeamBadge teamId={t.id} name={t.name} shortLabel={t.shortName} />
                    </Link>
                  </td>
                  <td className="px-3 py-3 font-mono text-[var(--color-text)]">{row.played}</td>
                  <td className="px-3 py-3 font-mono text-[var(--color-text)]">{row.wins}</td>
                  <td className="px-3 py-3 font-mono text-[var(--color-text)]">{row.draws}</td>
                  <td className="px-3 py-3 font-mono text-[var(--color-text)]">{row.losses}</td>
                  <td className="px-3 py-3 font-mono text-[#00ff87]">{row.goalsFor}</td>
                  <td className="px-3 py-3 font-mono text-[#ff4757]">{row.goalsAgainst}</td>
                  <td className="px-3 py-3 font-mono text-[var(--color-text)]">
                    {row.goalDifference > 0 ? `+${row.goalDifference}` : row.goalDifference}
                  </td>
                  <td className="px-3 py-3 font-mono text-lg font-bold text-[var(--color-text)]">{row.points}</td>
                  <td className="px-3 py-3">
                    <FormChart results={row.form} maxVisible={5} />
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </GlassPanel>
    </div>
  );
}
