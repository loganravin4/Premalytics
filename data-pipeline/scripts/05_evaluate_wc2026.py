"""
05_evaluate_wc2026.py — score the match-outcome predictor across WC 2026.

Self-contained tournament post-mortem. Loads the pre-tournament predictions
produced by `python -m ml.pipeline.predict` and the actual WC 2026 results,
joins them, and prints a readable report:

  * Overall accuracy (argmax of p_home_win / p_draw / p_away_win vs actual)
  * Accuracy by tournament stage
  * Multi-class log loss across all 104 matches
  * Calibration of confident home picks (p_home_win > 0.5)
  * Best "gutsy" correct calls and the model's most confident misses

Inputs (all under data-pipeline/data/):
    wc2026_predictions.json      — output of ml.pipeline.predict (fixture order)
    wc2026_full_fixtures.csv     — carries match_date + stage per fixture
    wc2026_actual_results.csv    — actual outcomes (home-team perspective)

Join key (per task spec): home_team + away_team + match_date. The predictions
JSON has no match_date column, so match_date/stage are attached from the
fixtures CSV by row order (predict.py preserves fixture order) before the
key-based join to the actual results.

Result convention: `result` is goals-based from the home team's perspective
(W = home win, D = draw, L = away win). Knockout matches decided on penalties
count as draws by default — the same W/D/L definition the model was trained on.
Pass --credit-shootout-winner to instead score those matches against the team
that actually advanced (from martj42 shootouts.csv).

Every run is versioned to:
    data-pipeline/data/evaluation/wc2026/{YYYYMMDD_HHMMSS}/
        report.txt              — plain-text copy of the full report
        metrics.json            — structured metrics
        predictions_scored.csv  — the full joined + scored table

Usage:
    python data-pipeline/scripts/05_evaluate_wc2026.py
    python data-pipeline/scripts/05_evaluate_wc2026.py --credit-shootout-winner
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent          # .../data-pipeline/scripts/
PIPELINE_DIR = SCRIPT_DIR.parent                      # .../data-pipeline/
PROJECT_ROOT = PIPELINE_DIR.parent                    # .../premalytics/
DATA_DIR = PIPELINE_DIR / "data"

PRED_JSON = DATA_DIR / "wc2026_predictions.json"
FIXTURES_CSV = DATA_DIR / "wc2026_full_fixtures.csv"
ACTUAL_CSV = DATA_DIR / "wc2026_actual_results.csv"
TEAM_MAP_CSV = DATA_DIR / "static" / "team_map_intl.csv"
SHOOTOUTS_CSV = DATA_DIR / "raw" / "martj42" / "shootouts.csv"
LATEST_RUN_TXT = PROJECT_ROOT / "ml" / "artifacts" / "latest_run.txt"
EVAL_OUT_ROOT = DATA_DIR / "evaluation" / "wc2026"

# Stage display order + friendly labels for the report.
STAGE_ORDER = [
    "group", "round_of_32", "round_of_16",
    "quarter_final", "semi_final", "third_place", "final",
]
STAGE_LABEL = {
    "group": "Group stage",
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "quarter_final": "Quarter-finals",
    "semi_final": "Semi-finals",
    "third_place": "Third-place playoff",
    "final": "Final",
}

# Force UTF-8 so team names with diacritics never hit the Windows cp1252 console.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover — non-reconfigurable stream
    pass

# rich is nice-to-have; degrade gracefully to plain text if unavailable.
try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    _CONSOLE = Console()
    _HAVE_RICH = True
except Exception:  # pragma: no cover
    _CONSOLE = None
    _HAVE_RICH = False

# Every emitted line is mirrored here so we can persist a clean plain-text
# report.txt regardless of whether rich is active on stdout.
_BUFFER: list[str] = []

_MARKUP_TAGS = ("[bold]", "[/bold]", "[green]", "[/green]", "[red]", "[/red]",
                "[yellow]", "[/yellow]", "[dim]", "[/dim]", "[bold cyan]")


def _strip(msg: str) -> str:
    for tag in _MARKUP_TAGS:
        msg = msg.replace(tag, "")
    return msg


# ---------------------------------------------------------------------------
# Loading / joining
# ---------------------------------------------------------------------------
def load_team_names() -> dict[str, str]:
    """FIFA code -> human-readable national team name (best-effort, for display)."""
    if not TEAM_MAP_CSV.exists():
        return {}
    df = pd.read_csv(TEAM_MAP_CSV)
    names: dict[str, str] = {}
    for _, row in df.iterrows():
        code = str(row.get("team_id", "")).strip().upper()
        full = str(row.get("full_name", "")).strip()
        if code and full and code not in names:
            names[code] = full
    return names


def _name_to_code() -> dict[str, str]:
    """Provider display name (alias or full_name) -> FIFA 3-letter code."""
    m: dict[str, str] = {}
    if not TEAM_MAP_CSV.exists():
        return m
    df = pd.read_csv(TEAM_MAP_CSV)
    for _, row in df.iterrows():
        code = str(row.get("team_id", "")).strip().upper()
        if not code:
            continue
        for col in ("alias", "full_name"):
            name = str(row.get(col, "")).strip()
            if name:
                m.setdefault(name, code)
    return m


def ensure_winner_column() -> None:
    """
    Guarantee wc2026_actual_results.csv has a `winner` column, persisting it if
    absent (per task spec). `winner` is the FIFA code of the team that
    advanced: the higher scorer for decisive matches, the shootout winner
    (from martj42 shootouts.csv) for matches level after extra time, and empty
    for genuine draws (group stage).
    """
    if not ACTUAL_CSV.exists():
        sys.exit(f"ERROR: missing required input {ACTUAL_CSV}")
    actual = pd.read_csv(ACTUAL_CSV)
    if "winner" in actual.columns:
        return

    name2code = _name_to_code()
    shoot: dict[tuple, str] = {}
    if SHOOTOUTS_CSV.exists():
        s = pd.read_csv(SHOOTOUTS_CSV)
        s["date"] = pd.to_datetime(s["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        for _, r in s.iterrows():
            h = name2code.get(str(r["home_team"]).strip())
            a = name2code.get(str(r["away_team"]).strip())
            w = name2code.get(str(r["winner"]).strip())
            if h and a and w:
                shoot[(r["date"], h, a)] = w

    winners: list[str] = []
    for r in actual.itertuples():
        gf, ga = int(r.goals_for), int(r.goals_against)
        if gf > ga:
            winners.append(r.home_team)
        elif gf < ga:
            winners.append(r.away_team)
        else:
            winners.append(shoot.get((r.match_date, r.home_team, r.away_team), ""))
    actual["winner"] = winners
    actual.to_csv(ACTUAL_CSV, index=False)


def load_joined() -> pd.DataFrame:
    """Load predictions + actuals and return one row per match, key-joined."""
    for p in (PRED_JSON, FIXTURES_CSV, ACTUAL_CSV):
        if not p.exists():
            sys.exit(f"ERROR: missing required input {p}")

    preds = pd.DataFrame(json.loads(PRED_JSON.read_text(encoding="utf-8")))
    fixtures = pd.read_csv(FIXTURES_CSV, comment="#")
    actual = pd.read_csv(ACTUAL_CSV)

    if len(preds) != len(fixtures):
        sys.exit(f"ERROR: predictions ({len(preds)}) and fixtures "
                 f"({len(fixtures)}) row counts differ — cannot align.")

    # predict.py preserves fixture order, so attach match_date/stage by position.
    preds = preds.reset_index(drop=True)
    preds["match_date"] = fixtures["match_date"].values
    preds["competition_stage"] = fixtures["competition_stage"].values

    # Key-based join to actuals on home_team + away_team + match_date.
    # stage already came from the fixtures file; drop the actuals' copy so the
    # merge doesn't suffix it to competition_stage_x/_y.
    actual = actual.drop(columns=["competition_stage"], errors="ignore")
    merged = preds.merge(
        actual,
        on=["match_date", "home_team", "away_team"],
        how="inner",
        validate="one_to_one",
    )
    if len(merged) != len(preds):
        sys.exit(f"ERROR: join dropped rows — {len(preds)} predictions but "
                 f"{len(merged)} joined. Check key alignment.")
    return merged


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
OUTCOMES = ["home", "draw", "away"]
RESULT_TO_OUTCOME = {"W": "home", "D": "draw", "L": "away"}


def annotate(df: pd.DataFrame, credit_shootout: bool = True) -> pd.DataFrame:
    """Add predicted outcome, actual outcome, correctness, and probability views.

    Draws are not a real final outcome in knockout football — a level match
    goes to extra time, then penalties, and someone advances. So by default
    (credit_shootout=True), knockout-stage matches level on goals (result=D)
    are re-labelled to the team that advanced on penalties (from the `winner`
    column) instead of counting as draws. Group-stage rows are never
    relabeled — a draw there is a genuine final outcome.
    """
    df = df.copy()

    # Normalize each probability triple (predict.py rounds to 4dp so they may
    # not sum to exactly 1); used for a well-defined log loss.
    p = df[["p_home_win", "p_draw", "p_away_win"]].astype(float)
    totals = p.sum(axis=1).replace(0.0, 1.0)
    df["n_home"] = p["p_home_win"] / totals
    df["n_draw"] = p["p_draw"] / totals
    df["n_away"] = p["p_away_win"] / totals

    def pred_outcome(r):
        trip = {"home": r.p_home_win, "draw": r.p_draw, "away": r.p_away_win}
        return max(trip, key=trip.get)

    df["pred_outcome"] = df.apply(pred_outcome, axis=1)
    df["actual_outcome"] = df["result"].map(RESULT_TO_OUTCOME)

    if credit_shootout and "winner" in df.columns:
        def credited(r):
            w = r.winner
            is_knockout = str(r.competition_stage).strip().lower() != "group"
            if is_knockout and r.result == "D" and pd.notna(w) and str(w).strip():
                if str(w).strip() == r.home_team:
                    return "home"
                if str(w).strip() == r.away_team:
                    return "away"
            return r.actual_outcome
        df["actual_outcome"] = df.apply(credited, axis=1)

    df["correct"] = df["pred_outcome"] == df["actual_outcome"]

    norm = {"home": "n_home", "draw": "n_draw", "away": "n_away"}
    # Probability the model assigned to the outcome that actually happened.
    df["p_actual"] = df.apply(lambda r: r[norm[r.actual_outcome]], axis=1)
    # Probability the model assigned to its own (argmax) pick — its confidence.
    df["p_pick"] = df.apply(lambda r: r[norm[r.pred_outcome]], axis=1)
    return df


def log_loss(df: pd.DataFrame) -> float:
    """Mean multi-class log loss over all matches (natural log, clipped)."""
    eps = 1e-15
    ll = -df["p_actual"].clip(lower=eps).map(math.log)
    return float(ll.mean())


# ---------------------------------------------------------------------------
# Reporting helpers — mirror everything to _BUFFER (plain) + rich stdout
# ---------------------------------------------------------------------------
def hr(title: str) -> None:
    _BUFFER.append("")
    _BUFFER.append("=" * 78)
    _BUFFER.append(_strip(title))
    _BUFFER.append("=" * 78)
    if _HAVE_RICH:
        _CONSOLE.rule(f"[bold cyan]{title}")
    else:
        print("\n" + "=" * 78 + f"\n{_strip(title)}\n" + "=" * 78)


def line(msg: str = "") -> None:
    _BUFFER.append(_strip(msg))
    if _HAVE_RICH:
        _CONSOLE.print(msg)
    else:
        print(_strip(msg))


def _plain_table(title: str, columns: list[str], rows: list[list[str]]) -> list[str]:
    out = ["", title]
    widths = [len(c) for c in columns]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    out.append(fmt.format(*columns))
    out.append(fmt.format(*["-" * w for w in widths]))
    for r in rows:
        out.append(fmt.format(*[str(c) for c in r]))
    return out


def render_table(title: str, columns: list[str], rows: list[list[str]],
                 justify: list[str] | None = None) -> None:
    _BUFFER.extend(_plain_table(title, columns, rows))
    if _HAVE_RICH:
        table = Table(title=title, box=box.SIMPLE_HEAVY, title_style="bold")
        for i, c in enumerate(columns):
            j = justify[i] if justify else ("left" if i == 0 else "right")
            table.add_column(c, justify=j)
        for r in rows:
            table.add_row(*r)
        _CONSOLE.print(table)
    else:
        for ln in _plain_table(title, columns, rows):
            print(ln)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def matchup(r, names: dict[str, str]) -> str:
    h = names.get(r.home_team, r.home_team)
    a = names.get(r.away_team, r.away_team)
    return f"{h} vs {a}"


def score_line(r) -> str:
    return f"{int(r.goals_for)}-{int(r.goals_against)}"


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def build_report(df: pd.DataFrame, names: dict[str, str],
                 credit_shootout: bool) -> dict:
    """Emit the full report to stdout/_BUFFER and return the metrics dict."""
    n = len(df)
    correct = int(df["correct"].sum())
    ll = log_loss(df)

    hr("PREMALYTICS — WORLD CUP 2026 PREDICTION REPORT")
    line("How well did the model call the tournament, using only pre-tournament")
    line("form? Every one of the 104 matches was predicted before a ball was")
    line("kicked (training data stops the day the group stage began).")
    line("")
    line('For each match the model gives three chances: home win, draw, away win.')
    line('Its "pick" is simply the most likely of the three.')
    if credit_shootout:
        line("")
        line("[yellow]Scoring mode: SHOOTOUT-CREDITED[/yellow] — knockout matches level")
        line("after extra time are scored against the team that advanced on penalties.")
    else:
        line("")
        line("Scoring mode: goals-based (penalty shootouts count as draws).")

    # --- Overall accuracy ---
    hr("HEADLINE")
    line(f"[bold]Overall accuracy:[/bold] {correct}/{n} matches called correctly "
         f"= [bold]{pct(correct / n)}[/bold]")
    line(f"[bold]Log loss:[/bold] {ll:.4f}  "
         "[dim](lower is better; 1.0986 = always guessing 1/3 each)[/dim]")

    # --- Accuracy by stage ---
    stage_rows = []
    by_stage: dict[str, dict] = {}
    for stage in STAGE_ORDER:
        sub = df[df["competition_stage"] == stage]
        if sub.empty:
            continue
        c = int(sub["correct"].sum())
        t = int(len(sub))
        by_stage[stage] = {"correct": c, "total": t, "accuracy": round(c / t, 4)}
        stage_rows.append([STAGE_LABEL.get(stage, stage), f"{c}/{t}", pct(c / t)])
    render_table("Accuracy by stage", ["Stage", "Correct", "Accuracy"], stage_rows)

    # --- Calibration ---
    hr("CALIBRATION — are the probabilities honest?")
    confident_home = df[df["p_home_win"] > 0.5]
    calibration: dict = {}
    if len(confident_home):
        won = int((confident_home["actual_outcome"] == "home").sum())
        avg_p = float(confident_home["p_home_win"].mean())
        rate = won / len(confident_home)
        gap = rate - avg_p
        verdict = ("well calibrated" if abs(gap) <= 0.05
                   else ("over-confident" if gap < 0 else "under-confident"))
        line("When the model was [bold]confident the home team would win[/bold] "
             "(p_home_win > 50%):")
        line(f"  • {len(confident_home)} such matches")
        line(f"  • Home team actually won [bold]{won}[/bold] of them "
             f"= [bold]{pct(rate)}[/bold]")
        line(f"  • Model's average stated confidence in those picks: {pct(avg_p)}")
        line(f"  • Verdict: [bold]{verdict}[/bold] "
             f"(actual − stated = {gap * 100:+.0f} points)")
        calibration = {
            "confident_home_matches": int(len(confident_home)),
            "confident_home_actual_wins": won,
            "confident_home_win_rate": round(rate, 4),
            "confident_home_avg_stated": round(avg_p, 4),
            "verdict": verdict,
        }
    else:
        line("No match had p_home_win > 0.5.")
        calibration = {
            "confident_home_matches": 0,
            "confident_home_actual_wins": 0,
            "confident_home_win_rate": 0.0,
            "confident_home_avg_stated": 0.0,
            "verdict": "n/a",
        }

    # Broader calibration table across confidence buckets of the model's pick.
    line("")
    buckets = [(0.33, 0.40), (0.40, 0.50), (0.50, 0.60), (0.60, 0.70), (0.70, 1.01)]
    cal_rows = []
    for lo, hi in buckets:
        sub = df[(df["p_pick"] >= lo) & (df["p_pick"] < hi)]
        if sub.empty:
            continue
        acc = sub["correct"].mean()
        cal_rows.append([f"{pct(lo)}–{pct(hi) if hi <= 1 else '100%'}",
                         str(len(sub)), pct(sub["p_pick"].mean()), pct(acc)])
    render_table("Reliability of the model's pick, by stated confidence",
                 ["Confidence in pick", "Matches", "Avg stated", "Actual accuracy"],
                 cal_rows)

    # --- Gutsy correct calls: correct picks with the LOWEST confidence ---
    hr("BEST CALLS — correct picks the model was least sure about")
    line("Matches the model got right despite giving its winning pick a low")
    line("probability — the closest calls it still nailed.")
    gutsy = df[df["correct"]].sort_values("p_pick").head(5)
    rows, gutsy_json = [], []
    for r in gutsy.itertuples():
        rows.append([f"{matchup(r, names)}",
                     STAGE_LABEL.get(r.competition_stage, r.competition_stage),
                     score_line(r), r.pred_outcome, pct(r.p_pick)])
        gutsy_json.append({
            "match_date": r.match_date, "home_team": r.home_team,
            "away_team": r.away_team, "stage": r.competition_stage,
            "score": score_line(r), "called": r.pred_outcome,
            "confidence": round(float(r.p_pick), 4),
        })
    render_table("Gutsiest correct calls", ["Match", "Stage", "Score",
                 "Called", "Confidence"], rows)

    # --- Confident misses: wrong picks where actual outcome got lowest prob ---
    hr("WORST MISSES — the results that surprised the model most")
    line("Matches the model got wrong, ranked by how little probability it gave")
    line("to what actually happened (its biggest upsets missed).")
    misses = df[~df["correct"]].sort_values("p_actual").head(5)
    rows, misses_json = [], []
    for r in misses.itertuples():
        rows.append([f"{matchup(r, names)}",
                     STAGE_LABEL.get(r.competition_stage, r.competition_stage),
                     score_line(r),
                     f"{r.pred_outcome} ({pct(r.p_pick)})",
                     f"{r.actual_outcome} ({pct(r.p_actual)})"])
        misses_json.append({
            "match_date": r.match_date, "home_team": r.home_team,
            "away_team": r.away_team, "stage": r.competition_stage,
            "score": score_line(r), "model_picked": r.pred_outcome,
            "model_pick_prob": round(float(r.p_pick), 4),
            "actual": r.actual_outcome, "actual_prob": round(float(r.p_actual), 4),
        })
    render_table("Most surprising results",
                 ["Match", "Stage", "Score", "Model picked", "Actually happened"],
                 rows)

    hr("END OF REPORT")

    model_run_id = LATEST_RUN_TXT.read_text().strip() if LATEST_RUN_TXT.exists() else None
    return {
        "run_date": datetime.now().isoformat(timespec="seconds"),
        "model_run_id": model_run_id,
        "scoring_mode": "shootout_credited" if credit_shootout else "goals_based",
        "overall": {
            "accuracy": round(correct / n, 4),
            "correct": correct,
            "total": n,
            "log_loss": round(ll, 4),
        },
        "by_stage": by_stage,
        "calibration": calibration,
        "top_5_gutsy_correct": gutsy_json,
        "top_5_worst_misses": misses_json,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
PRED_SCORED_COLS = [
    "match_date", "home_team", "away_team", "competition_stage",
    "p_home_win", "p_draw", "p_away_win", "pred_outcome", "actual_outcome",
    "correct", "p_actual", "p_pick", "goals_for", "goals_against",
]


def save_versioned(df: pd.DataFrame, metrics: dict) -> Path:
    """Write report.txt, metrics.json, predictions_scored.csv to a timestamped dir."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = EVAL_OUT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "report.txt").write_text("\n".join(_BUFFER) + "\n", encoding="utf-8")
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8")
    df[PRED_SCORED_COLS].to_csv(out_dir / "predictions_scored.csv", index=False)
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Score WC 2026 predictions")
    parser.add_argument(
        "--credit-shootout-winner", dest="credit_shootout_winner",
        action="store_true", default=True,
        help="Score knockout matches level on goals against the team that "
             "advanced on penalties (default: on).",
    )
    parser.add_argument(
        "--no-credit-shootout-winner", dest="credit_shootout_winner",
        action="store_false",
        help="Disable shootout crediting; score every level knockout match "
             "goals-based, i.e. as a draw (old behavior, for comparison).",
    )
    args = parser.parse_args()

    names = load_team_names()
    ensure_winner_column()
    df = annotate(load_joined(), credit_shootout=args.credit_shootout_winner)

    metrics = build_report(df, names, credit_shootout=args.credit_shootout_winner)
    out_dir = save_versioned(df, metrics)

    rel = out_dir.relative_to(PROJECT_ROOT).as_posix()
    print(f"\nResults saved to: {rel}/")


if __name__ == "__main__":
    main()
