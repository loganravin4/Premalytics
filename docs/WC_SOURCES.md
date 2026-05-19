# WC-01 — Source matrix (WC-00 pivot: soccerdata / FBref)

Aligned with **`docs/WC_HANDOFF.md`** after the **WC-00 pivot** away from paid football-data.org tiers. Primary path is **$0**: soccerdata scraping FBref + StatsBomb open for shot events.

**Acceptance:** every row includes **Used for** (outcome / shots / odds / lineups).

---

## 1. Strategy summary

| Track | Primary source | Why |
|-------|----------------|-----|
| **1 — Match predictor** | soccerdata → FBref (`INT-World Cup`, `INT-European Championship` + custom leagues) | Schedules, scores, team/player match logs, lineups — no API subscription |
| **2 — Shot xG** | StatsBomb open data (WC 2018, 2022) | Shot coordinates + outcomes; FBref does not expose full shot-level tables via soccerdata |
| **3 — Penalties** | Separate public kick datasets | Not from soccerdata |
| **Squad / PL club form** | Archived EPL + ASSESS-01 | Not a WC-01 live source |

**Trade-offs (honest):** soccerdata uses Selenium + FBref — slower backfills, **403/IP blocks** possible. Mitigate: `soccerdata>=1.9`, Chrome, `headless=False`, cache under `.soccerdata/`.

### WC-01b findings (your machine, May 2026)

| Issue | Cause | Fix |
|-------|--------|-----|
| `403 Forbidden` on `fbref.com/en/comps/` | **soccerdata 1.8.7** uses plain `requests`, not Chrome | `pip install "soccerdata>=1.9.0"` in `data-pipeline/venv` |
| `Chrome not found` | Older path or missing browser | Install Chrome; probe uses `headless=False` |
| Custom leagues in `available_leagues` but scrape fails | Still hits `/en/comps/` first | Fix version first; then re-probe |

**If FBref still blocks after 1.9 + Chrome:** use **hybrid ingest** (still $0):

| Role | Source |
|------|--------|
| WC + Euro match results | **football-data.org API** (free tier, `FOOTBALL_DATA_TOKEN`) |
| Copa / qualifiers / lineups | soccerdata FBref when scrape works, else **Defer** |
| Shot-level xG | **StatsBomb open** (unchanged) |

Do not block WC-02 on FBref — write the contract against normalized columns; wire soccerdata **or** football-data in WC-03.

---

## 2. soccerdata + FBref (primary when scrape works)

### 2.1 Install & cache (canonical venv)

Use **`data-pipeline/venv`** with **Python 3.12** (`py -3.12`). See **`docs/VENV.md`**.

```powershell
cd premalytics
.\scripts\setup_venv.ps1
# or: py -3.12 -m venv data-pipeline\venv
#     .\data-pipeline\venv\Scripts\pip.exe install -r requirements.txt -r ml\requirements.txt
```

Do not use bare `python -m venv` (often 3.13 here) or a second venv at repo root.

**Prerequisites:**

