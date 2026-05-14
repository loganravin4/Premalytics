/** Result letter for recent form visualization */
export type FormResult = 'W' | 'D' | 'L';

/** Monthly goal tally for charts (API can return the same shape) */
export interface MonthlyGoals {
  month: string;
  goals: number;
}

/** Core team record returned by `/teams` and `/teams/:id` */
export interface Team {
  id: string;
  name: string;
  shortName: string;
  badge: string;
  primaryColor: string;
  form: FormResult[];
  stats: {
    played: number;
    wins: number;
    draws: number;
    losses: number;
    goalsFor: number;
    goalsAgainst: number;
    points: number;
    xG: number;
    xGA: number;
  };
  /** Optional detail fields for profile / future API */
  cleanSheets?: number;
  redCards?: number;
  monthlyGoals?: MonthlyGoals[];
}
