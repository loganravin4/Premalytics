import { Link, useParams } from 'react-router-dom';
import { CONFEDERATIONS, STAGES, STAGE_LABEL, team, teamMatches, teams, type Stage } from '../data/wc2026';
import { pct } from '../lib/format';
import { Page } from '../components/Layout';
import { MatchList } from '../components/MatchRow';
import { NotFound } from './NotFound';

function furthest(code: string): Stage {
  const ms = teamMatches(code);
  return ms.reduce<Stage>((best, m) => (STAGES.indexOf(m.stage) > STAGES.indexOf(best) ? m.stage : best), 'group');
}

function finish(code: string): string {
  const ms = teamMatches(code);
  const final = ms.find((m) => m.stage === 'final');
  if (final) return final.winner === code ? 'Champions' : 'Runners-up';
  const third = ms.find((m) => m.stage === 'third_place');
  if (third) return third.winner === code ? 'Third place' : 'Fourth place';
  const s = furthest(code);
  return s === 'group' ? 'Out in the groups' : `Out in the ${STAGE_LABEL[s].toLowerCase()}`;
}

const CONF_ORDER = ['UEFA', 'CONMEBOL', 'CONCACAF', 'CAF', 'AFC', 'OFC', 'OTHER'];

export function Nations() {
  return (
    <Page
      head={
        <>
          <span>Volume: World Cup 2026</span>
          <span>48 nations, by confederation</span>
        </>
      }
    >
      <h1 className="condensed mt-10 text-[clamp(2.5rem,7vw,4.5rem)] leading-none font-extrabold">Nations</h1>
      <p className="mt-4 max-w-[60ch] text-ink-2">
        How far each team went, and how often the model read their matches correctly.
      </p>
      <div className="mt-12 grid gap-x-16 gap-y-14 lg:grid-cols-2">
        {CONF_ORDER.map((conf) => {
          const list = teams.filter((t) => t.confederation === conf);
          if (!list.length) return null;
          return (
            <section key={conf}>
              <h2 className="running-head border-b-2 border-rule-strong pb-2">{CONFEDERATIONS[conf]}</h2>
              <ul>
                {list.map((t) => {
                  const ms = teamMatches(t.code);
                  const called = ms.filter((m) => m.correct).length;
                  return (
                    <li key={t.code} className="border-b border-rule">
                      <Link
                        to={`/nations/${t.code.toLowerCase()}`}
                        className="grid grid-cols-[3rem_minmax(0,1fr)_auto] items-baseline gap-3 py-2.5 no-underline hover:bg-paper-2 sm:grid-cols-[3rem_minmax(0,1fr)_10rem_5rem]"
                      >
                        <span className="condensed font-extrabold text-muted">{t.code}</span>
                        <span className="truncate font-semibold">{t.name}</span>
                        <span className="hidden text-sm text-ink-2 sm:block">{finish(t.code)}</span>
                        <span className="text-right text-sm">
                          <strong>{called}</strong>/{ms.length} called
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>
    </Page>
  );
}

export function Nation() {
  const { code = '' } = useParams();
  const t = teams.find((x) => x.code === code.toUpperCase());
  if (!t) return <NotFound />;
  const ms = teamMatches(t.code);
  const called = ms.filter((m) => m.correct).length;
  const meanGiven = ms.reduce((s, m) => s + m.pActual, 0) / ms.length;
  const favored = ms.filter((m) => (m.home === t.code ? m.p.home : m.p.away) > Math.max(m.p.draw, m.home === t.code ? m.p.away : m.p.home)).length;

  return (
    <Page
      head={
        <>
          <Link to="/nations" className="no-underline hover:text-ink">
            Nations · {CONFEDERATIONS[t.confederation]} · {t.code}
          </Link>
          <span>Volume: World Cup 2026</span>
        </>
      }
    >
      <div className="grid gap-10 pt-10 lg:grid-cols-[7fr_5fr] lg:items-end">
        <div>
          <h1 className="display text-[clamp(3.5rem,12vw,9rem)]">{team(t.code).name}</h1>
          <p className="mt-5 text-[1.3125rem]">{finish(t.code)}.</p>
        </div>
        <dl className="grid grid-cols-3 gap-px border-y-2 border-rule-strong">
          <div className="py-4 pr-3">
            <dt className="running-head">Matches called</dt>
            <dd className="condensed mt-1 text-3xl font-extrabold">
              {called}/{ms.length}
            </dd>
          </div>
          <div className="py-4 pr-3">
            <dt className="running-head">Favored in</dt>
            <dd className="condensed mt-1 text-3xl font-extrabold">{favored}</dd>
          </div>
          <div className="py-4">
            <dt className="running-head">Avg. given to result</dt>
            <dd className="condensed mt-1 text-3xl font-extrabold">{pct(meanGiven)}</dd>
          </div>
        </dl>
      </div>
      <h2 className="running-head mt-16 mb-3">Their tournament, match by match</h2>
      <MatchList items={ms} showStage />
    </Page>
  );
}
