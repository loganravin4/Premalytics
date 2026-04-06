/** Tailwind arbitrary color utilities per team (no inline styles in UI) */
export const teamAccentBoxClass: Record<string, string> = {
  arsenal: 'border-[#ef0107] bg-[#ef0107]/20',
  liverpool: 'border-[#c8102e] bg-[#c8102e]/20',
  'man-city': 'border-[#6cabdd] bg-[#6cabdd]/20',
  chelsea: 'border-[#034694] bg-[#034694]/20',
  spurs: 'border-[#132257] bg-[#132257]/25',
  'man-united': 'border-[#da291c] bg-[#da291c]/20',
  newcastle: 'border-[#241f20] bg-[#241f20]/30',
  'aston-villa': 'border-[#670e36] bg-[#670e36]/20',
  brighton: 'border-[#0057b8] bg-[#0057b8]/20',
  'west-ham': 'border-[#7a263a] bg-[#7a263a]/20',
  fulham: 'border-[#888888] bg-[#888888]/15',
  'crystal-palace': 'border-[#1b458f] bg-[#1b458f]/20',
  brentford: 'border-[#e30613] bg-[#e30613]/20',
  everton: 'border-[#003399] bg-[#003399]/20',
  forest: 'border-[#dd0000] bg-[#dd0000]/20',
  bournemouth: 'border-[#da291c] bg-[#da291c]/18',
  wolves: 'border-[#fdb913] bg-[#fdb913]/20',
  leicester: 'border-[#003090] bg-[#003090]/20',
  ipswich: 'border-[#3d195b] bg-[#3d195b]/20',
  southampton: 'border-[#d71920] bg-[#d71920]/20',
};

export function getTeamAccentBoxClass(teamId: string): string {
  return teamAccentBoxClass[teamId] ?? 'border-[var(--color-border)] bg-[var(--color-surface-elevated)]';
}
