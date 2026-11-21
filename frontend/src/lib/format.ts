const dateFmt = new Intl.DateTimeFormat('en-US', { day: 'numeric', month: 'short', timeZone: 'UTC' });
const longDateFmt = new Intl.DateTimeFormat('en-US', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

export const shortDate = (iso: string) => dateFmt.format(new Date(`${iso}T00:00:00Z`));
export const longDate = (iso: string) => longDateFmt.format(new Date(`${iso}T00:00:00Z`));

export const pct = (p: number, digits = 0) => `${(p * 100).toFixed(digits)}%`;

/** Strike weight for a miss: a coin-flip miss gets a hairline, a confident one a heavy rule. */
export function strikeWeight(pPick: number, max = 6): number {
  const t = Math.min(1, Math.max(0, (pPick - 0.34) / (0.8 - 0.34)));
  return Math.round((1 + t * (max - 1)) * 2) / 2;
}
