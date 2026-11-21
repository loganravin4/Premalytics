// Builds the typed JSON the site reads from the pipeline's own outputs.
// Run from frontend/: `npm run data`. Output is committed so the site builds without the pipeline.
import { readFileSync, readdirSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', '..');
const dataDir = join(root, 'data-pipeline', 'data');
const outDir = join(here, '..', 'src', 'data', 'generated');

function parseCsv(text) {
  const rows = [];
  let row = [], field = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field); field = '';
      if (row.some((v) => v !== '')) rows.push(row);
      row = [];
    } else field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  const [head, ...body] = rows;
  return body.map((r) => Object.fromEntries(head.map((h, i) => [h.trim(), (r[i] ?? '').trim()])));
}
const csv = (p) => parseCsv(readFileSync(p, 'utf8'));

// Latest scored evaluation run (directory names are timestamps).
const evalRoot = join(dataDir, 'evaluation', 'wc2026');
const runs = readdirSync(evalRoot).filter((d) => existsSync(join(evalRoot, d, 'predictions_scored.csv'))).sort();
if (!runs.length) throw new Error(`No scored runs under ${evalRoot}`);
const runDir = join(evalRoot, runs.at(-1));
const scored = csv(join(runDir, 'predictions_scored.csv'));
const evalMetrics = JSON.parse(readFileSync(join(runDir, 'metrics.json'), 'utf8'));
// Runs written before the --as-of fix (2026-11-21) lack raw metrics and leaked in-tournament form.
if (evalMetrics.accuracy_raw == null || evalMetrics.log_loss_raw == null) {
  throw new Error(`${runs.at(-1)} has no raw metrics; re-run 05_evaluate_wc2026.py on a leak-free (--as-of) prediction run`);
}

const fixtures = csv(join(dataDir, 'wc2026_full_fixtures.csv'));
const results = csv(join(dataDir, 'wc2026_actual_results.csv'));
const teamMap = csv(join(dataDir, 'static', 'team_map_intl.csv'));

// Training-set size and feature count live in gitignored ml/artifacts; fall back to the last known values.
const modelMetricsPath = join(root, 'ml', 'artifacts', evalMetrics.model_run_id, 'metrics.json');
const modelMetrics = existsSync(modelMetricsPath) ? JSON.parse(readFileSync(modelMetricsPath, 'utf8')) : null;

// Display names follow common English usage where team_map_intl.csv differs.
const NAME_OVERRIDES = {
  CZE: 'Czechia', TUR: 'Türkiye', CUW: 'Curaçao', CIV: "Côte d'Ivoire", BIH: 'Bosnia and Herzegovina',
};

const key = (r) => `${r.match_date}|${r.home_team}|${r.away_team}`;
const fixtureBy = new Map(fixtures.map((r) => [key(r), r]));
const resultBy = new Map(results.map((r) => [key(r), r]));

const STAGE_ORDER = ['group', 'round_of_32', 'round_of_16', 'quarter_final', 'semi_final', 'third_place', 'final'];
const sorted = [...scored].sort((a, b) =>
  a.match_date.localeCompare(b.match_date) || STAGE_ORDER.indexOf(a.competition_stage) - STAGE_ORDER.indexOf(b.competition_stage));

const matches = sorted.map((r, i) => {
  const res = resultBy.get(key(r));
  const fx = fixtureBy.get(key(r));
  const hg = Number(r.goals_for), ag = Number(r.goals_against);
  const knockout = r.competition_stage !== 'group';
  const winner = res?.winner && res.winner !== 'draw' ? res.winner : hg > ag ? r.home_team : ag > hg ? r.away_team : null;
  return {
    id: i + 1,
    date: r.match_date,
    stage: r.competition_stage,
    home: r.home_team,
    away: r.away_team,
    neutral: fx ? fx.is_neutral_venue === 'True' : true,
    p: { home: Number(r.p_home_win), draw: Number(r.p_draw), away: Number(r.p_away_win) },
    pick: r.pred_outcome,
    outcome: r.actual_outcome,
    correct: r.correct === 'True',
    pActual: Number(Number(r.p_actual).toFixed(4)),
    pPick: Number(Number(r.p_pick).toFixed(4)),
    score: { home: hg, away: ag },
    winner,
    shootout: knockout && hg === ag,
  };
});

const codes = [...new Set(matches.flatMap((m) => [m.home, m.away]))].sort();
const teams = codes.map((code) => {
  const row = teamMap.find((t) => t.team_id === code);
  return { code, name: NAME_OVERRIDES[code] ?? row?.full_name ?? code, confederation: row?.confederation ?? 'OTHER' };
});

// Groups are the connected components of the group-stage schedule. Official group letters
// are not in the data, so groups are identified by their teams, never by an invented letter.
const groupMatches = matches.filter((m) => m.stage === 'group');
const parent = new Map(codes.map((c) => [c, c]));
const find = (c) => (parent.get(c) === c ? c : find(parent.get(c)));
for (const m of groupMatches) parent.set(find(m.home), find(m.away));
const comps = new Map();
for (const c of codes) {
  if (!groupMatches.some((m) => m.home === c || m.away === c)) continue;
  const r = find(c);
  comps.set(r, [...(comps.get(r) ?? []), c]);
}
const groups = [...comps.values()]
  .map((members) => {
    const ms = groupMatches.filter((m) => members.includes(m.home));
    return { teams: members, matchIds: ms.map((m) => m.id), firstDate: ms.map((m) => m.date).sort()[0] };
  })
  .sort((a, b) => a.firstDate.localeCompare(b.firstDate) || a.teams[0].localeCompare(b.teams[0]))
  .map(({ teams: t, matchIds }) => ({ teams: t, matchIds }));

const summary = {
  run: runs.at(-1),
  modelRunId: evalMetrics.model_run_id,
  scoringMode: evalMetrics.scoring_mode,
  correct: evalMetrics.overall.correct,
  total: evalMetrics.overall.total,
  logLoss: evalMetrics.overall.log_loss,
  byStage: evalMetrics.by_stage,
  calibration: evalMetrics.calibration,
  // Strict numbers: a draw is its own outcome and shootouts count as draws.
  raw: {
    nTrain: modelMetrics?.n_train ?? 30417,
    nFeatures: modelMetrics?.n_features ?? 123,
    strict: { accuracy: evalMetrics.accuracy_raw, log_loss: evalMetrics.log_loss_raw },
    rps: evalMetrics.rps,
  },
};

mkdirSync(outDir, { recursive: true });
const write = (name, value) => writeFileSync(join(outDir, name), JSON.stringify(value, null, 1) + '\n');
write('wc2026.json', { summary, matches, groups, teams });
console.log(`wrote ${matches.length} matches, ${teams.length} teams, ${groups.length} groups from ${runs.at(-1)}`);
