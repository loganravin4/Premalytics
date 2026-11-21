import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { matches, STAGES, STAGE_LABEL, summary } from '../data/wc2026';
import { pct } from '../lib/format';
import { Page } from '../components/Layout';
import { MarkGrid } from '../components/MarkGrid';
import { MatchList } from '../components/MatchRow';

const BINS: [number, number][] = [
  [0.33, 0.4],
  [0.4, 0.5],
  [0.5, 0.6],
  [0.6, 0.7],
  [0.7, 1.01],
];

function Reliability() {
  const rows = BINS.map(([lo, hi]) => {
    const ms = matches.filter((m) => m.pPick >= lo && m.pPick < hi);
    const stated = ms.reduce((s, m) => s + m.pPick, 0) / (ms.length || 1);
    const actual = ms.filter((m) => m.correct).length / (ms.length || 1);
    return { lo, hi, n: ms.length, stated, actual };
  });
  return (
    <table className="w-full border-collapse text-[0.9375rem]">
      <caption className="sr-only">How often the model's pick held, by how sure it was</caption>
      <thead>
        <tr className="running-head border-b-2 border-rule-strong text-left">
          <th className="py-2 font-normal">Confidence</th>
          <th className="py-2 pl-3 text-right font-normal"><span className="sm:hidden">n</span><span className="hidden sm:inline">Matches</span></th>
          <th className="py-2 pl-4 font-normal sm:pl-6">Said</th>
          <th className="py-2 font-normal">Happened</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.lo} className="border-b border-rule">
            <td className="py-3">
              {Math.round(r.lo * 100)}–{Math.min(100, Math.round(r.hi * 100))}%
            </td>
            <td className="py-3 text-right">{r.n}</td>
            <td className="py-3 pl-4 sm:pl-6">
              <span className="inline-flex items-center gap-2">
                <span className="h-2 bg-tint-away" style={{ width: `${r.stated * 4}rem` }} />
                {pct(r.stated)}
              </span>
            </td>
            <td className="py-3">
              <span className="inline-flex items-center gap-2">
                <span className="h-2 bg-spot" style={{ width: `${r.actual * 4}rem` }} />
                <strong>{pct(r.actual)}</strong>
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Section({ title, lede, children }: { title: string; lede?: ReactNode; children: ReactNode }) {
  return (
    <section className="mt-24 grid gap-8 lg:grid-cols-[18rem_minmax(0,1fr)] lg:gap-16">
      <div>
        <h2 className="condensed balance text-[2rem] font-extrabold leading-[1.05]">{title}</h2>
        {lede && <div className="mt-3 max-w-[40ch] text-ink-2">{lede}</div>}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

export function Home() {
  const misses = matches.filter((m) => !m.correct).sort((a, b) => b.pPick - a.pPick).slice(0, 6);
  const brave = matches.filter((m) => m.correct).sort((a, b) => a.pPick - b.pPick).slice(0, 5);
  const draws = matches.filter((m) => m.outcome === 'draw' && m.stage === 'group');
  const drawsCalled = draws.filter((m) => m.correct).length;
  const knockoutMisses = matches.filter((m) => m.stage !== 'group' && !m.correct).length;

  return (
    <Page
      head={
        <>
          <span>International football yearbook · Volume: World Cup 2026</span>
          <span>Every match priced before kickoff · 11 June – 19 July 2026</span>
        </>
      }
    >
      <section className="grid gap-12 pt-10 pb-4 lg:grid-cols-[7fr_5fr] lg:gap-16 lg:pt-14">
        <div>
          <h1 className="sr-only">World Cup 2026: the model's record</h1>
          <p className="display text-[clamp(6rem,22vw,13.5rem)]" aria-hidden>
            {summary.correct}
            <span className="text-spot">/{summary.total}</span>
          </p>
          <p className="balance mt-6 max-w-[34ch] text-[1.3125rem] leading-snug">
            World Cup 2026 matches called, each priced using only results from before the tournament began.
          </p>
          <p className="mt-4 max-w-[52ch] text-ink-2">
            Log loss {summary.logLoss.toFixed(3)} with knockout ties credited to the shootout winner. Scored strictly,
            with a draw as its own outcome, the model managed {pct(summary.raw.gbm.accuracy, 1)} and{' '}
            {summary.raw.gbm.log_loss.toFixed(3)}. {summary.byStage.final.correct ? 'It called the final.' : 'It missed the final.'}
          </p>
        </div>
        <div className="lg:pt-4">
          <table className="w-full border-collapse text-[0.9375rem]">
            <caption className="sr-only">Matches called by stage</caption>
            <thead>
              <tr className="running-head border-b-2 border-rule-strong text-left">
                <th className="py-2 font-normal">Stage</th>
                <th className="py-2 font-normal">
                  <span className="sr-only">Share called</span>
                </th>
                <th className="py-2 text-right font-normal">Called</th>
              </tr>
            </thead>
            <tbody>
              {STAGES.map((s) => {
                const t = summary.byStage[s];
                return (
                  <tr key={s} className="border-b border-rule">
                    <td className="py-2.5 pr-4 whitespace-nowrap">{STAGE_LABEL[s]}</td>
                    <td className="w-full py-2.5">
                      <div className="h-2 w-full max-w-40 bg-tint-draw">
                        <div className="h-full bg-spot" style={{ width: `${t.accuracy * 100}%` }} />
                      </div>
                    </td>
                    <td className="py-2.5 pl-4 text-right font-bold whitespace-nowrap">
                      {t.correct} / {t.total}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <Link to="/wc2026" className="mt-6 inline-flex items-center gap-2 font-semibold text-spot">
            Browse all 104 matches <ArrowRight aria-hidden className="size-4" />
          </Link>
        </div>
      </section>

      <section className="mt-12 border-t-2 border-rule-strong pt-6" aria-labelledby="volume-grid">
        <h2 id="volume-grid" className="running-head mb-5">
          The volume at a glance: every match in date order, by stage
        </h2>
        <MarkGrid />
      </section>

      <Section
        title="Where it was most wrong"
        lede={
          <>
            The model's six most confident misses, {misses.filter((m) => m.outcome === 'draw').length} of them draws.
            It called {drawsCalled} of {draws.length} group-stage draws, because it almost never picks one.
          </>
        }
      >
        <MatchList items={misses} showStage />
      </Section>

      <Section title="Calls against the grain" lede="Correct picks it made with the least confidence.">
        <MatchList items={brave} showStage />
      </Section>

      <Section
        title="Did the percentages mean anything?"
        lede="When the model said 70%, did its pick hold about 70% of the time? Grouped by the confidence it gave its pick."
      >
        <Reliability />
        <p className="mt-4 max-w-[60ch] text-sm text-ink-2">
          Five bins over 104 matches is a small sample; each bin moves several points on one result. The knockout rounds
          held up better than the groups ({knockoutMisses} knockout misses in 32).
        </p>
      </Section>

      <Section title="How it works" lede="Data, features, the train/test split, and the two ways to score a knockout.">
        <Link
          to="/method"
          className="group flex items-center justify-between border-y-2 border-rule-strong py-6 no-underline hover:bg-paper-2"
        >
          <span className="prose-col text-xl">
            A gradient-boosted model trained on {summary.raw.nTrain.toLocaleString('en-US')} international matches,{' '}
            {summary.raw.nFeatures} features per fixture.
          </span>
          <ArrowRight aria-hidden className="mr-2 size-6 shrink-0 text-spot transition-transform group-hover:translate-x-1" />
        </Link>
      </Section>
    </Page>
  );
}
