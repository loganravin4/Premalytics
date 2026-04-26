import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import { usePlayers } from '../hooks/usePlayers';
import { useTeams } from '../hooks/useTeams';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { GlassPanel } from '../components/common/GlassPanel';
import type { Player } from '../types/player';

type SortCol = 'name' | 'team' | 'position' | 'goals' | 'assists' | 'xg' | 'xag' | 'minutes' | 'apps';

export function Players() {
  const { data: players, loading: plLoading } = usePlayers();
  const { data: teams, loading: tmLoading } = useTeams();
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [pos, setPos] = useState<string>('All');
  const [teamId, setTeamId] = useState<string>('All');
  const [sortCol, setSortCol] = useState<SortCol>('goals');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const reduce = useReducedMotion();

  const teamOptions = useMemo(() => {
    if (!teams) return [];
    return [...teams].sort((a, b) => a.name.localeCompare(b.name));
  }, [teams]);

  const filtered = useMemo(() => {
    if (!players) return [];
    return players.filter((p) => {
      const matchQ = p.name.toLowerCase().includes(q.trim().toLowerCase());
      const matchPos = pos === 'All' || p.position === pos;
      const matchTeam = teamId === 'All' || p.teamId === teamId;
      return matchQ && matchPos && matchTeam;
    });
  }, [players, q, pos, teamId]);

  const sorted = useMemo(() => {
    const m = sortDir === 'desc' ? -1 : 1;
    const val = (p: Player): string | number => {
      switch (sortCol) {
        case 'name':
          return p.name.toLowerCase();
        case 'team':
          return p.team.toLowerCase();
        case 'position':
          return p.position;
        case 'goals':
          return p.stats.goals;
        case 'assists':
          return p.stats.assists;
        case 'xg':
          return p.stats.xG;
        case 'xag':
          return p.stats.xAG;
        case 'minutes':
          return p.stats.minutes;
        case 'apps':
          return p.stats.appearances;
        default:
          return 0;
      }
    };
    return [...filtered].sort((a, b) => {
      const va = val(a);
      const vb = val(b);
      if (typeof va === 'number' && typeof vb === 'number') return m * (va - vb);
      return m * String(va).localeCompare(String(vb));
    });
  }, [filtered, sortCol, sortDir]);

  function headerBtn(col: SortCol, label: string) {
    const active = sortCol === col;
    return (
      <button
        type="button"
        className={`font-semibold hover:text-[#00ff87] ${active ? 'text-[#00ff87]' : ''}`}
        onClick={() => {
          if (sortCol === col) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
          else {
            setSortCol(col);
            setSortDir(col === 'name' || col === 'team' || col === 'position' ? 'asc' : 'desc');
          }
        }}
      >
        {label}
        {active ? (sortDir === 'desc' ? ' v' : ' ^') : ''}
      </button>
    );
  }

  if (plLoading || tmLoading || !players || !teams) {
    return <LoadingSpinner label="Loading players" />;
  }

  return (
    <div className="space-y-6">
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      >
        <h1 className="text-3xl font-bold tracking-tight text-[var(--color-text)] sm:text-4xl">Players</h1>
        <p className="mt-1 text-[var(--color-text-muted)]">Search, filter, and sort the full mock player pool.</p>
      </motion.div>

      <GlassPanel className="flex flex-col gap-3 p-4 sm:flex-row sm:flex-wrap sm:items-end sm:p-5">
        <label className="flex min-w-[200px] flex-1 flex-col gap-1 text-xs text-[var(--color-text-muted)]">
          Search name
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-3 py-2 text-sm text-[var(--color-text)] outline-none transition-colors duration-200 focus:border-[#37003c]/60"
            placeholder="e.g. Salah"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--color-text-muted)]">
          Position
          <select
            value={pos}
            onChange={(e) => setPos(e.target.value)}
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-3 py-2 text-sm text-[var(--color-text)] outline-none transition-colors duration-200 focus:border-[#37003c]/60"
          >
            {['All', 'FW', 'MF', 'DF', 'GK'].map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-[200px] flex-col gap-1 text-xs text-[var(--color-text-muted)]">
          Team
          <select
            value={teamId}
            onChange={(e) => setTeamId(e.target.value)}
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-3 py-2 text-sm text-[var(--color-text)] outline-none transition-colors duration-200 focus:border-[#37003c]/60"
          >
            <option value="All">All teams</option>
            {teamOptions.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
      </GlassPanel>

      <GlassPanel className="overflow-x-auto p-0" elevated>
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="border-b border-[var(--color-border)] bg-[var(--color-surface-elevated)]/80 text-xs uppercase tracking-wide text-[var(--color-text-muted)]">
            <tr>
              <th className="px-3 py-3">{headerBtn('name', 'Name')}</th>
              <th className="px-3 py-3">{headerBtn('team', 'Team')}</th>
              <th className="px-3 py-3">{headerBtn('position', 'Pos')}</th>
              <th className="px-3 py-3">{headerBtn('goals', 'Goals')}</th>
              <th className="px-3 py-3">{headerBtn('assists', 'Assists')}</th>
              <th className="px-3 py-3">{headerBtn('xg', 'xG')}</th>
              <th className="px-3 py-3">{headerBtn('xag', 'xAG')}</th>
              <th className="px-3 py-3">{headerBtn('minutes', 'Minutes')}</th>
              <th className="px-3 py-3">{headerBtn('apps', 'Apps')}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p, i) => (
              <motion.tr
                key={p.id}
                initial={reduce ? false : { opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: reduce ? 0 : 0.012 * Math.min(i, 24) }}
                className="cursor-pointer border-b border-white/[0.06] transition-colors duration-200 hover:bg-white/[0.04]"
                onClick={() => navigate(`/players/${p.id}`)}
              >
                <td className="px-3 py-3 font-medium text-[var(--color-text)]">{p.name}</td>
                <td className="px-3 py-3 text-[var(--color-text-muted)]">{p.team}</td>
                <td className="px-3 py-3 font-mono text-[var(--color-text)]">{p.position}</td>
                <td className="px-3 py-3 font-mono text-[#00ff87]">{p.stats.goals}</td>
                <td className="px-3 py-3 font-mono">{p.stats.assists}</td>
                <td className="px-3 py-3 font-mono">{p.stats.xG.toFixed(1)}</td>
                <td className="px-3 py-3 font-mono">{p.stats.xAG.toFixed(1)}</td>
                <td className="px-3 py-3 font-mono">{p.stats.minutes}</td>
                <td className="px-3 py-3 font-mono">{p.stats.appearances}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </GlassPanel>
    </div>
  );
}
