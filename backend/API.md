# Neutral Ground API

Base URL: `VITE_API_URL` (local: `http://localhost:8080`). Live OpenAPI: `GET /api/docs` (JSON), Swagger UI at
`/api/docs/ui`. This file is the contract the frontend codes against; the Java records in
`src/main/java/com/neutralground/web/dto/` are the source of truth.

## Conventions

- JSON keys are **camelCase**. Dates are `"YYYY-MM-DD"`, timestamps ISO-8601 with offset.
- Outcome codes: `"H"` home win, `"D"` draw, `"A"` away win.
- Nullable fields are always present and set to `null` (never omitted).
- Probabilities are model estimates in `[0, 1]`. Knockout predictions have `pDraw: 0` because the model
  redistributes draw mass to the two teams (they are "advance" probabilities).
- Team codes are three uppercase letters (`BRA`, `KOR`, `CPV`), as in `team_map_intl.csv`.
- Reads send `Cache-Control: public, max-age=300` and an `ETag`; send `If-None-Match` to get `304`.
- Data changes only when a model run is published (`python -m ml.pipeline.publish`).

### Paging

List endpoints that can grow take `page` (zero-based, default `0`) and `size` (default `50`, max `200`) and
return:

```ts
type Page<T> = { items: T[]; page: number; size: number; totalItems: number; totalPages: number };
```

### Errors

Every error, including 404s for unknown routes, has this body. No stack traces or internal messages.

```ts
type ApiError = {
  status: number;          // 400, 404, 405, 415, 422, 429, 500, 503
  error: string;           // "Bad Request"
  message: string;         // "Request validation failed"
  path: string;            // "/api/predictions/match"
  timestamp: string;
  fieldErrors: { field: string; message: string }[];  // empty unless validation failed
};
```

`field` is a path into the request: `fixtures[0].homeTeam`, or a query parameter name such as `stage`.

## Shared shapes

```ts
type Outcome = "H" | "D" | "A";
type Stage = "group" | "round_of_32" | "round_of_16" | "quarter_final" | "semi_final" | "third_place" | "final";

type TeamRef = { code: string; name: string };

type MatchResult = {
  homeGoals: number;            // after extra time
  awayGoals: number;
  outcome: Outcome;             // by goals, so a shootout is "D"
  winner: string | null;        // team code; null for a group-stage draw
  decidedOnPenalties: boolean;
};

type MatchPrediction = {
  modelRunId: string;
  pHome: number; pDraw: number; pAway: number;
  pick: Outcome;                // most likely outcome
  predictedScore: { home: number; away: number } | null;
  homeXg: number | null;        // expected goals from the score model
  awayXg: number | null;
  correct: boolean | null;      // null until played; shootout-credited (a shootout counts for the team that advanced)
};

type MatchSummary = {
  id: number; tournamentId: string; matchNumber: number; date: string; stage: Stage;
  homeTeam: TeamRef; awayTeam: TeamRef; neutralVenue: boolean;
  result: MatchResult | null;           // null until played
  prediction: MatchPrediction | null;   // newest published run
};

type ModelRecord = { scored: number; correct: number; accuracy: number | null };  // accuracy rounded to 4 dp
```

## Read endpoints

### `GET /api/tournaments` → `TournamentSummary[]`

Newest first. Not paged (one row per tournament).

```ts
type TournamentSummary = {
  id: string;                 // "wc2026"
  name: string; competitionId: string; year: number; hosts: string | null;
  startDate: string | null; endDate: string | null;
  matchCount: number; playedCount: number;
};
```

### `GET /api/tournaments/{id}` → `TournamentDetail`

`TournamentSummary` fields plus the model's record, overall and per stage (stages in bracket order).

```ts
type TournamentDetail = TournamentSummary & {
  modelRunId: string | null;
  record: ModelRecord;
  stages: { stage: Stage; matches: number; played: number; record: ModelRecord }[];
};
```

The record is shootout-credited, so for WC 2026 it reproduces the report's 72/104. The raw (non-credited)
numbers are in `/api/model-runs/latest` → `metrics` and `evaluation`.

### `GET /api/tournaments/{id}/matches?stage=&page=&size=` → `Page<MatchSummary>`

Match order. `stage` is optional. Unknown tournament → 404; bad `stage` or `size` → 400.

### `GET /api/matches/{id}` → `MatchDetail`

