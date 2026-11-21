import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { matches, summary } from '../data/wc2026';
import { BACKTEST, PREVIOUS_MODEL_WC2026 as PREV } from '../data/backtest';
import { pct } from '../lib/format';
import { Page } from '../components/Layout';

const SECTIONS = [
  { id: 'data', title: 'The data' },
  { id: 'model', title: 'The model' },
  { id: 'test', title: 'How it was tested' },
  { id: 'backtest', title: 'Twenty-seven tournaments' },
  { id: 'knockouts', title: 'Scoring a knockout' },
  { id: 'results', title: 'World Cup 2026, both ways' },
  { id: 'limits', title: 'Where it fails' },
  { id: 'correction', title: 'Correction' },
  { id: 'next', title: 'What comes next' },
];

function H2({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h2 id={id} className="condensed mt-16 mb-4 scroll-mt-8 font-sans text-[1.875rem] leading-tight font-extrabold">
      {children}
    </h2>
  );
}

function Th({ children, right }: { children: ReactNode; right?: boolean }) {
  return <th className={`py-2 font-normal ${right ? 'pl-4 text-right' : ''}`}>{children}</th>;
}

export function Method() {
  const draws = matches.filter((m) => m.stage === 'group' && m.outcome === 'draw');
  const groupN = matches.filter((m) => m.stage === 'group').length;
  const bt = BACKTEST;
  return (
    <Page
      head={
        <>
          <span>Method</span>
          <span>Model run {summary.modelRunId}</span>
        </>
      }
    >
      <div className="grid gap-12 pt-10 lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-16">
        <nav aria-label="On this page" className="lg:sticky lg:top-6 lg:self-start">
          <p className="running-head mb-3">On this page</p>
          <ol className="flex flex-wrap gap-x-5 gap-y-1 text-[0.9375rem] lg:flex-col">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a href={`#${s.id}`} className="no-underline hover:underline">
                  {s.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <article className="min-w-0">
          <h1 className="condensed balance text-[clamp(2.5rem,7vw,4.5rem)] leading-none font-extrabold">
            How the model works, and where it doesn't
          </h1>
          <div className="prose-col mt-8">
            <p>
              Neutral Ground gives every international match three probabilities: home win, draw, away win. For World
              Cup 2026 it priced all 104 matches using only results from before the tournament began, then kept score.
              This page explains what went in, how it was checked, and what the numbers do and don't show.
            </p>

            <H2 id="data">The data</H2>
            <p>
              The training set is {summary.raw.nTrain.toLocaleString('en-US')} international matches: friendlies,
              qualifiers, and tournaments, built from the open martj42 international results dataset and supplemented
              with FBref match statistics (via the soccerdata library) for World Cups and European Championships.
              Friendlies count for less than competitive matches.
            </p>

            <H2 id="model">The model</H2>
            <p>
              Two models are blended. Most of the weight, {pct(1 - bt.blend.gbmWeight)}, goes to a{' '}
              <strong>Dixon-Coles score model</strong>. It rates each team's attack and defense from the last{' '}
              {bt.blend.dcWindowYears} years of results ({bt.blend.dcMatches.toLocaleString('en-US')} matches), with
              recent matches counting more, then works out how likely every scoreline is. Adding up the scorelines gives
              home win, draw, and away win. It also includes a small correction that makes 0–0 and 1–1 slightly more
              likely than two independent goal counts would suggest.
            </p>
            <p>
              The other {pct(bt.blend.gbmWeight)} comes from a <strong>gradient-boosted tree model</strong> that sees{' '}
              {summary.raw.nFeatures} numbers per fixture, all from matches played strictly before it:
            </p>
            <ul className="mt-4 list-disc space-y-1.5 pl-6">
              <li>Elo rating for each team, and the gap between them.</li>
              <li>Recent form over the last 3, 5, and 10 matches: points, wins, goals for and against.</li>
              <li>Expected goals for and against, where match-level xG exists.</li>
              <li>Shots, shots on target, possession, and passing where FBref has them.</li>
              <li>Head-to-head record over the last five meetings.</li>
              <li>Confederation, rest days, and whether the venue is neutral.</li>
            </ul>
            <p className="mt-4">
              The blend is then sharpened slightly (temperature {bt.blend.temperature.toFixed(2)}). The blend weight and
              that last step were chosen only from tournaments that finished before World Cup 2026.
            </p>

            <H2 id="test">How it was tested</H2>
            <p>
              The split is by date, never random. Everything before 11 June 2026 trains the model; the tournament is
              the test. Every team's form is frozen at that date, so the knockout rounds were priced with the same
              pre-tournament information as the opening match.
            </p>

            <H2 id="backtest">Twenty-seven tournaments</H2>
            <p>
              One tournament is a small test, so the same procedure was replayed on every World Cup, European
              Championship, Copa América, Africa Cup of Nations, Asian Cup, and Gold Cup from {bt.from} to {bt.to}:{' '}
              {bt.tournaments} tournaments and {bt.matches.toLocaleString('en-US')} matches. Each one was priced by a
              model trained only on matches before its first game.
            </p>
            <p>
              The main score is the ranked probability score (RPS), the standard for home/draw/away forecasts. It
              rewards putting probability near the right outcome. Lower is better.
            </p>
          </div>
          <div className="mt-6 w-full max-w-[44rem] overflow-x-auto">
            <table className="w-full min-w-[30rem] border-collapse text-[0.9375rem]">
              <caption className="sr-only">Pooled results over {bt.tournaments} tournaments</caption>
              <thead>
                <tr className="running-head border-b-2 border-rule-strong text-left">
                  <Th>Model</Th>
                  <Th right>RPS</Th>
                  <Th right>Log loss</Th>
                  <Th right>Accuracy</Th>
                </tr>
              </thead>
              <tbody>
                {bt.rows.map((r) => (
                  <tr key={r.label} className={`border-b border-rule ${r.served ? 'font-bold' : ''}`}>
                    <td className="py-2.5">{r.label}</td>
                    <td className="py-2.5 pl-4 text-right">{r.rps.toFixed(4)}</td>
                    <td className="py-2.5 pl-4 text-right">{r.logLossRaw.toFixed(3)}</td>
                    <td className="py-2.5 pl-4 text-right">{pct(r.accuracy, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="prose-col mt-6">
            <p>
              The blend beats the plain Elo model by {Math.abs(bt.vsElo.delta).toFixed(4)} RPS (95% interval{' '}
              {Math.abs(bt.vsElo.hi).toFixed(4)} to {Math.abs(bt.vsElo.lo).toFixed(4)}) and beats the previous model in{' '}
              {bt.blendWinsOverGbm} of {bt.tournaments} tournaments. The margins are small. The previous model, with all
              its features, did no better than Elo alone.
            </p>

            <H2 id="knockouts">Scoring a knockout</H2>
            <p>
              A knockout match can't end in a draw. Two scoring modes follow from that, and every headline number on
              this site says which one it uses.
            </p>
            <ul className="mt-4 list-disc space-y-1.5 pl-6">
              <li>
                <strong>Strict:</strong> the raw model output, where a draw is a valid outcome in every match and a
                shootout counts as a draw. This is the honest benchmark for the model itself.
              </li>
              <li>
                <strong>Shootout-credited:</strong> in knockouts, the draw probability is split between the two teams,
                and a match level after extra time counts for the team that won the shootout. This is how a fan would
                score the picks.
              </li>
            </ul>

            <H2 id="results">World Cup 2026, both ways</H2>
          </div>
          <div className="mt-2 w-full max-w-[44rem] overflow-x-auto">
            <table className="w-full min-w-[28rem] border-collapse text-[0.9375rem]">
              <caption className="sr-only">Accuracy and log loss on World Cup 2026</caption>
              <thead>
                <tr className="running-head border-b-2 border-rule-strong text-left">
                  <Th>Model</Th>
                  <Th right>Accuracy</Th>
                  <Th right>Log loss</Th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-rule font-bold">
                  <td className="py-2.5">Blend, shootout-credited</td>
                  <td className="py-2.5 pl-4 text-right">
                    {pct(summary.correct / summary.total, 1)} ({summary.correct}/{summary.total})
                  </td>
                  <td className="py-2.5 pl-4 text-right">{summary.logLoss.toFixed(3)}</td>
                </tr>
                <tr className="border-b border-rule">
                  <td className="py-2.5">Blend, strict</td>
                  <td className="py-2.5 pl-4 text-right">{pct(summary.raw.strict.accuracy, 1)}</td>
                  <td className="py-2.5 pl-4 text-right">{summary.raw.strict.log_loss.toFixed(3)}</td>
                </tr>
                <tr className="border-b border-rule text-ink-2">
                  <td className="py-2.5">Previous model, shootout-credited</td>
                  <td className="py-2.5 pl-4 text-right">
                    {pct(PREV.correct / PREV.total, 1)} ({PREV.correct}/{PREV.total})
                  </td>
                  <td className="py-2.5 pl-4 text-right">{PREV.logLossCredited.toFixed(3)}</td>
                </tr>
                <tr className="border-b border-rule text-ink-2">
                  <td className="py-2.5">Previous model, strict</td>
                  <td className="py-2.5 pl-4 text-right">{pct(PREV.accuracyStrict, 1)}</td>
                  <td className="py-2.5 pl-4 text-right">{PREV.logLossStrict.toFixed(3)}</td>
                </tr>
                <tr className="border-b border-rule text-muted">
                  <td className="py-2.5">Guessing a third each</td>
                  <td className="py-2.5 pl-4 text-right">—</td>
                  <td className="py-2.5 pl-4 text-right">1.099</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="prose-col mt-6">
            <p>
              On this tournament the blend gave better probabilities (lower log loss) but made{' '}
              {PREV.correct - summary.correct} fewer correct picks than the previous model. Log loss punishes confident misses
              hard, so it is the fairer comparison; a count of correct picks swings on a handful of close matches.
            </p>

            <H2 id="limits">Where it fails</H2>
            <ul className="list-disc space-y-3 pl-6">
              <li>
                <strong>It never picks a draw.</strong> {draws.length} of {groupN} group matches were drawn. A draw is
                almost never the single most likely outcome, so its worst misses are 0–0s and 2–2s between a favorite
                and an outsider. What did improve is the pricing: across the {bt.tournaments} tournaments the blend
                gives draws {pct(bt.draws.blendMean, 1)} on average against {pct(bt.draws.actual, 1)} that happened.
              </li>
              <li>
                <strong>Small margins.</strong> The blend's lead over simple baselines is real but slight, and one
                tournament can swing several points on a handful of results.
              </li>
              <li>
                <strong>No bookmaker comparison.</strong> No free source of closing odds covers international matches.
              </li>
              <li>
                <strong>No lineups.</strong> Probabilities are frozen before kickoff without team news, so injuries and
                rotation aren't seen.
              </li>
            </ul>

            <H2 id="correction">Correction</H2>
            <p>
              An earlier version of this site reported 72 of 104 (69%). That run built each match's features from the
              latest data on file, which included results from later in the tournament, so it was not a true
              pre-tournament forecast. Rerun with every team's form frozen at 11 June 2026, that model called{' '}
              {PREV.correct} of {PREV.total}. The site now shows the blended model, which replaced it in November 2026.
            </p>

            <H2 id="next">What comes next</H2>
            <p>
              Work in progress: calibration checks, a shot-level expected-goals lab, a penalties study, and future
              volumes for the next international tournaments once their fixtures are set.
            </p>
            <p>
              Browse the record: <Link to="/wc2026?view=all">all 104 matches</Link>, or start with{' '}
              <Link to="/">the volume</Link>.
            </p>
          </div>
        </article>
      </div>
    </Page>
  );
}
