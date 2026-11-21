import type { Match, Outcome } from '../data/wc2026';
import { pct, strikeWeight } from '../lib/format';

const FILL: Record<Outcome, string> = {
  home: 'bg-spot',
  draw: 'bg-tint-draw',
  away: 'bg-tint-away',
};

interface Props {
  match: Match;
  size?: 'row' | 'large';
  labels?: boolean;
}

/**
 * The three-way split, home / draw / away, with the actual result marked over its segment.
 * Meaning never rides on color alone: segment order is fixed and the result carries an ink frame.
 */
export function ProbBar({ match, size = 'row', labels = false }: Props) {
  const order: Outcome[] = ['home', 'draw', 'away'];
  const segs = order.filter((o) => match.p[o] > 0);
  const h = size === 'large' ? 'h-9' : 'h-2.5';
  const desc = order
    .filter((o) => match.p[o] > 0)
    .map((o) => `${o === 'draw' ? 'draw' : o === 'home' ? `${match.home} win` : `${match.away} win`} ${pct(match.p[o])}`)
    .join(', ');

  return (
    <div className="w-full">
      <div role="img" aria-label={`Model: ${desc}. Result: ${match.outcome === 'draw' ? 'draw' : `${match.outcome} win`}.`} className={`relative flex w-full ${h} gap-px`}>
        {segs.map((o) => {
          const isResult = o === match.outcome;
          return (
            <div key={o} className={`relative ${FILL[o]}`} style={{ width: `${match.p[o] * 100}%` }}>
              {!match.correct && o === match.pick && (
                <span
                  aria-hidden
                  className="absolute inset-x-0 top-1/2 -translate-y-1/2 bg-ink"
                  style={{ height: `${strikeWeight(match.pPick, size === 'large' ? 10 : 6)}px` }}
                />
              )}
              {isResult && (
                <span
                  aria-hidden
                  className={`absolute ${size === 'large' ? '-inset-1 border-[3px]' : '-inset-[3px] border-2'} border-ink`}
                />
              )}
            </div>
          );
        })}
      </div>
      {labels && (
        <div className="mt-2 flex w-full text-sm" aria-hidden>
          {segs.map((o) => (
            <div key={o} className="w-1/3 min-w-0 sm:w-[var(--w)]" style={{ ['--w' as string]: `${match.p[o] * 100}%` }}>
              <span className={`block truncate pr-2 ${o === match.outcome ? 'font-bold text-ink' : 'text-muted'}`}>
                {o === 'draw' ? 'Draw' : o === 'home' ? match.home : match.away} {pct(match.p[o], 1)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
