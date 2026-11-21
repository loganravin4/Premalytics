import { useState } from 'react';
import { Link } from 'react-router-dom';
import { matches, matchHref, STAGES, STAGE_SHORT, team, type Match } from '../data/wc2026';
import { pct, shortDate, strikeWeight } from '../lib/format';

function label(m: Match) {
  return `${shortDate(m.date)}: ${team(m.home).name} ${m.score.home}–${m.score.away} ${team(m.away).name}. ${
    m.correct ? 'Called' : 'Missed'
  }, model's pick at ${pct(m.pPick)}.`;
}

export function MarkGrid() {
  const [active, setActive] = useState<Match | null>(null);
  let i = 0;
  return (
    <div>
      <div className="flex flex-wrap items-end gap-x-3 gap-y-5 sm:gap-x-5 xl:justify-between">
        {STAGES.map((s) => {
          const ms = matches.filter((m) => m.stage === s);
          const called = ms.filter((m) => m.correct).length;
          return (
            <div key={s} className="flex flex-col gap-2">
              <ol
                className="grid grid-flow-col grid-rows-6 gap-[2px] sm:gap-1"
                aria-label={`${STAGE_SHORT[s]}: ${called} of ${ms.length} called`}
              >
                {ms.map((m) => {
                  const idx = i++;
                  return (
                    <li key={m.id}>
                      <Link
                        to={matchHref(m)}
                        aria-label={label(m)}
                        onMouseEnter={() => setActive(m)}
                        onFocus={() => setActive(m)}
                        onMouseLeave={() => setActive(null)}
                        onBlur={() => setActive(null)}
                        className={`ink-in relative block size-[22px] border-[1.5px] border-ink sm:size-6 lg:size-9 xl:size-12 ${
                          m.correct ? 'bg-ink hover:bg-spot hover:border-spot' : 'bg-paper hover:bg-paper-2'
                        }`}
                        style={{ ['--i' as string]: idx }}
                      >
                        {!m.correct && (
                          <svg aria-hidden viewBox="0 0 10 10" className="absolute inset-0 size-full" preserveAspectRatio="none">
                            <line
                              x1="0"
                              y1="10"
                              x2="10"
                              y2="0"
                              stroke="currentColor"
                              vectorEffect="non-scaling-stroke"
                              style={{ strokeWidth: `${strikeWeight(m.pPick)}px` }}
                            />
                          </svg>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ol>
              <span className="running-head whitespace-nowrap">
                {STAGE_SHORT[s]} <span className="text-ink">{called}/{ms.length}</span>
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-5 min-h-12 text-sm text-ink-2 sm:min-h-6" aria-live="polite">
        {active ? (
          label(active)
        ) : (
          <>
            Solid: called. Struck: missed, with a heavier stroke the surer the model was. Each mark opens its match.
          </>
        )}
      </p>
    </div>
  );
}