1. **`soccerdata>=1.9.0`** — verify: `.\data-pipeline\venv\Scripts\pip.exe show soccerdata`
2. [Google Chrome](https://www.google.com/chrome/) installed

```powershell
.\data-pipeline\venv\Scripts\pip.exe install "soccerdata>=1.9.0,<2"
.\data-pipeline\venv\Scripts\python.exe data-pipeline\scripts\wc01b_probe_soccerdata.py
```

Writes `docs/wc01b_probe_results.json` and caches under `.soccerdata/` (gitignored).

| Setting | Purpose |
|---------|---------|
| `SOCCERDATA_DIR` | Cache root (this repo: `.soccerdata/` at project root) |
| `SOCCERDATA_NOCACHE` | Force refresh when `true` |
| `SOCCERDATA_NOSTORE` | Skip disk cache when `true` (usually leave off) |
| `config/league_dict.json` | Under `SOCCERDATA_DIR` — must exist **before** `import soccerdata` |

Docs: [Getting started](https://soccerdata.readthedocs.io/en/stable/intro.html), [FBref API](https://soccerdata.readthedocs.io/en/stable/reference/fbref.html), [FBref datasource guide](https://soccerdata.readthedocs.io/en/stable/datasources/FBref.html).

### 2.2 Built-in international league IDs

From upstream soccerdata `LEAGUE_DICT` (verify after `pip install`):

| soccerdata ID | FBref competition name | WC-00 use |
|---------------|------------------------|-----------|
| `INT-World Cup` | FIFA World Cup | **Yes** — 2018, 2022, 2026 seasons |
| `INT-European Championship` | UEFA European Football Championship | **Yes** — 2020, 2024 |
| `INT-Women's World Cup` | FIFA Women's World Cup | Out of scope unless added later |

**Example (discovery):**

```python
import soccerdata as sd

print(sd.FBref.available_leagues())  # includes INT-* after install

wc = sd.FBref(leagues="INT-World Cup", seasons=[2018, 2022, 2024])
schedule = wc.read_schedule()
shooting = wc.read_team_match_stats(stat_type="shooting")
lineups = wc.read_lineup(match_id=...)  # per match_id from schedule
```

### 2.3 soccerdata methods → our pipeline

| Method | Returns (summary) | Used for |
|--------|-------------------|----------|
| `read_schedule()` | date, home/away, score, venue, `game_id` | **outcome** |
| `read_team_match_stats(stat_type='schedule')` | GF/GA, result, possession, formation | **outcome** |
| `read_team_match_stats(stat_type='shooting')` | Shots, SoT, xG-style cols if present | **outcome** (aggregates) |
| `read_player_match_stats(stat_type='summary')` | Per-player Gls, Sh, SoT, min | **lineups**, squad features |
| `read_lineup(match_id=...)` | XI, bench, minutes | **lineups** |
| `read_events(match_id=...)` | Goals, cards, subs | **outcome** enrichment |
| `read_player_season_stats()` | Tournament player totals | squad aggregates (ASSESS-01) |

Normalize these in **WC-03** → `match_logs_normalized.csv` shape (WC-02).

### 2.4 Custom leagues (WC-01b spike)

Not built-in for Copa / qualifiers / Nations League. Add via:

`$SOCCERDATA_DIR/config/league_dict.json`

**Important:** write `league_dict.json` **before** the first `import soccerdata` in any process (the library loads it at import time).

Template (committed for probes at `.soccerdata/config/league_dict.json` when you run the script):

```json
{
  "INT-Copa America": {
    "FBref": "Copa América",
    "season_code": "single-year"
  },
  "INT-WCQ UEFA": {
    "FBref": "UEFA World Cup Qualifiers",
    "season_code": "single-year"
  },
  "INT-WCQ CONMEBOL": {
    "FBref": "CONMEBOL World Cup Qualifiers",
    "season_code": "single-year"
  },
  "INT-Nations League": {
    "FBref": "UEFA Nations League",
    "season_start": "Sep",
    "season_end": "Jun"
  }
}
```

#### WC-01b probe results (2026-05-17)

| Competition | Verdict | Evidence |
|-------------|---------|----------|
| `INT-World Cup` | **Use** | soccerdata **1.9.0** + Chrome; WC 2022 schedule **64 rows** verified |
| `INT-European Championship` | **Use** (if scrape OK) | Same |
| `INT-Copa America` | **Experiment** | Custom league loads in `available_leagues`; scrape unverified |
| `INT-WCQ UEFA` / `CONMEBOL` | **Experiment** | Verify FBref comp names on [fbref.com/comps](https://fbref.com/en/comps/) |
| `INT-Nations League` | **Experiment** | Same |
| Friendlies | **Defer** | No comp mapped |
| WC + Euro (fallback) | **Use** | football-data.org **free** API if FBref keeps 403 |

Re-run probe after: `pip install "soccerdata>=1.9.0"` + Chrome + optional `headless=False` (probe default).

| Competition (WC-00) | Status | Action |
|---------------------|--------|--------|
| Copa América 2021, 2024 | **Experiment** | Re-probe after Chrome; fix FBref name if scrape errors |
| WC Qualifiers UEFA / CONMEBOL | **Experiment** | Verify exact FBref competition names |
| Friendlies | **Defer** | Find comp name or skip |

### 2.5 Rate limits & refresh

| Context | Cadence | Notes |
|---------|---------|-------|
| Historical backfill | Once + cache | Script sleep 2–5s between requests; run overnight if needed |
| 2026 tournament | Daily or on match days | `force_cache` only when debugging |
| CI | Use committed fixtures | Do not scrape FBref in unit tests |

### 2.6 License / ToS

- **soccerdata:** [project license](https://github.com/probberechts/soccerdata/blob/master/LICENSE.rst)
- **FBref / Sports Reference:** follow [data use guidelines](https://www.sports-reference.com/data_use.html); attribute in public write-ups
- **No commercial data resale** without checking ToS

---

## 3. StatsBomb open data (Track 2 — shot events)

Unchanged from prior WC-01: free GitHub JSON for **WC 2018 + 2022** shot-level modeling.

| Artifact | Path | Used for |
|----------|------|----------|
| Events | `data/events/{match_id}.json` | **shots** |
| Lineups | `data/lineups/{match_id}.json` | **lineups** (cross-check) |
| Matches | `data/matches/{comp_id}/{season_id}.json` | join keys |

Repo: [statsbomb/open-data](https://github.com/statsbomb/open-data). **2026:** not assumed until published.

---

## 4. football-data.org (free tier — hybrid fallback)

Use when FBref returns **403** or for a **reliable** WC + Euro backbone while Copa/qualifiers stay on FBref experiment.

| Included on €0 plan | WC-00 need |
|---------------------|------------|
| FIFA World Cup, European Championship | Partial overlap with built-in INT-* |
| Copa, qualifiers, friendlies | **Not** on free 12 — do not rely on API for these |
| Lineups / squads / live scores | Paid tiers — use FBref via soccerdata instead |

Auth: `FOOTBALL_DATA_TOKEN` + `X-Auth-Token`. See [pricing](https://www.football-data.org/pricing).

---

## 5. Archived EPL (assess only)

| ID | Source | Used for |
|----|--------|----------|
| PL-ARCH | Local EPL CSV/DB (`docs/PIVOT_INVENTORY.md`) | **None** until ASSESS-01 → possible squad/club-form features |

---

## 6. Odds

| Source | Used for | Status |
|--------|----------|--------|
| Bookmaker APIs | **odds** | **Out of scope** ($0 project) |
| FBref | — | No closing odds in standard soccerdata match tables |

---

## 7. Source matrix

| ID | Provider | Access | Fields (summary) | Date range | Cost | Refresh | Used for |
|----|----------|--------|------------------|------------|------|---------|----------|
| SD-01 | soccerdata / FBref | `FBref('INT-World Cup', seasons=...)` | schedule, scores, game_id | 2018–2026 | $0 | Cache + periodic | **outcome** |
| SD-02 | soccerdata / FBref | `INT-European Championship` | same | 2020, 2024 | $0 | same | **outcome** |
| SD-03 | soccerdata / FBref | `read_team_match_stats(shooting)` | Sh, SoT, xG cols | Per WC-00 comps | $0 | same | **outcome** |
| SD-04 | soccerdata / FBref | `read_player_match_stats`, `read_lineup` | minutes, Sh, XI | Per match | $0 | on demand | **lineups**, squad |
| SD-05 | soccerdata / FBref | Custom `league_dict.json` | TBD | Copa, qualifiers, friendlies | $0 | WC-01b spike | **outcome** (if verified) |
| SB-01 | StatsBomb open | GitHub JSON | shot events | WC 2018, 2022 | $0 | static | **shots** |
| SB-02 | StatsBomb open | lineups JSON | XI | WC 2018, 2022 | $0 | static | **lineups** |
| FD-OPT | football-data.org | REST v4 | fixtures/results | WC, Euro only | $0 tier | optional | **outcome** (fallback) |
| PL-ARCH | Local archive | files | PL player/match | historical | $0 | N/A | ASSESS-01 only |

---

## 8. Gaps & tickets

| Gap | Owner ticket |
|-----|----------------|
| Copa / qualifiers / friendlies league IDs | **WC-01b** |
| Exact FBref `seasons=` for Euro 2020 vs 2021 | **WC-03** spike |
| Shot coordinates for 2026 | StatsBomb publish or defer Track 2 |
| `team_id` = FIFA 3-letter codes | **WC-02** |
| soccerdata IP blocks | proxy guide + committed cache samples |

---

## 9. WC-01 done criteria

- [x] Matrix reflects **soccerdata/FBref primary**, $0
- [x] Every row has **Used for**
- [x] StatsBomb retained for **shots**
- [x] football-data demoted to optional fallback
- [x] **WC-01b:** probe script + venv path documented; built-in INT leagues confirmed
- [x] **WC-01b:** WC 2022 `read_schedule()` OK (see `wc01b_probe_results.json`); run full probe for Euro + custom leagues when ready

**Next:** **WC-01b** (league spike) → **WC-02** (data contract) → **WC-03** (soccerdata importer).
