import { useEffect, useMemo, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Goal, CalendarDays, Crosshair, Crown, Sparkles } from 'lucide-react';
import { StatCard } from '../components/common/StatCard';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { Badge } from '../components/common/Badge';
import { GlassPanel } from '../components/common/GlassPanel';
import { PredictionGauge } from '../components/charts/PredictionGauge';
import { PlayerAvatar } from '../components/common/PlayerAvatar';
import { TeamShowcaseStrip } from '../components/showcase/TeamShowcaseStrip';
import { PlayerSpotlightStrip } from '../components/showcase/PlayerSpotlightStrip';
import { useTeams } from '../hooks/useTeams';
import { usePlayers } from '../hooks/usePlayers';
import { useMatches } from '../hooks/useMatches';
import { mockPredictions } from '../data/mockPredictions';
import type { Prediction, PredictionConfidence } from '../types/prediction';
import { fadeUp, staggerContainer, staggerItem } from '../styles/motion';

function confidenceVariant(c: PredictionConfidence): 'success' | 'warning' | 'danger' {
  if (c === 'high') return 'success';
  if (c === 'medium') return 'warning';
  return 'danger';
}

function outcomeLabel(p: Prediction): string {
  if (p.predictedOutcome === 'home') return `${p.homeTeam} win`;
  if (p.predictedOutcome === 'away') return `${p.awayTeam} win`;
  return 'Draw';
}

