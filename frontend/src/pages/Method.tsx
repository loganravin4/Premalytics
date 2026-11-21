import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { matches, summary } from '../data/wc2026';
import { pct } from '../lib/format';
import { Page } from '../components/Layout';

const SECTIONS = [
  { id: 'data', title: 'The data' },
  { id: 'features', title: 'What the model sees' },
  { id: 'test', title: 'How it was tested' },
  { id: 'knockouts', title: 'Scoring a knockout' },
  { id: 'results', title: 'The numbers, both ways' },
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

export function Method() {
  const draws = matches.filter((m) => m.stage === 'group' && m.outcome === 'draw');
  const groupN = matches.filter((m) => m.stage === 'group').length;
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
        <article>
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
              Friendlies count for less than competitive matches during training.
            </p>
            <p>
              Each fixture is stored twice, once from each team's side, so every feature is computed the same way for
              home and away.
            </p>

            <H2 id="features">What the model sees</H2>
            <p>
              {summary.raw.nFeatures} numbers per fixture, all computed from matches played strictly before it. The main
              families:
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
              Two models are trained on these: a logistic regression and a gradient-boosted tree ensemble. The
              gradient-boosted model is the one shown across the site.
            </p>

            <H2 id="test">How it was tested</H2>
            <p>
              The split is by date, never random. Everything before 11 June 2026 trains the model; the tournament is
              the test. No result from the tournament feeds back into any prediction, including the knockout rounds,
              which were priced with the same pre-tournament information.
            </p>

            <H2 id="knockouts">Scoring a knockout</H2>
            <p>
              A knockout match can't end in a draw. Two scoring modes follow from that, and every headline number on
              this site says which one it uses.
            </p>
            <ul className="mt-4 list-disc space-y-1.5 pl-6">
              <li>
                <strong>Strict:</strong> the raw model output, where a draw is a valid outcome in every match. This is
                the honest benchmark for the model itself.
              </li>
              <li>
                <strong>Shootout-credited:</strong> in knockouts, the draw probability is split between the two teams,
                and a match level after extra time counts for the team that won the shootout. This is how a fan would
                score the picks.
              </li>
            </ul>

            <H2 id="results">The numbers, both ways</H2>
          </div>
          <table className="mt-2 w-full max-w-[44rem] border-collapse text-[0.9375rem]">
            <caption className="sr-only">Accuracy and log loss on World Cup 2026</caption>
            <thead>
              <tr className="running-head border-b-2 border-rule-strong text-left">
                <th className="py-2 font-normal">Model</th>
                <th className="py-2 text-right font-normal">Accuracy</th>
                <th className="py-2 text-right font-normal">Log loss</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-rule">
                <td className="py-2.5">Gradient-boosted, shootout-credited</td>
                <td className="py-2.5 text-right font-bold">
                  {pct(summary.correct / summary.total, 1)} ({summary.correct}/{summary.total})
                </td>
                <td className="py-2.5 text-right font-bold">{summary.logLoss.toFixed(3)}</td>
              </tr>
              <tr className="border-b border-rule">
                <td className="py-2.5">Gradient-boosted, strict</td>
                <td className="py-2.5 text-right">{pct(summary.raw.gbm.accuracy, 1)}</td>
                <td className="py-2.5 text-right">{summary.raw.gbm.log_loss.toFixed(3)}</td>
              </tr>
              <tr className="border-b border-rule text-muted">
                <td className="py-2.5">Guessing a third each</td>
                <td className="py-2.5 text-right">—</td>
                <td className="py-2.5 text-right">1.099</td>
              </tr>
            </tbody>
          </table>
          <div className="prose-col mt-6">
            <p>
              Log loss rewards putting high probability on what actually happened and punishes confident misses hard.
              The shootout-credited figure is lower partly because knockout matches lose their draw outcome; compare
              models on the strict numbers.
            </p>

            <H2 id="limits">Where it fails</H2>
            <ul className="list-disc space-y-3 pl-6">
              <li>
                <strong>Draws.</strong> {draws.length} of {groupN} group matches were drawn. The model's highest draw
                probability rarely tops its favorite, so it almost never picks one, and its worst misses are 0–0s and
                2–2s between a favorite and an outsider.
              </li>
              <li>
                <strong>One tournament is a small test.</strong> 104 matches can swing several points on a handful of
                results.
              </li>
              <li>
                <strong>It doesn't beat a simple baseline.</strong> Replayed over 27 tournaments from 2014 to 2026,
                this model does no better than a plain Elo model with two inputs. A score-based model that beats both is
                next. There is no bookmaker comparison: no free source of closing odds covers international matches.
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
              pre-tournament forecast. The numbers here come from a rerun that freezes every team's form at 11 June
              2026.
            </p>

            <H2 id="next">What comes next</H2>
            <p>
              Work in progress: a score model built to price draws properly, calibration checks, a shot-level
              expected-goals lab, and a penalties study. Future volumes will cover the
              next international tournaments once their fixtures are set.
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
