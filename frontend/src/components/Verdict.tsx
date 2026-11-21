import { Check } from 'lucide-react';
import { sideTeam, type Match } from '../data/wc2026';
import { pct, strikeWeight } from '../lib/format';

/** The model's pick: ticked when it held, struck through (by confidence) when it did not. */
export function Verdict({ match, compact = false }: { match: Match; compact?: boolean }) {
  const pickName = sideTeam(match, match.pick) ?? 'Draw';
  if (match.correct) {
    return (
      <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
        <Check aria-hidden className="size-4 shrink-0 text-spot" strokeWidth={3} />
        <span className="font-semibold">{pickName}</span>
        <span className="text-muted">{pct(match.pPick)}</span>
        <span className="sr-only">, called correctly</span>
      </span>
    );
  }
  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-1.5 whitespace-nowrap">
      <span className="struck font-semibold" style={{ ['--strike' as string]: `${strikeWeight(match.pPick, 1.5)}px` }}>
        {pickName} {pct(match.pPick)}
      </span>
      <span className="sr-only">, missed.</span>
      {!compact && <span className="text-muted">result had {pct(match.pActual)}</span>}
    </span>
  );
}
