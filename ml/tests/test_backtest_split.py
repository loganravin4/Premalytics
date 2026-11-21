"""ML-01: the walk-forward split never trains on data at or after a tournament's start."""

import numpy as np
import pandas as pd
import pytest

from ml.pipeline.backtest import Fold, find_tournament_folds, post_process


def _synthetic_corpus() -> pd.DataFrame:
    """Friendlies every few days 2009-2026 plus two editions each of two tournaments."""
    rows = []
    d = pd.Timestamp("2009-01-01")
    i = 0
    while d < pd.Timestamp("2026-12-31"):
        rows.append(("friendly", d, f"T{i % 7}", f"T{(i + 3) % 7}", "martj42", d.year))
        d += pd.Timedelta(days=5)
        i += 1
    for cid, starts in {"fifa_world_cup": ["2014-06-12", "2018-06-14"],
                        "afcon": ["2013-01-19", "2015-01-17"]}.items():
        for s in starts:
            s = pd.Timestamp(s)
            for k in range(20):
                rows.append((cid, s + pd.Timedelta(days=k), f"A{k}", f"B{k}", "martj42", s.year))
    df = pd.DataFrame(rows, columns=["home_competition_id", "match_date", "home_team",
                                     "away_team", "home_source", "season_id"])
    return df.sort_values("match_date", kind="stable").reset_index(drop=True)


def test_every_fold_trains_strictly_before_its_tournament():
    df = _synthetic_corpus()
    folds = find_tournament_folds(df, competitions=["fifa_world_cup", "afcon"],
                                  since=pd.Timestamp("2010-01-01"),
                                  report_start=pd.Timestamp("2014-01-01"))
    assert [f.name for f in folds] == ["afcon_2013", "fifa_world_cup_2014",
                                       "afcon_2015", "fifa_world_cup_2018"]
    for f in folds:
        train = df[f.train_mask(df["match_date"])]
        test = df.iloc[f.test_index]
        assert len(train) > 0
        assert train["match_date"].max() < f.start
        assert test["match_date"].min() == f.start
        assert not (df["match_date"][f.train_mask(df["match_date"])] >= f.start).any()
        assert (test["home_competition_id"] == f.competition_id).all()
        # no scored match is in its own training set
        assert not np.intersect1d(np.flatnonzero(f.train_mask(df["match_date"])),
                                  f.test_index).size
    assert [f.warmup for f in folds] == [True, False, False, False]


def test_same_day_matches_are_excluded_from_training():
    df = _synthetic_corpus()
    folds = find_tournament_folds(df, competitions=["fifa_world_cup"],
                                  since=pd.Timestamp("2010-01-01"))
    f = folds[0]
    # a friendly on the tournament's opening day must not train that fold
    extra = pd.DataFrame([{"home_competition_id": "friendly", "match_date": f.start,
                           "home_team": "X", "away_team": "Y", "home_source": "martj42",
                           "season_id": 2014}])
    df2 = pd.concat([df, extra], ignore_index=True)
    assert not f.train_mask(df2["match_date"])[len(df2) - 1]


def test_swapped_source_duplicates_scored_once():
    df = _synthetic_corpus()
    s = pd.Timestamp("2014-06-12")
    dup = pd.DataFrame([{"home_competition_id": "fifa_world_cup", "match_date": s,
                         "home_team": "B0", "away_team": "A0", "home_source": "fbref",
                         "season_id": 2014}])
    df = pd.concat([df, dup], ignore_index=True).sort_values("match_date", kind="stable")
    df = df.reset_index(drop=True)
    f = [x for x in find_tournament_folds(df, competitions=["fifa_world_cup"],
                                          since=pd.Timestamp("2010-01-01"))
         if x.name == "fifa_world_cup_2014"][0]
    assert len(f.test_index) == 20
    kept = df.iloc[f.test_index]
    assert ((kept["home_team"] == "B0") & (kept["home_source"] == "fbref")).sum() == 1


def test_post_processing_only_uses_folds_finished_before_start():
    rng = np.random.default_rng(0)
    mk = lambda n, s, e, idx: Fold(n, "x", pd.Timestamp(s), pd.Timestamp(e), idx, False)  # noqa: E731
    folds = [mk("a", "2014-01-01", "2014-01-20", np.arange(0, 30)),
             # Overlaps c's start, so c can't use it
             mk("b", "2014-01-10", "2014-02-01", np.arange(30, 60)),
             mk("c", "2014-01-25", "2014-02-10", np.arange(60, 90))]
    y = rng.integers(0, 3, 90)
    preds = {f.name: {"gbm": rng.dirichlet([2, 1, 2], 30)} for f in folds}
    _, params = post_process(folds[2], folds, preds, y, ["gbm_temp"])
    assert params["prior_folds"] == ["a"]
    out, params = post_process(folds[0], folds, preds, y, ["gbm_temp"])
    assert out == {} and params == {}


@pytest.mark.parametrize("gap_days", [10, 60])
def test_edition_split_by_gap(gap_days):
    base = pd.Timestamp("2015-06-01")
    dates = [base + pd.Timedelta(days=k) for k in range(20)]
    dates += [dates[-1] + pd.Timedelta(days=gap_days + k) for k in range(20)]
    df = pd.DataFrame({"home_competition_id": "copa_america", "match_date": dates,
                       "home_team": [f"H{k}" for k in range(40)],
                       "away_team": [f"A{k}" for k in range(40)],
                       "home_source": "martj42", "season_id": 2015})
    folds = find_tournament_folds(df, competitions=["copa_america"],
                                  since=pd.Timestamp("2010-01-01"))
    # Both gaps are under the 90-day edition split
    assert len(folds) == 1