export function Dashboard() {
  const { data: teams, loading: teamsLoading } = useTeams();
  const { data: players, loading: playersLoading } = usePlayers();
  const { data: matches, loading: matchesLoading } = useMatches();
  const [predictions, setPredictions] = useState<Prediction[] | null>(null);
  const [predLoading, setPredLoading] = useState(true);
  const reduce = useReducedMotion();

  useEffect(() => {
    let cancelled = false;
    const t = window.setTimeout(() => {
      if (!cancelled) {
        const sorted = [...mockPredictions].sort(
          (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
        );
        setPredictions(sorted);
        setPredLoading(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, []);

  const loading = teamsLoading || playersLoading || matchesLoading || predLoading;

  const leagueStats = useMemo(() => {
    if (!teams?.length || !matches?.length || !players?.length) return null;
    const totalGoals = teams.reduce((s, t) => s + t.stats.goalsFor, 0);
    const playedMatches = matches.filter((m) => m.status === 'completed').length;
    const totalXG = teams.reduce((s, t) => s + t.stats.xG, 0);
    const avgXG = playedMatches > 0 ? totalXG / playedMatches : 0;
    const top = [...players].sort((a, b) => b.stats.goals - a.stats.goals)[0];
    return { totalGoals, playedMatches, avgXG, topScorer: top };
  }, [teams, matches, players]);

  const topTeamsShowcase = useMemo(() => {
    if (!teams) return [];
    return [...teams]
      .sort((a, b) => b.stats.points - a.stats.points)
      .slice(0, 8);
  }, [teams]);

  const spotlightPlayers = useMemo(() => {
    if (!players) return [];
    return [...players].sort((a, b) => b.stats.goals - a.stats.goals).slice(0, 8);
  }, [players]);

  if (loading || !leagueStats || !teams || !matches || !players) {
    return <LoadingSpinner label="Loading dashboard" />;
  }

  const topThreePred = predictions?.slice(0, 3) ?? [];
  const recentResults = [...matches]
    .filter((m) => m.status === 'completed')
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .slice(0, 5);
  const topPerformers = [...players].sort((a, b) => b.stats.goals - a.stats.goals).slice(0, 5);

  const gridVariants = reduce
    ? { hidden: { opacity: 1 }, show: { opacity: 1 } }
    : staggerContainer;

  const cardVariants = reduce ? { hidden: { opacity: 1 }, show: { opacity: 1 } } : staggerItem;

  return (
    <div className="space-y-10 lg:space-y-12">
      <motion.section
        className="relative overflow-hidden rounded-3xl border border-white/[0.1] bg-gradient-to-br from-[#37003c]/35 via-white/[0.04] to-transparent p-6 shadow-[0_20px_60px_rgba(0,0,0,0.45)] backdrop-blur-2xl sm:p-8"
        initial={reduce ? false : { opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[#00ff87]/10 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-16 left-10 h-48 w-48 rounded-full bg-[#37003c]/30 blur-3xl" aria-hidden />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <motion.div
              className="mb-2 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.06] px-3 py-1 text-xs font-medium text-[#00ff87] backdrop-blur-md"
              initial={reduce ? false : { opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.1 }}
            >
              <Sparkles className="h-3.5 w-3.5" aria-hidden />
              Live mock season
            </motion.div>
            <h1 className="text-3xl font-bold tracking-tight text-[var(--color-text)] sm:text-4xl">
              Premier League intelligence
            </h1>
            <p className="mt-2 max-w-xl text-[var(--color-text-muted)]">
              Glass dashboards, model probabilities, and form at a glance. Built for the Spring Boot API swap later.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 text-sm text-[var(--color-text-muted)]">
            <span className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 font-mono backdrop-blur-sm">
              {teams.length} teams
            </span>
            <span className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 font-mono backdrop-blur-sm">
              {matches.filter((m) => m.status === 'completed').length} results
            </span>
          </div>
        </div>
      </motion.section>

      <div className="grid gap-4 lg:grid-cols-2">
        <TeamShowcaseStrip teams={topTeamsShowcase} />
        <PlayerSpotlightStrip players={spotlightPlayers} />
      </div>

      <motion.div
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        variants={gridVariants}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={cardVariants}>
          <StatCard
            title="Total goals (season)"
            value={leagueStats.totalGoals}
            subtitle="Across all clubs"
            icon={<Goal className="h-5 w-5" />}
            trend={{ direction: 'up', percent: 4.2 }}
          />
        </motion.div>
        <motion.div variants={cardVariants}>
          <StatCard
            title="Matches played"
            value={leagueStats.playedMatches}
            subtitle="Completed fixtures in dataset"
            icon={<CalendarDays className="h-5 w-5" />}
          />
        </motion.div>
        <motion.div variants={cardVariants}>
          <StatCard
            title="Avg xG / match"
            value={leagueStats.avgXG.toFixed(2)}
            subtitle="League-wide attacking quality"
            icon={<Crosshair className="h-5 w-5" />}
            trend={{ direction: 'up', percent: 1.8 }}
          />
        </motion.div>
        <motion.div variants={cardVariants}>
          <StatCard
            title="Top scorer"
            value={leagueStats.topScorer.stats.goals}
            subtitle={leagueStats.topScorer.name}
            icon={<Crown className="h-5 w-5" />}
          />
        </motion.div>
      </motion.div>

      <section>
        <motion.div className="mb-4" variants={fadeUp} initial="hidden" animate="show">
          <h2 className="text-xl font-bold text-[var(--color-text)]">Upcoming predictions</h2>
          <p className="text-sm text-[var(--color-text-muted)]">Model probabilities for the next kickoffs.</p>
        </motion.div>
        <div className="grid gap-4 lg:grid-cols-3">
          {topThreePred.map((p, i) => (
            <motion.div
              key={p.matchId}
              initial={reduce ? false : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: reduce ? 0 : 0.06 * i, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            >
              <GlassPanel
                className="p-5"
                elevated
                whileHover={reduce ? undefined : { y: -4, scale: 1.01 }}
                transition={{ type: 'spring', stiffness: 380, damping: 26 }}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-lg font-bold text-[var(--color-text)]">
                      {p.homeTeam} <span className="text-[var(--color-text-muted)]">vs</span> {p.awayTeam}
                    </p>
                    <p className="text-xs text-[var(--color-text-muted)]">
                      {new Date(p.date).toLocaleString(undefined, {
                        weekday: 'short',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                  <Badge variant={confidenceVariant(p.confidence)}>{p.confidence} confidence</Badge>
                </div>
                <div className="mt-4">
                  <PredictionGauge
                    homePct={p.homeWinProbability}
                    drawPct={p.drawProbability}
                    awayPct={p.awayWinProbability}
                  />
                  <div className="mt-2 flex flex-wrap justify-between gap-2 text-[10px] font-mono text-[var(--color-text-muted)]">
                    <span className="text-[#00ff87]">H {p.homeWinProbability}%</span>
                    <span className="text-[#ffd700]">D {p.drawProbability}%</span>
                    <span className="text-[#ff4757]">A {p.awayWinProbability}%</span>
                  </div>
                </div>
                <p className="mt-3 text-sm font-semibold text-[#ffd700]">Pick: {outcomeLabel(p)}</p>
              </GlassPanel>
            </motion.div>
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <GlassPanel className="p-5" elevated>
          <h2 className="text-lg font-bold text-[var(--color-text)]">Recent results</h2>
          <ul className="mt-4 space-y-2">
            {recentResults.map((m, i) => (
              <motion.li
                key={m.id}
                initial={reduce ? false : { opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: reduce ? 0 : 0.04 * i }}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/[0.04] bg-black/15 px-3 py-2.5 backdrop-blur-sm"
              >
                <span className="text-sm text-[var(--color-text)]">
                  <span className="font-semibold">{m.homeTeam}</span>{' '}
                  <span className="font-mono text-[#00ff87]">
                    {m.homeGoals} - {m.awayGoals}
                  </span>{' '}
                  <span className="font-semibold">{m.awayTeam}</span>
                </span>
                <span className="text-xs text-[var(--color-text-muted)]">
                  {new Date(m.date).toLocaleDateString()}
                </span>
              </motion.li>
            ))}
          </ul>
        </GlassPanel>

        <GlassPanel className="p-5" elevated>
          <h2 className="text-lg font-bold text-[var(--color-text)]">Top performers</h2>
          <ul className="mt-4 space-y-2">
            {topPerformers.map((pl, i) => (
              <motion.li
                key={pl.id}
                initial={reduce ? false : { opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: reduce ? 0 : 0.04 * i }}
                className="flex items-center gap-3 rounded-xl border border-white/[0.04] bg-black/15 px-3 py-2.5 backdrop-blur-sm"
              >
                <PlayerAvatar name={pl.name} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-[var(--color-text)]">{pl.name}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">{pl.team}</p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-lg font-bold text-[#00ff87]">{pl.stats.goals}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">xG {pl.stats.xG.toFixed(1)}</p>
                </div>
              </motion.li>
            ))}
          </ul>
        </GlassPanel>
      </div>
    </div>
  );
}
