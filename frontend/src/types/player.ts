/** Normalized 0–100 scores for radar breakdown (ML or scouting API) */
export interface PlayerRadarScores {
  finishing: number;
  creativity: number;
  pressing: number;
  progression: number;
  defending: number;
}

/** One season’s cumulative xG for trend line */
export interface SeasonXGPoint {
  season: string;
  xG: number;
}

/** Shot location in percent within the attacking-half placeholder (0–100) */
export interface ShotMapPoint {
  x: number;
  y: number;
}

/** Player row from `/players` and `/players/:id` */
export interface Player {
  id: string;
  name: string;
  team: string;
  teamId: string;
  position: string;
  nationality: string;
  age: number;
  stats: {
    goals: number;
    assists: number;
    xG: number;
    xAG: number;
    minutes: number;
    appearances: number;
    progressivePasses: number;
    progressiveCarries: number;
    shots: number;
    shotsOnTarget: number;
    tackles: number;
    interceptions: number;
  };
  /** Display helpers — optional until API provides them */
  flagEmoji?: string;
  radarScores?: PlayerRadarScores;
  seasonXGHistory?: SeasonXGPoint[];
  shotMap?: ShotMapPoint[];
}
