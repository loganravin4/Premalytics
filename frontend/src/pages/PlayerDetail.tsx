import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import {
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';
import { usePlayers } from '../hooks/usePlayers';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { Badge } from '../components/common/Badge';
import { GlassPanel } from '../components/common/GlassPanel';
import { theme } from '../styles/theme';

const defaultRadar = [
  { subject: 'Finishing', value: 60 },
  { subject: 'Creativity', value: 60 },
  { subject: 'Pressing', value: 60 },
  { subject: 'Progression', value: 60 },
  { subject: 'Defending', value: 60 },
];

const defaultSeasons = [
  { season: '20/21', xG: 4 },
  { season: '21/22', xG: 5 },
  { season: '22/23', xG: 6 },
  { season: '23/24', xG: 7 },
  { season: '24/25', xG: 8 },
];

export function PlayerDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: players, loading } = usePlayers();
  const reduce = useReducedMotion();

  const player = useMemo(() => players?.find((p) => p.id === id), [players, id]);

  const radarData = useMemo(() => {
    if (!player?.radarScores) return defaultRadar;
    const r = player.radarScores;
    return [
      { subject: 'Finishing', value: r.finishing },
      { subject: 'Creativity', value: r.creativity },
      { subject: 'Pressing', value: r.pressing },
      { subject: 'Progression', value: r.progression },
      { subject: 'Defending', value: r.defending },
    ];
  }, [player]);

  const lineData = player?.seasonXGHistory ?? defaultSeasons;

  const shots = player?.shotMap ?? [
    { x: 82, y: 48 },
    { x: 88, y: 44 },
    { x: 85, y: 52 },
  ];

  if (loading || !players) {
    return <LoadingSpinner label="Loading player" />;
  }

  if (!player) {
    return (
      <GlassPanel className="p-8 text-center" elevated>
        <p className="text-[var(--color-text)]">Player not found.</p>
        <Link to="/players" className="mt-4 inline-block text-[#00ff87] hover:underline">
          Back to players
        </Link>
      </GlassPanel>
    );
  }

  return (
    <div className="space-y-8">
      <GlassPanel className="p-6 sm:p-8" elevated>
        <p className="text-sm text-[var(--color-text-muted)]">
          <Link to="/players" className="hover:text-[#00ff87]">
            Players
          </Link>{' '}
          / {player.name}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-bold tracking-tight text-[var(--color-text)] sm:text-4xl">{player.name}</h1>
          <Badge variant="primary">{player.position}</Badge>
          <motion.span
            className="text-2xl"
            title={player.nationality}
            initial={reduce ? false : { scale: 0.85, rotate: -8 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: 'spring', stiffness: 280, damping: 18 }}
            whileHover={reduce ? undefined : { scale: 1.12 }}
          >
            {player.flagEmoji ?? '🏳️'}
          </motion.span>
          <span className="text-sm text-[var(--color-text-muted)]">Age {player.age}</span>
        </div>
        <p className="mt-2 text-[var(--color-text-muted)]">
          <Link to={`/teams/${player.teamId}`} className="font-medium text-[#00ff87] hover:underline">
            {player.team}
          </Link>
        </p>
      </GlassPanel>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {[
          { label: 'Goals', value: player.stats.goals },
          { label: 'Assists', value: player.stats.assists },
          { label: 'xG', value: player.stats.xG.toFixed(1) },
          { label: 'xAG', value: player.stats.xAG.toFixed(1) },
          { label: 'Minutes', value: player.stats.minutes },
        ].map((s, i) => (
          <GlassPanel
            key={s.label}
            className="p-5"
            initial={reduce ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: reduce ? 0 : 0.04 * i }}
            whileHover={reduce ? undefined : { y: -3, scale: 1.02 }}
          >
            <p className="text-xs text-[var(--color-text-muted)]">{s.label}</p>
            <p className="mt-2 font-mono text-3xl font-bold text-[var(--color-text)]">{s.value}</p>
          </GlassPanel>
        ))}
      </div>

      <section className="grid gap-6 lg:grid-cols-2">
        <GlassPanel className="p-5" elevated>
          <h2 className="text-lg font-bold text-[var(--color-text)]">Performance profile</h2>
          <p className="text-xs text-[var(--color-text-muted)]">Normalized 0-100 scouting-style axes.</p>
          <div className="mt-4 h-72 w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                <PolarGrid stroke={theme.colors.chartGrid} />
                <PolarAngleAxis dataKey="subject" tick={{ fill: theme.colors.chartAxis, fontSize: 11 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: theme.colors.chartAxis, fontSize: 10 }} />
                <Radar
                  name={player.name}
                  dataKey="value"
                  stroke={theme.colors.green}
                  fill={theme.colors.green}
                  fillOpacity={0.35}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const row = payload[0].payload as { subject: string; value: number };
                    return (
                      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs text-[var(--color-text)] shadow-xl">
                        <p className="font-semibold">{row.subject}</p>
                        <p className="font-mono text-[#00ff87]">{row.value}</p>
                      </div>
                    );
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </GlassPanel>

        <GlassPanel className="p-5" elevated>
          <h2 className="text-lg font-bold text-[var(--color-text)]">Shot map (mock)</h2>
          <p className="text-xs text-[var(--color-text-muted)]">Attacking half placeholder with static dots.</p>
          <div className="relative mt-4 h-56 w-full overflow-hidden rounded-xl border border-[var(--color-border)] bg-gradient-to-br from-[#0f3d2a] via-[#0a0e1a] to-[#0a0e1a]">
            <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full" preserveAspectRatio="none" aria-hidden>
              <rect x="8" y="10" width="84" height="80" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="0.4" strokeDasharray="2 2" rx="1" />
              {shots.map((pt, i) => (
                <circle key={`${pt.x}-${pt.y}-${i}`} cx={pt.x} cy={pt.y} r="2.2" className="fill-[#ff4757]" />
              ))}
            </svg>
            <p className="absolute bottom-2 left-3 text-[10px] text-white/50">Attacking direction up</p>
          </div>
        </GlassPanel>
      </section>

      <GlassPanel className="p-5" elevated>
        <h2 className="text-lg font-bold text-[var(--color-text)]">Season xG trend</h2>
        <p className="text-xs text-[var(--color-text-muted)]">Mock five-season cumulative xG.</p>
        <div className="mt-4 h-64 w-full min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={lineData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={theme.colors.chartGrid} strokeDasharray="3 3" />
              <XAxis dataKey="season" tick={{ fill: theme.colors.chartAxis, fontSize: 11 }} />
              <YAxis tick={{ fill: theme.colors.chartAxis, fontSize: 11 }} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const row = payload[0].payload as { season: string; xG: number };
                  return (
                    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs text-[var(--color-text)] shadow-xl">
                      <p className="font-semibold">{row.season}</p>
                      <p className="font-mono text-[#ffd700]">{row.xG} xG</p>
                    </div>
                  );
                }}
              />
              <Line type="monotone" dataKey="xG" stroke={theme.colors.yellow} strokeWidth={2} dot={{ r: 4 }} name="xG" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </GlassPanel>
    </div>
  );
}
