"""Walk-forward backtest: retrain before each major tournament, then score it.

Usage: python -m ml.pipeline.backtest [--max-folds N] [--models gbm,dixon_coles] [--rebuild-features]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.config import (
    ARTIFACTS_DIR, DATA_DIR, LOG_FORMAT, RANDOM_SEED, STATIC_DIR,
    TOURNAMENT_WEIGHTS, DRAW_CALIBRATION_THRESHOLD, DRAW_CALIBRATION_ALPHA,
)
from ml.models import metrics as M
from ml.models.baselines import make_logistic_pipeline
from ml.models.calibration import (
    DrawBiasScaler, LinearPool, TemperatureScaler, ThresholdDrawCal,
    apply_threshold_draw_cal,
)
from ml.models.dixon_coles import DixonColes
from ml.models.gradient_boost import make_best_boosting_pipeline

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

MAJOR_TOURNAMENTS = [
    "fifa_world_cup", "uefa_euro", "copa_america",
    "afcon", "afc_asian_cup", "concacaf_gold_cup",
]
# 2010-2013 folds are scored only so later folds have OOS predictions to fit post-processing on.
WARMUP_START = pd.Timestamp("2010-01-01")
REPORT_START = pd.Timestamp("2014-01-01")
EDITION_GAP_DAYS = 90
MIN_EDITION_MATCHES = 16

# Tuned on the 2010-2013 warm-up folds only, so reported folds stay out of sample.
DC_XI = 0.0005
DC_L2 = 0.1
DC_WINDOW_YEARS = 12

ELO_COLS = ["diff_elo", "home_is_neutral_venue"]
NON_KO_STAGES = {"group", "friendly", "qualifier"}

BASE_MODELS = ["gbm", "gbm_raw", "logistic_123", "elo_logistic", "favorite", "priors",
               "dixon_coles"]
POST_MODELS = ["gbm_drawcal_shipped", "gbm_drawcal_wf", "gbm_temp", "gbm_drawbias",
               "gbm_raw_temp", "blend", "blend_temp", "blend_drawbias", "elo_dc_blend"]


@dataclass
class Fold:
    name: str
    competition_id: str
    start: pd.Timestamp
    end: pd.Timestamp
    # Positional (iloc) indices, not index labels.
    test_index: np.ndarray
    warmup: bool

    def train_mask(self, dates: pd.Series) -> np.ndarray:
        # Model is frozen at the tournament start; later rounds still see updated pre-match form.
        return (pd.to_datetime(dates) < self.start).to_numpy()


def _drop_swapped_duplicates(features: pd.DataFrame, pos: np.ndarray) -> np.ndarray:
    sub = features.iloc[pos]
    key = [(d, *sorted((h, a))) for d, h, a in
           zip(pd.to_datetime(sub["match_date"]), sub["home_team"], sub["away_team"])]
    src = sub.get("home_source", pd.Series("", index=sub.index)).astype(str).to_numpy()
    # Loader keeps both sources' rows when they disagree on home/away; prefer FBref, it has real stage labels.
    order = np.argsort(src != "fbref", kind="stable")
    seen, keep = set(), []
    for i in order:
        if key[i] not in seen:
            seen.add(key[i])
            keep.append(pos[i])
    return np.sort(np.array(keep, dtype=int))


def find_tournament_folds(features: pd.DataFrame,
                          competitions: list[str] = MAJOR_TOURNAMENTS,
                          since: pd.Timestamp = WARMUP_START,
                          report_start: pd.Timestamp = REPORT_START,
                          min_matches: int = MIN_EDITION_MATCHES) -> list[Fold]:
    # Split editions by date gap because season_id is unreliable (Euro 2020 spans 2020 and 2021).
    comp = features["home_competition_id"].astype(str).to_numpy()
    dates = pd.to_datetime(features["match_date"])
    folds: list[Fold] = []
    for cid in competitions:
        pos = np.flatnonzero(comp == cid)
        if len(pos) == 0:
            continue
        pos = pos[np.argsort(dates.iloc[pos].to_numpy(), kind="stable")]
        d = dates.iloc[pos].to_numpy()
        breaks = np.flatnonzero(np.diff(d) > np.timedelta64(EDITION_GAP_DAYS, "D")) + 1
        for chunk in np.split(pos, breaks):
            start, end = dates.iloc[chunk].min(), dates.iloc[chunk].max()
            if start < since or len(chunk) < min_matches:
                continue
            chunk = _drop_swapped_duplicates(features, chunk)
            seasons = pd.to_numeric(features["season_id"].iloc[chunk], errors="coerce")
            label = int(seasons.min()) if seasons.notna().any() else start.year
            folds.append(Fold(f"{cid}_{label}", cid, start, end,
                              np.sort(chunk), bool(start < report_start)))
    folds.sort(key=lambda f: (f.start, f.name))
    return folds


def _raw_fingerprint() -> str:
    h = hashlib.sha1()
    for p in sorted(DATA_DIR.rglob("match_logs_normalized.csv")):
        st = p.stat()
        h.update(f"{p.relative_to(DATA_DIR)}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:12]


def load_features(rebuild: bool = False) -> pd.DataFrame:
    """Full-corpus feature matrix, cached by raw-data fingerprint (build takes ~5 min)."""
    from ml.pipeline.train import load_wc_features
    cache_dir = ARTIFACTS_DIR / "feature_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"features_{_raw_fingerprint()}.joblib"
    if path.exists() and not rebuild:
        logger.info("Loading cached features %s", path.name)
        return joblib.load(path)
    features = load_wc_features()
    joblib.dump(features, path)
    return features


def load_shootouts() -> dict[tuple, str]:
    """(YYYY-MM-DD, home_code, away_code) -> winner code, from martj42 shootouts.csv."""
    path = DATA_DIR / "martj42" / "shootouts.csv"
    tm = STATIC_DIR / "team_map_intl.csv"
    if not path.exists() or not tm.exists():
        logger.warning("shootouts.csv or team map missing; credited metrics == raw")
        return {}
    name2code: dict[str, str] = {}
    for _, r in pd.read_csv(tm).iterrows():
        code = str(r.get("team_id", "")).strip().upper()
        for col in ("alias", "full_name"):
            nm = str(r.get(col, "")).strip()
            if code and nm:
                name2code.setdefault(nm, code)
    s = pd.read_csv(path)
    s["date"] = pd.to_datetime(s["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out = {}
    for r in s.itertuples():
        h, a, w = (name2code.get(str(x).strip()) for x in (r.home_team, r.away_team, r.winner))
        if h and a and w:
            out[(r.date, h, a)] = w
            out[(r.date, a, h)] = w
    return out


def outcome_index(features: pd.DataFrame) -> np.ndarray:
    return features["match_outcome"].map(M.LABEL_TO_OUTCOME).to_numpy().astype(int)


def shootout_vectors(df: pd.DataFrame, shootouts: dict) -> tuple[np.ndarray, np.ndarray]:
    """(knockout mask, shootout_winner_is_home) for M.credit_shootouts."""
    dates = pd.to_datetime(df["match_date"]).dt.strftime("%Y-%m-%d").to_numpy()
    sw = np.full(len(df), np.nan)
    for i, (d, h, a) in enumerate(zip(dates, df["home_team"], df["away_team"])):
        w = shootouts.get((d, h, a))
        if w is not None:
            sw[i] = 1.0 if w == h else (0.0 if w == a else np.nan)
    stage = df.get("home_competition_stage", pd.Series("group", index=df.index))
    ko = ~stage.fillna("group").astype(str).str.lower().isin(NON_KO_STAGES).to_numpy()
    return ko, sw


def _weights(df: pd.DataFrame) -> np.ndarray:
    return df["home_competition_id"].map(TOURNAMENT_WEIGHTS).fillna(1.0).to_numpy(float)


def _X(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return df[cols].fillna(0.0).astype(float)


def _y_model(df: pd.DataFrame) -> np.ndarray:
    from ml.config import TARGET_ENCODE
    return df["match_outcome"].map(TARGET_ENCODE).to_numpy().astype(int)


def fit_predict_base(name: str, train: pd.DataFrame, test: pd.DataFrame,
                     feature_cols: list[str], start: pd.Timestamp) -> tuple[np.ndarray, dict]:
    """Fit one base model; returns probabilities in outcome order (home/draw/away), not model label order."""
    w = _weights(train)
    if name == "gbm":
        m = make_best_boosting_pipeline()
        m.fit(_X(train, feature_cols), _y_model(train), clf__sample_weight=w)
        return M.from_model_proba(m.predict_proba(_X(test, feature_cols))), {}
    if name == "gbm_raw":
        m = make_best_boosting_pipeline(calibrate=False)
        m.fit(_X(train, feature_cols), _y_model(train), clf__sample_weight=w)
        return M.from_model_proba(m.predict_proba(_X(test, feature_cols))), {}
    if name == "logistic_123":
        m = make_logistic_pipeline()
        m.fit(_X(train, feature_cols), _y_model(train), clf__sample_weight=w)
        return M.from_model_proba(m.predict_proba(_X(test, feature_cols))), {}
    if name == "elo_logistic":
        m = Pipeline([("scale", StandardScaler()),
                      ("clf", LogisticRegression(max_iter=2000, random_state=RANDOM_SEED))])
        m.fit(_X(train, ELO_COLS), _y_model(train), clf__sample_weight=w)
        return M.from_model_proba(m.predict_proba(_X(test, ELO_COLS))), {}
    if name == "priors":
        y = outcome_index(train)
        pri = np.bincount(y, minlength=3) / len(y)
        return np.tile(pri, (len(test), 1)), {"priors": pri.round(4).tolist()}
    if name == "favorite":
        y = outcome_index(train)
        home_fav = train["diff_elo"].fillna(0).to_numpy() >= 0
        fav_win = np.where(home_fav, y == M.HOME, y == M.AWAY).mean()
        draw = (y == M.DRAW).mean()
        dog = 1.0 - fav_win - draw
        t_home_fav = test["diff_elo"].fillna(0).to_numpy() >= 0
        p = np.where(t_home_fav[:, None], [fav_win, draw, dog], [dog, draw, fav_win])
        return p, {"fav_win": round(float(fav_win), 4), "draw": round(float(draw), 4)}
    if name == "dixon_coles":
        lo = start - pd.DateOffset(years=DC_WINDOW_YEARS)
        tr = train[pd.to_datetime(train["match_date"]) >= lo]
        dc = DixonColes(xi=DC_XI, l2=DC_L2).fit(
            tr["home_team"], tr["away_team"], tr["goals_for"], tr["goals_against"],
            tr["home_is_neutral_venue"].fillna(0).astype(bool), tr["match_date"],
            ref_date=start, weights=_weights(tr))
        p = dc.predict_outcome_proba(test["home_team"], test["away_team"],
                                     test["home_is_neutral_venue"].fillna(0).astype(bool))
        return p, {"rho": round(float(dc.rho_), 4), "home_adv": round(float(dc.home_adv_), 4),
                   "converged": dc.converged_, "n_train": dc.n_train_}
    raise ValueError(name)


def post_process(fold: Fold, folds: list[Fold], preds: dict, y_all: np.ndarray,
                 models: list[str]) -> tuple[dict, dict]:
    # Only folds that finished before this one started, so post-processing never sees the future.
    prior = [f for f in folds if f.end < fold.start and f.name in preds]
    if not prior:
        return {}, {}
    cat = lambda key: np.vstack([preds[f.name][key] for f in prior])  # noqa: E731
    y_prior = np.concatenate([y_all[f.test_index] for f in prior])
    cur = preds[fold.name]
    out, params = {}, {"n_prior_matches": int(len(y_prior)),
                       "prior_folds": [f.name for f in prior]}

    have = lambda *ks: all(k in cur for k in ks)  # noqa: E731
    if have("gbm"):
        g_prior, g = cat("gbm"), cur["gbm"]
        out["gbm_drawcal_shipped"] = apply_threshold_draw_cal(
            g, DRAW_CALIBRATION_THRESHOLD, DRAW_CALIBRATION_ALPHA)
        tdc = ThresholdDrawCal().fit(g_prior, y_prior)
        out["gbm_drawcal_wf"], params["gbm_drawcal_wf"] = tdc.transform(g), tdc.params()
        ts = TemperatureScaler().fit(g_prior, y_prior)
        out["gbm_temp"], params["gbm_temp"] = ts.transform(g), ts.params()
        db = DrawBiasScaler().fit(g_prior, y_prior)
        out["gbm_drawbias"], params["gbm_drawbias"] = db.transform(g), db.params()
    if have("gbm_raw"):
        ts = TemperatureScaler().fit(cat("gbm_raw"), y_prior)
        out["gbm_raw_temp"], params["gbm_raw_temp"] = ts.transform(cur["gbm_raw"]), ts.params()
    if have("gbm", "dixon_coles"):
        g_prior, d_prior = cat("gbm"), cat("dixon_coles")
        lp = LinearPool().fit(g_prior, d_prior, y_prior)
        b_prior, b = lp.transform(g_prior, d_prior), lp.transform(cur["gbm"], cur["dixon_coles"])
        out["blend"], params["blend"] = b, lp.params()
        ts = TemperatureScaler().fit(b_prior, y_prior)
        out["blend_temp"], params["blend_temp"] = ts.transform(b), {**lp.params(), **ts.params()}
        db = DrawBiasScaler().fit(b_prior, y_prior)
        out["blend_drawbias"], params["blend_drawbias"] = (
            db.transform(b), {**lp.params(), **db.params()})
    if have("elo_logistic", "dixon_coles"):
        lp = LinearPool().fit(cat("elo_logistic"), cat("dixon_coles"), y_prior)
        out["elo_dc_blend"] = lp.transform(cur["elo_logistic"], cur["dixon_coles"])
        params["elo_dc_blend"] = lp.params()
    return {k: v for k, v in out.items() if k in models}, params


def _pooled(names, folds, preds, y_all, ko_all, sw_all, idx_filter=None):
    out = {}
    for name in names:
        fs = [f for f in folds if not f.warmup and name in preds.get(f.name, {})]
        if idx_filter:
            fs = [f for f in fs if idx_filter(f)]
        if not fs:
            continue
        p = np.vstack([preds[f.name][name] for f in fs])
        ix = np.concatenate([f.test_index for f in fs])
        out[name] = M.score_raw_and_credited(p, y_all[ix], ko_all[ix], sw_all[ix],
                                             with_reliability=True)
        out[name]["n_tournaments"] = len(fs)
    return out


def _table(pooled: dict, title: str) -> str:
    cols = ["model", "n", "RPS", "LL raw", "LL credited", "Brier", "acc", "draw recall", "ECE"]
    rows = sorted(pooled.items(), key=lambda kv: kv[1]["rps"])
    lines = [f"### {title}", "", "| " + " | ".join(cols) + " |",
             "|" + "---|" * len(cols)]
    for name, m in rows:
        lines.append(
            f"| {name} | {m['n']} | {m['rps']:.4f} | {m['log_loss_raw']:.4f} | "
            f"{m['log_loss_shootout_credited']:.4f} | {m['brier']:.4f} | "
            f"{m['accuracy']:.3f} | {m['draw_recall']:.3f} | "
            f"{m['reliability']['ece_mean']:.4f} |")
    return "\n".join(lines)


def run(models: list[str], max_folds: int | None = None, rebuild: bool = False,
        out_dir: Path | None = None) -> Path:
    from ml.pipeline.train import select_feature_columns
    t0 = time.time()
    features = load_features(rebuild=rebuild).reset_index(drop=True)
    feature_cols = select_feature_columns(features)
    features["match_date"] = pd.to_datetime(features["match_date"])
    y_all = outcome_index(features)
    ko_all, sw_all = shootout_vectors(features, load_shootouts())

    folds = find_tournament_folds(features)
    if max_folds:
        folds = folds[:max_folds]
    logger.info("%d folds (%d warm-up, %d reported, %d reported matches)",
                len(folds), sum(f.warmup for f in folds), sum(not f.warmup for f in folds),
                sum(len(f.test_index) for f in folds if not f.warmup))

    base = [m for m in BASE_MODELS if m in models]
    preds: dict[str, dict[str, np.ndarray]] = {}
    info: dict[str, dict] = {}
    for f in folds:
        tf = time.time()
        tr_mask = f.train_mask(features["match_date"])
        train, test = features[tr_mask], features.iloc[f.test_index]
        assert train["match_date"].max() < test["match_date"].min()
        preds[f.name], info[f.name] = {}, {
            "competition_id": f.competition_id, "start": str(f.start.date()),
            "end": str(f.end.date()), "n_train": int(tr_mask.sum()),
            "train_max_date": str(train["match_date"].max().date()),
            "n_test": int(len(test)), "warmup": f.warmup, "base_info": {}}
        for name in base:
            p, extra = fit_predict_base(name, train, test, feature_cols, f.start)
            preds[f.name][name] = M.normalize(p)
            if extra:
                info[f.name]["base_info"][name] = extra
        logger.info("fold %-24s n_test=%3d  n_train=%5d  %.1fs", f.name, len(test),
                    tr_mask.sum(), time.time() - tf)

    post = [m for m in POST_MODELS if m in models]
    for f in folds:
        out, params = post_process(f, folds, preds, y_all, post)
        preds[f.name].update(out)
        info[f.name]["post_params"] = params

    names = base + post
    per_tournament = {}
    for f in folds:
        ix = f.test_index
        per_tournament[f.name] = {**info[f.name], "models": {
            n: M.score_raw_and_credited(preds[f.name][n], y_all[ix], ko_all[ix], sw_all[ix])
            for n in names if n in preds[f.name]}}

    pooled = _pooled(names, folds, preds, y_all, ko_all, sw_all)
    pooled_ex26 = _pooled(names, folds, preds, y_all, ko_all, sw_all,
                          idx_filter=lambda f: f.name != "fifa_world_cup_2026")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = out_dir or ARTIFACTS_DIR / f"backtest_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    strip = lambda d: {k: {kk: vv for kk, vv in v.items() if kk != "reliability"}  # noqa: E731
                       for k, v in d.items()}
    meta = {
        "run_id": run_id, "models": names,
        "config": {"warmup_start": str(WARMUP_START.date()),
                   "report_start": str(REPORT_START.date()),
                   "edition_gap_days": EDITION_GAP_DAYS,
                   "dixon_coles": {"xi": DC_XI, "l2": DC_L2, "window_years": DC_WINDOW_YEARS},
                   "n_features": len(feature_cols)},
        "n_folds": len(folds),
        "n_reported_matches": int(sum(len(f.test_index) for f in folds if not f.warmup)),
        "pooled": strip(pooled),
        "pooled_ex_wc2026": strip(pooled_ex26),
        "per_tournament": per_tournament,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (out_dir / "metrics.json").write_text(json.dumps(meta, indent=2))

    best = min(pooled, key=lambda k: pooled[k]["rps"]) if pooled else None
    (out_dir / "reliability.json").write_text(json.dumps({
        "run_id": run_id, "scope": "pooled reported folds (2014-2026), raw W/D/L",
        "best_model_by_rps": best,
        "models": {k: {"n": v["n"], **v["reliability"]} for k, v in pooled.items()},
        "per_fold_ece": {f.name: {n: M.reliability(preds[f.name][n], y_all[f.test_index])["ece_mean"]
                                  for n in names if n in preds[f.name]}
                         for f in folds if not f.warmup},
    }, indent=2))

    rows = []
    for f in folds:
        sub = features.iloc[f.test_index]
        for n in names:
            if n not in preds[f.name]:
                continue
            p = preds[f.name][n]
            rows.append(pd.DataFrame({
                "fold": f.name, "warmup": f.warmup, "model": n,
                "match_date": sub["match_date"].dt.strftime("%Y-%m-%d").to_numpy(),
                "home_team": sub["home_team"].to_numpy(), "away_team": sub["away_team"].to_numpy(),
                "goals_home": sub["goals_for"].to_numpy(), "goals_away": sub["goals_against"].to_numpy(),
                "outcome": np.array(M.OUTCOMES)[y_all[f.test_index]],
                "p_home": p[:, 0].round(5), "p_draw": p[:, 1].round(5), "p_away": p[:, 2].round(5)}))
    if rows:
        pd.concat(rows).to_csv(out_dir / "predictions.csv", index=False)

    summary = "\n\n".join([
        f"# Backtest {run_id}",
        f"{meta['n_reported_matches']} reported matches over "
        f"{sum(not f.warmup for f in folds)} tournaments (+{sum(f.warmup for f in folds)} warm-up).",
        _table(pooled, "Pooled, all reported tournaments 2014-2026"),
        _table(pooled_ex26, "Pooled, excluding WC 2026"),
    ])
    (out_dir / "summary.md").write_text(summary + "\n", encoding="utf-8")
    print(summary)
    logger.info("Backtest done in %.0fs -> %s", time.time() - t0, out_dir)
    return out_dir


def main() -> None:
    ap = argparse.ArgumentParser(description="Walk-forward tournament backtest")
    ap.add_argument("--models", default=",".join(BASE_MODELS + POST_MODELS))
    ap.add_argument("--max-folds", type=int, default=None)
    ap.add_argument("--rebuild-features", action="store_true")
    args = ap.parse_args()
    run([m.strip() for m in args.models.split(",") if m.strip()],
        max_folds=args.max_folds, rebuild=args.rebuild_features)


if __name__ == "__main__":
    main()
