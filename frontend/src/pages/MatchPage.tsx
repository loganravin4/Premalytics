import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { matches, matchFromSlug, matchHref, sideTeam, STAGE_LABEL, team, type Match, type Outcome } from '../data/wc2026';
import { longDate, pct, strikeWeight } from '../lib/format';
import { Page } from '../components/Layout';
import { ProbBar } from '../components/ProbBar';
import { NotFound } from './NotFound';

function outcomeName(m: Match, o: Outcome) {
  const code = sideTeam(m, o);
  return code ? `${team(code).name} win` : 'Draw';
}

function resultSentence(m: Match) {
  if (m.shootout && m.winner) return `${team(m.winner).name} went through on penalties`;
  const code = sideTeam(m, m.outcome);
  return code ? `${team(code).name} won` : 'It finished level';
}

function missStrength(m: Match) {
  if (m.pPick >= 0.65) return 'A confident miss.';
  if (m.pPick - m.pActual < 0.1) return 'Close to a coin flip, and it fell the other way.';
  return 'A clear miss.';
}

export function MatchPage() {
  const { slug = '' } = useParams();
  const m = matchFromSlug(slug);
  if (!m) return <NotFound />;
  const home = team(m.home), away = team(m.away);
  const i = matches.indexOf(m);
  const prev = matches[i - 1], next = matches[i + 1];
  const knockout = m.stage !== 'group';
  const outcomes: Outcome[] = ['home', 'draw', 'away'];

  return (
    <Page
      head={
        <>
          <Link to="/wc2026" className="no-underline hover:text-ink">
            Volume: World Cup 2026 · {STAGE_LABEL[m.stage]}
          </Link>
          <span>
            {longDate(m.date)}
            {m.neutral ? ' · neutral venue' : ' · host nation at home'}
          </span>
        </>
      }
    >
      <article className="pt-10">
        <h1 className="grid grid-cols-[1fr_auto_1fr] items-baseline gap-x-4 sm:gap-x-8">
          <Link to={`/nations/${m.home.toLowerCase()}`} className="condensed text-right text-[clamp(1.75rem,5.5vw,4rem)] leading-none font-extrabold no-underline hover:underline">
            {home.name}
          </Link>
          <span className="display text-[clamp(3.5rem,11vw,8rem)]">
            {m.score.home}
            <span className="mx-[0.08em] font-normal tracking-normal text-ink-2">–</span>
            {m.score.away}
          </span>
          <Link to={`/nations/${m.away.toLowerCase()}`} className="condensed text-[clamp(1.75rem,5.5vw,4rem)] leading-none font-extrabold no-underline hover:underline">
            {away.name}
          </Link>
        </h1>
        {m.shootout && m.winner && (
          <p className="mt-3 text-center text-ink-2">{team(m.winner).name} won on penalties</p>
        )}

        <section className="mx-auto mt-14 max-w-4xl" aria-labelledby="split">
          <h2 id="split" className="running-head mb-4">
            The model's split before the tournament
          </h2>
          <ProbBar match={m} size="large" labels />
          <p className="balance mt-8 max-w-[52ch] text-[1.3125rem] leading-snug">
            The model backed{' '}
            {m.correct ? (
              <strong className="text-spot">{sideTeam(m, m.pick) ? team(sideTeam(m, m.pick)!).name : 'a draw'}</strong>
            ) : (
              <strong className="struck" style={{ ['--strike' as string]: `${strikeWeight(m.pPick, 4)}px` }}>
                {sideTeam(m, m.pick) ? team(sideTeam(m, m.pick)!).name : 'a draw'}
              </strong>
            )}{' '}
            at {pct(m.pPick, 1)}. {resultSentence(m)}
            {m.correct ? '.' : `, an outcome it gave ${pct(m.pActual, 1)}. ${missStrength(m)}`}
          </p>
        </section>

        <section className="mx-auto mt-14 grid max-w-4xl gap-10 md:grid-cols-2" aria-label="Details">
          <table className="w-full border-collapse text-[0.9375rem]">
            <caption className="running-head mb-2 text-left">Probabilities</caption>
            <tbody>
              {outcomes.map((o) => (
                <tr key={o} className="border-t border-rule">
                  <th scope="row" className="py-2.5 text-left font-normal">
                    {outcomeName(m, o)}
                    {o === m.outcome && <span className="ml-2 font-semibold">(result)</span>}
                  </th>
                  <td className="py-2.5 text-right font-bold">
                    {knockout && o === 'draw' ? '—' : pct(m.p[o], 1)}
                  </td>
                </tr>
              ))}
              <tr className="border-t border-rule">
                <th scope="row" className="py-2.5 text-left font-normal">
                  Log loss on this match
                </th>
                <td className="py-2.5 text-right font-bold">{(-Math.log(Math.max(m.pActual, 1e-6))).toFixed(3)}</td>
              </tr>
            </tbody>
          </table>
          <div className="text-[0.9375rem] text-ink-2">
            <p className="running-head mb-2">Reading this match</p>
            {knockout ? (
              <p>
                Knockout matches cannot end in a draw, so the model's draw probability was split between the two teams.
                A match level after extra time is credited to the team that won the shootout.
              </p>
            ) : (
              <p>
                Group matches can end level, so the draw is its own outcome. Log loss is −ln of the probability given to
                the result: lower is better, and 1.099 is what guessing a third each would score.
              </p>
            )}
          </div>
        </section>

        <nav aria-label="Adjacent matches" className="mx-auto mt-16 grid max-w-4xl grid-cols-2 gap-4 border-t-2 border-rule-strong pt-4 text-sm">
          {prev ? (
            <Link to={matchHref(prev)} className="group flex items-start gap-2 no-underline">
              <ArrowLeft aria-hidden className="mt-0.5 size-4 shrink-0 text-spot" />
              <span>
                <span className="running-head block">Previous</span>
                <span className="group-hover:underline">
                  {team(prev.home).name} – {team(prev.away).name}
                </span>
              </span>
            </Link>
          ) : (
            <span />
          )}
          {next && (
            <Link to={matchHref(next)} className="group flex items-start justify-end gap-2 text-right no-underline">
              <span>
                <span className="running-head block">Next</span>
                <span className="group-hover:underline">
                  {team(next.home).name} – {team(next.away).name}
                </span>
              </span>
              <ArrowRight aria-hidden className="mt-0.5 size-4 shrink-0 text-spot" />
            </Link>
          )}
        </nav>
      </article>
    </Page>
  );
}
