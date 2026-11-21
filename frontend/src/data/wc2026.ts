import raw from './generated/wc2026.json';

export type Outcome = 'home' | 'draw' | 'away';
export type Stage = 'group' | 'round_of_32' | 'round_of_16' | 'quarter_final' | 'semi_final' | 'third_place' | 'final';

export interface Match {
  id: number;
  date: string;
  stage: Stage;
  home: string;
  away: string;
  neutral: boolean;
  p: Record<Outcome, number>;
  pick: Outcome;
  outcome: Outcome;
  correct: boolean;
  pActual: number;
  pPick: number;
  score: { home: number; away: number };
  winner: string | null;
  shootout: boolean;
}
export interface Team {
  code: string;
  name: string;
  confederation: string;
}
export interface Group {
  teams: string[];
  matchIds: number[];
}
export interface StageTally {
  correct: number;
  total: number;
  accuracy: number;
}
export interface Summary {
  run: string;
  modelRunId: string;
  scoringMode: string;
  correct: number;
  total: number;
  logLoss: number;
  byStage: Record<Stage, StageTally>;
  raw: {
    nTrain: number;
    nFeatures: number;
    strict: { accuracy: number; log_loss: number };
    rps: number;
  };
}

const data = raw as unknown as { summary: Summary; matches: Match[]; groups: Group[]; teams: Team[] };

export const summary = data.summary;
export const matches = data.matches;
export const groups = data.groups;
export const teams = data.teams;

const teamBy = new Map(teams.map((t) => [t.code, t]));
export const team = (code: string): Team => teamBy.get(code) ?? { code, name: code, confederation: 'OTHER' };

export const STAGES: Stage[] = ['group', 'round_of_32', 'round_of_16', 'quarter_final', 'semi_final', 'third_place', 'final'];
export const STAGE_LABEL: Record<Stage, string> = {
  group: 'Group stage',
  round_of_32: 'Round of 32',
  round_of_16: 'Round of 16',
  quarter_final: 'Quarter-finals',
  semi_final: 'Semi-finals',
  third_place: 'Third place',
  final: 'Final',
};
export const STAGE_SHORT: Record<Stage, string> = {
  group: 'Groups',
  round_of_32: 'R32',
  round_of_16: 'R16',
  quarter_final: 'QF',
  semi_final: 'SF',
  third_place: '3rd',
  final: 'Final',
};

export const matchSlug = (m: Match) => `${m.date}-${m.home}-${m.away}`.toLowerCase();
const matchBySlug = new Map(matches.map((m) => [matchSlug(m), m]));
export const matchFromSlug = (slug: string) => matchBySlug.get(slug.toLowerCase());
export const matchHref = (m: Match) => `/wc2026/${matchSlug(m)}`;

export const teamMatches = (code: string) => matches.filter((m) => m.home === code || m.away === code);

/** The team named by an outcome (null for a draw). */
export const sideTeam = (m: Match, o: Outcome) => (o === 'home' ? m.home : o === 'away' ? m.away : null);

export const CONFEDERATIONS: Record<string, string> = {
  UEFA: 'Europe · UEFA',
  CONMEBOL: 'South America · CONMEBOL',
  CONCACAF: 'North and Central America · CONCACAF',
  CAF: 'Africa · CAF',
  AFC: 'Asia · AFC',
  OFC: 'Oceania · OFC',
  OTHER: 'Other',
};