```ts
type MatchDetail = MatchSummary & {
  tournamentName: string | null;
  predictionHistory: MatchPrediction[];   // every published run, newest first; prediction === predictionHistory[0]
};
```

### `GET /api/teams?confederation=&page=&size=` → `Page<TeamSummary>`

Sorted by name. `confederation` is one of `AFC CAF CONCACAF CONMEBOL OFC UEFA`.

```ts
type TeamSummary = { code: string; name: string; confederation: string };
```

### `GET /api/teams/{code}?eloSince=YYYY-MM-DD` → `TeamDetail`

`eloSince` defaults to `2018-01-01`. Elo is the pre-match rating from the match model's features.

```ts
type TeamDetail = TeamSummary & {
  currentElo: number | null;              // last point of eloHistory
  eloHistory: { date: string; elo: number }[];   // oldest first
  record: ModelRecord;                    // the model's record on this team's played matches
  matches: MatchSummary[];                // every published match of this team, newest first
};
```

### `GET /api/model-runs/latest?kind=match` → `ModelRunView`

`kind` is `match` (default), `score`, `shot_xg`, or `penalty`. `GET /api/model-runs/{id}` returns one run.

```ts
type ModelRunView = {
  id: string;                     // artifact dir name, e.g. "20260722_002607"
  kind: string;
  trainedThrough: string | null;  // training data cutoff (exclusive)
  publishedAt: string;
  metrics: Record<string, unknown>;            // ml/artifacts/<run>/metrics.json, verbatim
  evaluation: Record<string, unknown> | null;  // tournament evaluation metrics.json, verbatim
  notes: string | null;
};
```

`metrics` and `evaluation` are passed through untouched (snake_case keys, as the pipeline writes them), so
new metrics from ML-02 (`rps`, `brier`, `reliability`, ...) appear without an API change. For the WC 2026 run,
`evaluation` holds `overall`, `by_stage`, `calibration`, `top_5_gutsy_correct`, `top_5_worst_misses`.

### `GET /api/xg/grid` → `XgGrid`

From the newest shot model run that has a published grid (XG-04). 404 until one is published.

```ts
type XgGrid = {
  modelRunId: string;
  cells: { distanceM: number; angleDeg: number; bodyPart: string; situation: string; pGoal: number }[];
};
```

`bodyPart` / `situation` are `"any"` when the grid does not split by them.

### `GET /api/penalties/aggregates?dataset=&dimension=` → `PenaltyAggregate[]`

Empty array until PEN-03 publishes. Label it experimental in the UI.

```ts
type PenaltyAggregate = {
  dataset: string; dimension: string; bucket: string;   // e.g. "penalty_kicks_v0", "zone", "top_left"
  kicks: number; goals: number; conversion: number;
};
```

## Inference endpoints

Rate limited per client IP (default 30 requests, refilling 30 per minute). Over the limit → `429` with
`Retry-After`. If ml-serve is down or slow → `503`. Send `Content-Type: application/json`.

### `POST /api/predictions/match`

Up to 20 hypothetical fixtures. snake_case keys (`home_team`, `match_date`, ...) are also accepted.

```ts
type Request = {
  fixtures: {
    homeTeam: string;            // must exist in /api/teams
    awayTeam: string;            // must differ from homeTeam
    matchDate: string;           // YYYY-MM-DD
    competitionId?: string;      // default "fifa_world_cup"
    competitionStage?: Stage;    // default "group"; any other stage gets knockout (no-draw) probabilities
    neutralVenue?: boolean;      // default true
  }[];
};

type Response = {
  homeTeam: string; awayTeam: string;
  pHome: number; pDraw: number; pAway: number; pick: Outcome;
  predictedScore: { home: number; away: number } | null;
  homeXg: number | null; awayXg: number | null;
  modelRunId: string;
}[];
```

### `POST /api/predictions/shot`

Label the number "model estimate, not official xG".

```ts
type Request = {
  distanceM: number;        // 0-120, from goal center
  angleDeg: number;         // 0-90, 0 = central
  bodyPart?: string;        // ignored by the current logistic model
  situation?: string;
};
type Response = { pGoal: number; model: string; modelRunId: string | null; distanceM: number; angleDeg: number };
```

## Operations

- `GET /actuator/health`, `/actuator/health/liveness`, `/actuator/health/readiness` (readiness includes the
  database).
