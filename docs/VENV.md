# Python environment (canonical)

Use **one** virtual environment for data-pipeline, ML, and WC ingest work.

| Setting | Value |
|---------|--------|
| **Python** | **3.12** via Windows launcher: `py -3.12` |
| **Venv path** | `data-pipeline/venv/` |
| **Do not use** | Repo-root `venv/` (legacy), bare `python` (often 3.13 on this machine) |

## Create or recreate the venv

From the repo root:

```powershell
py -3.12 -m venv data-pipeline\venv
.\data-pipeline\venv\Scripts\python.exe -m pip install -U pip
.\data-pipeline\venv\Scripts\pip.exe install -r requirements.txt -r ml\requirements.txt
```

Or run the helper script:

```powershell
.\scripts\setup_venv.ps1
```

## Activate

```powershell
.\data-pipeline\venv\Scripts\Activate.ps1
```

## Run commands

Always prefer the venv interpreter explicitly (avoids wrong Python after activation mistakes):

```powershell
.\data-pipeline\venv\Scripts\python.exe -m pytest ml/tests -q
.\data-pipeline\venv\Scripts\python.exe -m ml.pipeline.train
.\data-pipeline\venv\Scripts\python.exe data-pipeline\scripts\wc01b_probe_soccerdata.py
```

## soccerdata cache

WC ingest uses project-local caches (not inside the venv):

```
premalytics/.soccerdata/      # soccerdata FBref HTML cache
premalytics/downloaded_files/  # SeleniumBase driver temp (auto-created; gitignored)
```

Set optionally: `$env:SOCCERDATA_DIR = "$PWD\.soccerdata"`

## Troubleshooting

- **`numpy` / `pandas` import errors** — venv was likely created with the wrong Python or `pip install -U pandas` pulled pandas 3.x. Recreate with `py -3.12` and reinstall from `requirements.txt` (pins `pandas<3`).
- **Chrome not found** — install [Google Chrome](https://www.google.com/chrome/) for soccerdata FBref scraping.

## If you have an old root `venv/`

Safe to delete after migrating:

```powershell
Remove-Item -Recurse -Force .\venv
```
