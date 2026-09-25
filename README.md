# NBA Lineup Explorer

A personal project: a lineup analytics tool built against real NBA
play-by-play data. It covers possession-level aggregation, a Django + Postgres
backend, and an Angular frontend with filters, a sortable table, a chart, and
a click-through detail panel.

## Data

Full 2024-25 NBA regular season, pulled via [`nba_api`](https://github.com/swar/nba_api):
1,230 games, 272,934 reconstructed possessions, 577 players, 30 teams.

Possessions are built from play-by-play events, with on-court lineups taken
from the `GameRotation` endpoint (NBA's own authoritative player stint data)
rather than parsed from substitution text in the play-by-play feed, since
that text log is known to sometimes drop events. Validated against the
official box score on a pilot game: points, steals, and blocks all matched
exactly, both teams.

## Structure

- `backend/lineups/reconstruct.py`: turns one game's play-by-play into
  possessions with correct 5-man lineups on both sides.
- `backend/lineups/ingest.py` / `management/commands/bulk_ingest.py`:
  resumable, rate-limited bulk pull for a full season.
- `backend/lineups/aggregate.py`: groups possessions into lineup-level
  stats (net rating, rebound percentages, etc.), built against this
  project's own schema.
- `frontend/src/app/lineup-explorer/`: filters, sortable table, offense vs
  defense chart, and a detail panel, in Angular with signals (this Angular
  version defaults to zoneless change detection).

## Running it locally

```bash
# backend
cd backend
source ~/.venvs/nba-explorer/bin/activate
python manage.py migrate
python manage.py bulk_ingest --season 2024-25   # takes about an hour
python manage.py runserver 8010

# frontend
cd frontend
npm install --legacy-peer-deps   # a known npm/Angular peer-dep resolver bug needs this flag
npx ng serve --port 4210
```

## Known rough edges

- The "Team" filter's selected-value text doesn't render next to its
  floated label when set to "All teams": cosmetic only, filtering itself
  works.
- No automated tests yet.
