import { useEffect, useMemo, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { mockPredictions } from '../data/mockPredictions';
import type { Prediction, PredictionConfidence } from '../types/prediction';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { Badge } from '../components/common/Badge';
import { ProgressBar } from '../components/common/ProgressBar';
import { GlassPanel } from '../components/common/GlassPanel';

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

export function Predictions() {
  const [data, setData] = useState<Prediction[] | null>(null);
  const [loading, setLoading] = useState(true);
  const reduce = useReducedMotion();

  useEffect(() => {
    let cancelled = false;
    const t = window.setTimeout(() => {
      if (!cancelled) {
        const sorted = [...mockPredictions].sort(
          (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
        );
        setData(sorted);
        setLoading(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, []);

  const rows = useMemo(() => data ?? [], [data]);

  if (loading || !data) {
    return <LoadingSpinner label="Loading predictions" />;
  }

  return (
    <div className="space-y-10">
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        <h1 className="text-3xl font-bold tracking-tight text-[var(--color-text)] sm:text-4xl">Predictions</h1>
        <p className="mt-2 max-w-3xl text-[var(--color-text-muted)]">
          Premalytics blends rolling team form, expected goals trends, and opponent-adjusted features in a gradient-boosted
          ensemble. Probabilities below are mock outputs shaped like future API payloads—swap the data source when the Spring
          Boot service is live.
        </p>
      </motion.div>

      <div className="space-y-5">
        {rows.map((p, i) => (
          <motion.div
            key={p.matchId}
            initial={reduce ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: reduce ? 0 : 0.04 * i, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          >
            <GlassPanel
              className="p-6"
              elevated
              whileHover={reduce ? undefined : { scale: 1.005, y: -2 }}
              transition={{ type: 'spring', stiffness: 380, damping: 28 }}
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-2xl font-bold tracking-tight text-[var(--color-text)] md:text-3xl">
                    {p.homeTeam} <span className="text-[var(--color-text-muted)]">vs</span> {p.awayTeam}
                  </p>
                  <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                    {new Date(p.date).toLocaleString(undefined, {
                      weekday: 'long',
                      month: 'long',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={confidenceVariant(p.confidence)}>{p.confidence} confidence</Badge>
                  <Badge variant="warning">Pick: {outcomeLabel(p)}</Badge>
                </div>
              </div>

              <div className="mt-6 space-y-4">
                <ProgressBar value={p.homeWinProbability} color="green" label="Home win" />
                <ProgressBar value={p.drawProbability} color="yellow" label="Draw" />
                <ProgressBar value={p.awayWinProbability} color="red" label="Away win" />
              </div>

              <div className="mt-6">
                <p className="text-sm font-semibold text-[var(--color-text)]">Key factors</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--color-text-muted)]">
                  {p.keyFactors.slice(0, 3).map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            </GlassPanel>
          </motion.div>
        ))}
      </div>

      <GlassPanel className="p-6" elevated>
        <h2 className="text-lg font-bold text-[var(--color-text)]">Model accuracy (mock)</h2>
        <p className="text-xs text-[var(--color-text-muted)]">Backtest-style metrics for UI only.</p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: 'Overall', value: '61.4%' },
            { label: 'Home wins', value: '64.2%' },
            { label: 'Away wins', value: '58.8%' },
            { label: 'Draws', value: '52.1%' },
          ].map((m) => (
            <GlassPanel key={m.label} className="p-4">
              <p className="text-xs text-[var(--color-text-muted)]">{m.label}</p>
              <p className="mt-1 font-mono text-2xl font-bold text-[#00ff87]">{m.value}</p>
            </GlassPanel>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}
