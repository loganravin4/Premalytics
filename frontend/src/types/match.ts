/** Lifecycle state for a fixture */
export type MatchStatus = 'completed' | 'upcoming' | 'live';

/** Fixture row from `/matches` */
export interface Match {
  id: string;
  homeTeam: string;
  homeTeamId: string;
  awayTeam: string;
  awayTeamId: string;
  date: string;
  homeGoals?: number;
  awayGoals?: number;
  status: MatchStatus;
  xGHome?: number;
  xGAway?: number;
}
