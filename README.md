# fqae: Football Quantitative Analytics Engine

Research and paper-trading tool. Environment managed with [uv](https://docs.astral.sh/uv/).

## Setup
    uv sync            # creates .venv, installs deps + dev group from uv.lock
    uv run pytest

## Load history
Download CSVs from football-data.co.uk (e.g. https://www.football-data.co.uk/mmz4281/2324/E0.csv)
into `data/raw/` named `<season>_<div>.csv` (`2324_E0.csv`, `2324_SP1.csv`, `2324_I1.csv`,
`2324_D1.csv`, `2324_F1.csv`, `2324_E1.csv`), then:

    uv run python -m fqae.jobs.load_history --bootstrap

Add a dependency with `uv add <pkg>` (dev: `uv add --dev <pkg>`); commit `uv.lock`.
Copy `.env.example` to `.env` for API keys (never commit it).

## Scheduled snapshots (GitHub Actions)
1. Push this repo to GitHub (never commit `.env`).
2. Repo -> Settings -> Secrets and variables -> Actions -> New secret: `THE_ODDS_API_KEY`.
3. Repo -> Settings -> Actions -> General -> Workflow permissions -> **Read and write permissions**.
4. Actions tab -> "snapshot" -> Run workflow (tick "force_open" for a first pull). The first run creates a `data` branch.
5. Pull the data locally: `git fetch origin data && git worktree add store origin/data`, then
   `uv run python -m fqae.jobs.import_store store`.

Credit plan (free tier 500/month, hard stop at 450): 2 credits per pull (h2h + totals, region eu).
"close" pulls (kickoff within 25 min) have priority; "open" pulls (Thu/Fri) stop when fewer than 150 credits remain.
Dry run locally: `uv run python -m fqae.jobs.snapshot --store store --dry-run`
