import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import { useTeams } from '../hooks/useTeams';
import { usePlayers } from '../hooks/usePlayers';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { FormChart } from '../components/charts/FormChart';
import { GoalsChart } from '../components/charts/GoalsChart';
import { Badge } from '../components/common/Badge';
import { GlassPanel } from '../components/common/GlassPanel';
import type { Player } from '../types/player';

type SquadSortKey = 'goals' | 'assists' | 'xg' | 'minutes';

export function TeamDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: teams, loading: teamsLoading } = useTeams();
  const { data: players, loading: playersLoading } = usePlayers();
  const [sortKey, setSortKey] = useState<SquadSortKey>('goals');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const reduce = useReducedMotion();

  const team = useMemo(() => teams?.find((t) => t.id === id), [teams, id]);

  const squad = useMemo(() => {
    if (!players || !id) return [];
    return players.filter((p) => p.teamId === id);
  }, [players, id]);

  const sortedSquad = useMemo(() => {
    const mult = sortDir === 'desc' ? -1 : 1;
    const keyFn = (p: Player) => {
      if (sortKey === 'goals') return p.stats.goals;
      if (sortKey === 'assists') return p.stats.assists;
      if (sortKey === 'xg') return p.stats.xG;
      return p.stats.minutes;
    };
    return [...squad].sort((a, b) => mult * (keyFn(a) - keyFn(b)));
  }, [squad, sortKey, sortDir]);

  const position = useMemo(() => {
    if (!teams || !team) return 0;
    const sorted = [...teams].sort((a, b) => {
      const pts = b.stats.points - a.stats.points;
      if (pts !== 0) return pts;
      return b.stats.goalsFor - b.stats.goalsAgainst - (a.stats.goalsFor - a.stats.goalsAgainst);
    });
    return sorted.findIndex((t) => t.id === team.id) + 1;
  }, [teams, team]);

  function toggleSort(k: SquadSortKey) {
    if (sortKey === k) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    else {
      setSortKey(k);
      setSortDir('desc');
    }
  }

  if (teamsLoading || playersLoading || !teams || !players) {
    return <LoadingSpinner label="Loading team" />;
  }

  if (!team) {
    return (
      <GlassPanel className="p-8 text-center" elevated>
        <p className="text-[var(--color-text)]">Team not found.</p>
        <Link to="/teams" className="mt-4 inline-block text-[#00ff87] hover:underline">
          Back to teams
        </Link>
      </GlassPanel>
    );
  }

  const monthly = team.monthlyGoals ?? [];

  return (
    <div className="space-y-8">
      <GlassPanel className="p-6 sm:p-8" elevated>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm text-[var(--color-text-muted)]">
              <Link to="/teams" className="hover:text-[#00ff87]">
                Teams
              </Link>{' '}
              / {team.name}
            </p>
            <h1 className="mt-2 flex flex-wrap items-center gap-3 text-3xl font-bold tracking-tight text-[var(--color-text)]">
              <motion.span
                className="text-4xl"
                aria-hidden
                initial={reduce ? false : { scale: 0.85, rotate: -6 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ type: 'spring', stiffness: 260, damping: 18 }}
                whileHover={reduce ? undefined : { scale: 1.08, rotate: [0, -4, 4, 0] }}
              >
                {team.badge}
              </motion.span>
              {team.name}
            </h1>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge variant="primary">
                {team.stats.wins}W {team.stats.draws}D {team.stats.losses}L
              </Badge>
              <Badge variant="success">{team.stats.points} pts</Badge>
              <Badge variant="warning">#{position} in table</Badge>
            </div>
          </div>
        </div>
      </GlassPanel>

      <GlassPanel className="p-5" elevated>
        <h2 className="text-lg font-bold text-[var(--color-text)]">Form (last 10)</h2>
        <p className="text-xs text-[var(--color-text-muted)]">Interactive dots — hover each result.</p>
        <div className="mt-4">
          <FormChart results={team.form} maxVisible={10} />
        </div>
      </GlassPanel>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {[
          { label: 'Goals', value: team.stats.goalsFor, color: 'text-[#00ff87]' },
          { label: 'xG', value: team.stats.xG.toFixed(1), color: 'text-[var(--color-text)]' },
          { label: 'xGA', value: team.stats.xGA.toFixed(1), color: 'text-[#ff4757]' },
          { label: 'Clean sheets', value: team.cleanSheets ?? 0, color: 'text-[var(--color-text)]' },
          { label: 'Red cards', value: team.redCards ?? 0, color: 'text-[#ffd700]' },
        ].map((s) => (
          <GlassPanel
            key={s.label}
            className="p-4"
            whileHover={reduce ? undefined : { y: -3 }}
            transition={{ type: 'spring', stiffness: 400, damping: 26 }}
          >
            <p className="text-xs text-[var(--color-text-muted)]">{s.label}</p>
            <p className={`mt-1 font-mono text-2xl font-bold ${s.color}`}>{s.value}</p>
          </GlassPanel>
        ))}
      </section>

      <GlassPanel className="p-5" elevated>
        <h2 className="text-lg font-bold text-[var(--color-text)]">Goals by month</h2>
        <div className="mt-4">
          <GoalsChart data={monthly} />
        </div>
      </GlassPanel>

      <GlassPanel className="p-5" elevated>
        <h2 className="text-lg font-bold text-[var(--color-text)]">Squad</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-[var(--color-border)] text-xs uppercase text-[var(--color-text-muted)]">
              <tr>
                <th className="py-2 pr-4 font-semibold">Player</th>
                <th className="py-2 pr-4 font-semibold">Pos</th>
                <th className="py-2 pr-4">
                  <button type="button" className="font-semibold hover:text-[#00ff87]" onClick={() => toggleSort('goals')}>
                    Goals {sortKey === 'goals' ? (sortDir === 'desc' ? 'v' : '^') : ''}
                  </button>
                </th>
                <th className="py-2 pr-4">
                  <button type="button" className="font-semibold hover:text-[#00ff87]" onClick={() => toggleSort('assists')}>
                    Ast {sortKey === 'assists' ? (sortDir === 'desc' ? 'v' : '^') : ''}
                  </button>
                </th>
                <th className="py-2 pr-4">
                  <button type="button" className="font-semibold hover:text-[#00ff87]" onClick={() => toggleSort('xg')}>
                    xG {sortKey === 'xg' ? (sortDir === 'desc' ? 'v' : '^') : ''}
                  </button>
                </th>
                <th className="py-2">
                  <button type="button" className="font-semibold hover:text-[#00ff87]" onClick={() => toggleSort('minutes')}>
                    Min {sortKey === 'minutes' ? (sortDir === 'desc' ? 'v' : '^') : ''}
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedSquad.map((p, i) => (
                <motion.tr
                  key={p.id}
                  initial={reduce ? false : { opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: reduce ? 0 : 0.02 * i }}
                  className="border-b border-white/[0.06] transition-colors hover:bg-white/[0.03]"
                >
                  <td className="py-2 pr-4">
                    <Link to={`/players/${p.id}`} className="font-medium text-[var(--color-text)] hover:text-[#00ff87]">
                      {p.name}
                    </Link>
                  </td>
                  <td className="py-2 pr-4 text-[var(--color-text-muted)]">{p.position}</td>
                  <td className="py-2 pr-4 font-mono text-[#00ff87]">{p.stats.goals}</td>
                  <td className="py-2 pr-4 font-mono">{p.stats.assists}</td>
                  <td className="py-2 pr-4 font-mono">{p.stats.xG.toFixed(1)}</td>
                  <td className="py-2 font-mono">{p.stats.minutes}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassPanel>
    </div>
  );
}
