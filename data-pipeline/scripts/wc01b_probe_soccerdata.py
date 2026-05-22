"""
=============================================================================
WC-01b SPIKE: Probe soccerdata FBref for international leagues
=============================================================================

WHAT THIS SCRIPT DOES:
  1. Writes custom league_dict.json under .soccerdata/config/
  2. Imports soccerdata (must happen AFTER league_dict exists)
  3. Calls read_schedule() for each target competition
  4. Prints OK/FAIL per league and saves docs/wc01b_probe_results.json

Used to decide which comps are safe to add to COMPETITIONS in the importer.

SETUP (see docs/VENV.md):
  py -3.12 -m venv data-pipeline\\venv
  .\\data-pipeline\\venv\\Scripts\\pip.exe install -r requirements.txt -r ml\\requirements.txt
  # Google Chrome required for FBref scraping

RUN:
  .\\data-pipeline\\venv\\Scripts\\python.exe data-pipeline/scripts/wc01b_probe_soccerdata.py
=============================================================================
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Repo root (two levels up from data-pipeline/scripts/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SD_DIR = PROJECT_ROOT / ".soccerdata"
CONFIG_DIR = SD_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# soccerdata reads this env var for cache + config location
os.environ["SOCCERDATA_DIR"] = str(SD_DIR)

# ---------------------------------------------------------------------------
# Custom leagues — must be written BEFORE `import soccerdata`
# ---------------------------------------------------------------------------
# soccerdata loads league_dict.json once at import time; editing later has no effect.

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

import soccerdata as sd  # noqa: E402  — intentional late import


def probe(league: str, seasons: list, label: str, *, headless: bool = False) -> dict:
    """
    Try one league + season list; return a result dict for wc01b_probe_results.json.

    Does not raise — failures are captured in result["error"].
    """
    out = {
        "label": label,
        "league": league,
        "seasons": seasons,
        "ok": False,
        "rows": 0,
        "error": None,
    }
    try:
        # soccerdata >=1.9 uses Selenium; headless=False often avoids FBref blocks
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

    # Discovery: which INT-* leagues soccerdata knows about after custom dict
    leagues = sd.FBref.available_leagues()
    intl = [x for x in leagues if x.startswith("INT-")]
    print("INT available_leagues:", intl)
    print()

    # Probe one league at a time — each may launch Chrome and hit FBref
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
        time.sleep(5)  # polite pause between FBref sessions

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
