"""WC-01b spike: probe which international leagues soccerdata's FBref reader can fetch; writes docs/wc01b_probe_results.json."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SD_DIR = PROJECT_ROOT / ".soccerdata"
CONFIG_DIR = SD_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

os.environ["SOCCERDATA_DIR"] = str(SD_DIR)

# soccerdata reads league_dict.json once at import, so it must be written first
CUSTOM_LEAGUES = {
    "INT-Copa America": {"FBref": "Copa América", "season_code": "single-year"},
    "INT-WCQ UEFA": {"FBref": "UEFA World Cup Qualifiers", "season_code": "single-year"},
    "INT-WCQ CONMEBOL": {"FBref": "CONMEBOL World Cup Qualifiers", "season_code": "single-year"},
    "INT-Nations League": {
        "FBref": "UEFA Nations League",
        "season_start": "Sep",
        "season_end": "Jun",
    },
}
(CONFIG_DIR / "league_dict.json").write_text(
    json.dumps(CUSTOM_LEAGUES, indent=2), encoding="utf-8"
)

import soccerdata as sd  # noqa: E402


def probe(league: str, seasons: list, label: str, *, headless: bool = False) -> dict:
    out = {
        "label": label,
        "league": league,
        "seasons": seasons,
        "ok": False,
        "rows": 0,
        "error": None,
    }
    try:
        # headless=False often avoids FBref blocks
        fb = sd.FBref(leagues=league, seasons=seasons, headless=headless)
        df = fb.read_schedule()
        out["ok"] = True
        out["rows"] = len(df)
        if len(df) > 0 and "date" in df.columns:
            out["date_min"] = str(df["date"].min())
            out["date_max"] = str(df["date"].max())
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def main() -> None:
    print(f"soccerdata {getattr(sd, '__version__', 'unknown')}")
    print(f"SOCCERDATA_DIR={SD_DIR}\n")

    leagues = sd.FBref.available_leagues()
    intl = [x for x in leagues if x.startswith("INT-")]
    print("INT available_leagues:", intl)
    print()

    probes = [
        ("INT-World Cup", [2018, 2022], "World Cup"),
        ("INT-European Championship", [2020, 2024], "Euro"),
        ("INT-Copa America", [2021, 2024], "Copa América"),
        ("INT-WCQ UEFA", [2022, 2024], "UEFA World Cup Qualifiers"),
        ("INT-WCQ CONMEBOL", [2022, 2024], "CONMEBOL World Cup Qualifiers"),
        ("INT-Nations League", [2022, 2024], "UEFA Nations League"),
    ]
    results = []
    for league, seasons, label in probes:
        results.append(probe(league, seasons, label, headless=False))
        time.sleep(5)

    print("\n=== RESULTS ===")
    for r in results:
        status = "OK" if r["ok"] else "FAIL"
        extra = f" rows={r['rows']}" if r["ok"] else f" {r['error']}"
        print(f"  [{status}] {r['label']}: {r['league']}{extra}")

    out_path = PROJECT_ROOT / "docs" / "wc01b_probe_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
