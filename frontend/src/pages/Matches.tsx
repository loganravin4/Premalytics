import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Search } from 'lucide-react';
import { groups, matches, matchHref, STAGES, STAGE_LABEL, STAGE_SHORT, team, type Match, type Stage } from '../data/wc2026';
import { pct, shortDate } from '../lib/format';
import { Page } from '../components/Layout';
import { MatchList } from '../components/MatchRow';
import { ProbBar } from '../components/ProbBar';
import { Verdict } from '../components/Verdict';

type View = 'groups' | 'knockouts' | 'all';
const VIEWS: { id: View; label: string }[] = [
  { id: 'groups', label: 'Groups' },
  { id: 'knockouts', label: 'Knockouts' },
  { id: 'all', label: 'All matches' },
];
const byId = new Map(matches.map((m) => [m.id, m]));

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { id: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap border-b border-rule">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={value === o.id}
          onClick={() => onChange(o.id)}
          className={`-mb-px border-b-2 px-3 py-2.5 text-[0.9375rem] font-semibold first:pl-0 ${
            value === o.id ? 'border-spot text-spot' : 'border-transparent text-ink-2 hover:text-ink'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- Groups ---------- */

function standings(codes: string[], ms: Match[]) {
  return codes
    .map((code) => {
      let w = 0, d = 0, l = 0, gf = 0, ga = 0, xp = 0;
      for (const m of ms) {
        if (m.home !== code && m.away !== code) continue;
        const isHome = m.home === code;
        const f = isHome ? m.score.home : m.score.away;
        const a = isHome ? m.score.away : m.score.home;
        gf += f;
        ga += a;
        if (f > a) w++;
        else if (f === a) d++;
        else l++;
        xp += 3 * (isHome ? m.p.home : m.p.away) + m.p.draw;
      }
      return { code, w, d, l, gf, ga, pts: 3 * w + d, xp };
    })
    .sort((a, b) => b.pts - a.pts || b.gf - b.ga - (a.gf - a.ga) || b.gf - a.gf);
}

function GroupsView() {
  return (
    <>
    <p className="-mt-4 mb-10 max-w-[60ch] text-sm text-ink-2">
      Exp. pts is what the model expected each team to take from its three group matches: three times its win chance plus
      its draw chance, summed.
    </p>
    <div className="grid gap-x-16 gap-y-16 xl:grid-cols-2">
      {groups.map((g) => {
        const ms = g.matchIds.map((id) => byId.get(id)!);
        const table = standings(g.teams, ms);
        const called = ms.filter((m) => m.correct).length;
        return (
          <section key={g.teams.join()} aria-label={`Group of ${table.map((t) => team(t.code).name).join(', ')}`}>
            <div className="flex items-baseline justify-between border-b-2 border-rule-strong pb-2">
              <h3 className="condensed text-xl font-extrabold">{table.map((t) => t.code).join(' · ')}</h3>
              <span className="running-head">
                called <span className="text-ink">{called}/6</span>
              </span>
            </div>
            <table className="w-full border-collapse text-[0.9375rem]">
              <thead>
                <tr className="running-head text-right">
                  <th className="py-2 text-left font-normal">Team</th>
                  <th className="py-2 font-normal" title="Won">W</th>
                  <th className="py-2 font-normal" title="Drawn">D</th>
                  <th className="py-2 font-normal" title="Lost">L</th>
                  <th className="hidden py-2 font-normal sm:table-cell">Goals</th>
                  <th className="py-2 font-normal">Pts</th>
                  <th className="py-2 pl-3 font-normal" title="Points the model expected from its pre-tournament probabilities: 3 × win chance + draw chance, summed over the three matches">
                    Exp. pts
                  </th>
                </tr>
              </thead>
              <tbody>
                {table.map((t, i) => (
                  <tr key={t.code} className={`border-t border-rule text-right ${i < 2 ? 'font-semibold' : ''}`}>
                    <td className="py-2 text-left">
                      <Link to={`/nations/${t.code.toLowerCase()}`} className="no-underline hover:underline">
                        {team(t.code).name}
                      </Link>
                    </td>
                    <td className="py-2">{t.w}</td>
                    <td className="py-2">{t.d}</td>
                    <td className="py-2">{t.l}</td>
                    <td className="hidden py-2 sm:table-cell">
                      {t.gf}–{t.ga}
                    </td>
                    <td className="py-2 font-bold">{t.pts}</td>
                    <td className="py-2 pl-3 font-normal text-muted">{t.xp.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ul className="mt-4 border-t border-rule">
              {ms.map((m) => (
                <li key={m.id} className="border-b border-rule">
                  <Link
                    to={matchHref(m)}
                    className="grid grid-cols-[3.5rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 py-2 text-sm no-underline hover:bg-paper-2 sm:grid-cols-[3.5rem_minmax(0,1fr)_7rem_auto]"
                  >
                    <span className="text-muted">{shortDate(m.date)}</span>
                    <span className="truncate">
                      {m.home} <strong>{m.score.home}–{m.score.away}</strong> {m.away}
                    </span>
                    <span className="col-span-3 row-start-2 sm:col-span-1 sm:row-start-auto">
                      <ProbBar match={m} />
                    </span>
                    <span className="col-start-3 row-start-1 sm:col-start-auto sm:row-start-auto">
                      <Verdict match={m} compact />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
    </>
  );
}

/* ---------- Knockouts ---------- */

const ROUNDS: Stage[] = ['round_of_32', 'round_of_16', 'quarter_final', 'semi_final', 'final'];

/** Orders each round so every match sits beside the two matches that fed it. */
function bracketOrder(): Match[][] {
  const final = matches.find((m) => m.stage === 'final');
  if (!final) return ROUNDS.map((s) => matches.filter((m) => m.stage === s));
  const cols: Match[][] = [[final]];
  for (let r = ROUNDS.length - 2; r >= 0; r--) {
    const prev = matches.filter((m) => m.stage === ROUNDS[r]);
    const next = cols[0];
    const ordered: Match[] = [];
    for (const m of next) {
      for (const code of [m.home, m.away]) {
        const feeder = prev.find((p) => p.winner === code);
        if (feeder) ordered.push(feeder);
      }
    }
    for (const p of prev) if (!ordered.includes(p)) ordered.push(p);
    cols.unshift(ordered);
  }
  return cols;
}

function BracketMatch({ m }: { m: Match }) {
  const line = (code: string, goals: number) => (
    <span className={`flex justify-between gap-2 ${m.winner === code ? 'font-bold' : 'text-ink-2'}`}>
      <span className="truncate">{team(code).name}</span>
      <span>{goals}</span>
    </span>
  );
  return (
    <Link
      to={matchHref(m)}
      className="block border border-rule bg-paper px-3 py-2 text-sm no-underline hover:border-rule-strong"
      aria-label={`${team(m.home).name} ${m.score.home}–${m.score.away} ${team(m.away).name}${
        m.shootout ? `, ${team(m.winner!).name} on penalties` : ''
      }. ${m.correct ? 'Called' : 'Missed'}.`}
    >
      {line(m.home, m.score.home)}
      {line(m.away, m.score.away)}
      <span className="mt-2 block">
        <ProbBar match={m} />
      </span>
      <span className="mt-1.5 flex justify-between text-xs">
        <Verdict match={m} compact />
        {m.shootout && <span className="text-muted">pens</span>}
      </span>
    </Link>
  );
}

function KnockoutsView() {
  const cols = bracketOrder();
  const third = matches.find((m) => m.stage === 'third_place');
  return (
    <div>
      <div className="relative -mx-4 overflow-x-auto px-4 pt-1 pb-4 sm:-mx-8 sm:px-8 lg:mx-0 lg:px-0">
        <ol className="grid min-w-[64rem] grid-cols-5 gap-4">
          {cols.map((col, ci) => (
            <li key={ROUNDS[ci]} className="flex flex-col">
              <h3 className="running-head mb-3 border-b-2 border-rule-strong pb-2">
                {STAGE_LABEL[ROUNDS[ci]]}{' '}
                <span className="text-ink">
                  {col.filter((m) => m.correct).length}/{col.length}
                </span>
              </h3>
              <ul className="flex flex-1 flex-col justify-around gap-2">
                {col.map((m) => (
                  <li key={m.id}>
                    <BracketMatch m={m} />
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      </div>
      {third && (
        <div className="mt-10 max-w-xs">
          <h3 className="running-head mb-3 border-b-2 border-rule-strong pb-2">Third place</h3>
          <BracketMatch m={third} />
        </div>
      )}
    </div>
  );
}

/* ---------- All matches ---------- */

type CallFilter = 'any' | 'called' | 'missed';

function AllView() {
  const [params, setParams] = useSearchParams();
  const stage = (params.get('stage') ?? 'any') as Stage | 'any';
  const call = (params.get('call') ?? 'any') as CallFilter;
  const q = params.get('q') ?? '';
  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (!v || v === 'any') next.delete(k);
    else next.set(k, v);
    setParams(next, { replace: true });
  };
  const items = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return matches.filter(
      (m) =>
        (stage === 'any' || m.stage === stage) &&
        (call === 'any' || (call === 'called') === m.correct) &&
        (!needle ||
          [m.home, m.away, team(m.home).name, team(m.away).name].some((s) => s.toLowerCase().includes(needle))),
    );
  }, [stage, call, q]);
  const calledN = items.filter((m) => m.correct).length;

  return (
    <div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:gap-8">
          <Segmented
            label="Stage"
            value={stage}
            onChange={(v) => set('stage', v)}
            options={[{ id: 'any' as const, label: 'Every stage' }, ...STAGES.map((s) => ({ id: s, label: STAGE_SHORT[s] }))]}
          />
          <Segmented
            label="Model's call"
            value={call}
            onChange={(v) => set('call', v)}
            options={[
              { id: 'any' as const, label: 'Any call' },
              { id: 'called' as const, label: 'Called' },
              { id: 'missed' as const, label: 'Missed' },
            ]}
          />
        </div>
        <label className="flex items-center gap-2 border-b-2 border-rule-strong py-1.5 focus-within:border-spot">
          <Search aria-hidden className="size-4 text-muted" />
          <span className="sr-only">Find a nation</span>
          <input
            type="search"
            value={q}
            onChange={(e) => set('q', e.target.value)}
            placeholder="Find a nation"
            className="w-full bg-transparent text-base outline-none placeholder:text-muted lg:w-56"
          />
        </label>
      </div>
      <p className="running-head mt-6 mb-3" aria-live="polite">
        {items.length} {items.length === 1 ? 'match' : 'matches'} · {calledN} called
        {items.length > 0 && ` (${pct(calledN / items.length)})`}
      </p>
      <MatchList items={items} showStage />
    </div>
  );
}

export function Matches() {
  const [params, setParams] = useSearchParams();
  const view = (VIEWS.some((v) => v.id === params.get('view')) ? params.get('view') : 'groups') as View;
  return (
    <Page
      head={
        <>
          <span>Volume: World Cup 2026</span>
          <span>104 matches · 48 nations</span>
        </>
      }
    >
      <h1 className="condensed mt-10 text-[clamp(2.5rem,7vw,4.5rem)] leading-none font-extrabold">The matches</h1>
      <p className="mt-4 max-w-[60ch] text-ink-2">
        Each bar is the model's pre-tournament split: home win, draw, away win, left to right. The framed segment is what
        happened. In the knockouts the model splits only between the two teams, and a tie goes to the shootout winner.
      </p>
      <div className="mt-8 mb-10">
        <Segmented
          label="View"
          value={view}
          onChange={(v) => {
            const next = new URLSearchParams();
            if (v !== 'groups') next.set('view', v);
            setParams(next);
          }}
          options={VIEWS}
        />
      </div>
      {view === 'groups' && <GroupsView />}
      {view === 'knockouts' && <KnockoutsView />}
      {view === 'all' && <AllView />}
    </Page>
  );
}
