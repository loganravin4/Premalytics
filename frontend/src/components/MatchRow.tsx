import { Link } from 'react-router-dom';
import { matchHref, STAGE_SHORT, team, type Match } from '../data/wc2026';
import { shortDate } from '../lib/format';
import { ProbBar } from './ProbBar';
import { Verdict } from './Verdict';

function Score({ m }: { m: Match }) {
  return (
    <span className="condensed text-xl font-extrabold whitespace-nowrap">
      {m.score.home}–{m.score.away}
    </span>
  );
}

/** One ledger line: date, fixture and score, the three-way bar with the result framed, and the verdict. */
export function MatchRow({ m, showStage = false }: { m: Match; showStage?: boolean }) {
  const home = team(m.home), away = team(m.away);
  const pens = m.shootout && m.winner ? `${m.winner} on pens` : null;
  return (
    <li className="border-b border-rule">
      <Link
        to={matchHref(m)}
        className="group grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 py-3 no-underline hover:bg-paper-2 md:grid-cols-[4.5rem_minmax(0,1fr)_minmax(10rem,14rem)_11rem] md:gap-x-6 md:px-2"
      >
        <span className="running-head col-span-2 md:col-span-1">
          {shortDate(m.date)}
          {showStage && <span className="ml-2 md:ml-0 md:block">{STAGE_SHORT[m.stage]}</span>}
        </span>
        <span className="flex min-w-0 items-baseline gap-2 text-[1.0625rem]">
          <span className="truncate font-semibold group-hover:underline">{home.name}</span>
          <Score m={m} />
          <span className="truncate font-semibold group-hover:underline">{away.name}</span>
          {pens && <span className="hidden text-sm text-muted sm:inline">({pens})</span>}
        </span>
        <span className="col-span-2 row-start-3 md:col-span-1 md:row-start-auto">
          <ProbBar match={m} />
        </span>
        <span className="text-right text-sm md:text-left">
          <Verdict match={m} compact />
        </span>
      </Link>
    </li>
  );
}

export function MatchList({ items, showStage }: { items: Match[]; showStage?: boolean }) {
  if (!items.length) return <p className="py-10 text-muted">No matches fit these filters.</p>;
  return (
    <ul className="border-t-2 border-rule-strong">
      {items.map((m) => (
        <MatchRow key={m.id} m={m} showStage={showStage} />
      ))}
    </ul>
  );
}
