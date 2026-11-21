// Copied from docs/ML_EXPERIMENTS.md because backtest artifacts are gitignored; update when the backtest reruns

export interface BacktestRow {
  label: string;
  rps: number;
  logLossRaw: number;
  accuracy: number;
  served?: boolean;
}

export const BACKTEST = {
  tournaments: 27,
  matches: 1150,
  from: 2014,
  to: 2026,
  blendWinsOverGbm: 20,
  rows: [
    { label: 'Blend (served): 0.2 × gradient-boosted + 0.8 × Dixon-Coles', rps: 0.1802, logLossRaw: 0.9283, accuracy: 0.572, served: true },
    { label: 'Dixon-Coles score model alone', rps: 0.1804, logLossRaw: 0.9281, accuracy: 0.57 },
    { label: 'Gradient-boosted, 123 features (previous model)', rps: 0.185, logLossRaw: 0.9466, accuracy: 0.572 },
    { label: 'Elo logistic, 2 inputs', rps: 0.1854, logLossRaw: 0.947, accuracy: 0.567 },
    { label: 'Always back the higher-rated team', rps: 0.1954, logLossRaw: 0.9821, accuracy: 0.564 },
    { label: 'Base rates only', rps: 0.2287, logLossRaw: 1.0759, accuracy: 0.443 },
  ] satisfies BacktestRow[],
  /** Blend minus Elo logistic, pooled RPS, with its 95% bootstrap interval. */
  vsElo: { delta: -0.0052, lo: -0.0082, hi: -0.0022 },
  draws: { blendMean: 0.25, gbmMean: 0.245, actual: 0.262 },
  blend: { gbmWeight: 0.2, temperature: 0.9, dcMatches: 10879, dcWindowYears: 12 },
};

/** Leak-free WC 2026 record of the previous (gradient-boosted) model, run 20261121_144113. */
export const PREVIOUS_MODEL_WC2026 = { correct: 70, total: 104, logLossCredited: 0.764, accuracyStrict: 0.663, logLossStrict: 0.861 };
