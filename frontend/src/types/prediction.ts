/** Model pick for the 1X2 market */
export type PredictedOutcome = 'home' | 'draw' | 'away';

/** Confidence bucket from the model */
export type PredictionConfidence = 'high' | 'medium' | 'low';

/** Prediction payload for `/predictions` */
export interface Prediction {
  matchId: string;
  homeTeam: string;
  awayTeam: string;
  date: string;
  homeWinProbability: number;
  drawProbability: number;
  awayWinProbability: number;
  predictedOutcome: PredictedOutcome;
  confidence: PredictionConfidence;
  keyFactors: string[];
}
