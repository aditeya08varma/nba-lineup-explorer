"""Pull an entire season's games and ingest them, one at a time, resumably.

Usage:
    python manage.py bulk_ingest --season 2024-25

Safe to stop (Ctrl+C) and re-run: games already present in the database (with
at least one possession) are skipped, so a re-run only fills in what's missing.
Progress and errors are printed with a timestamp so they can be tailed from a log file.
"""
import datetime
import time

from django.core.management.base import BaseCommand

from lineups.ingest import ingest_game, list_season_games
from lineups.models import Possession


def log(message):
    print(f'[{datetime.datetime.now().isoformat(timespec="seconds")}] {message}', flush=True)


class Command(BaseCommand):
    help = 'Pull and ingest a full season of games from nba_api, resumably.'

    def add_arguments(self, parser):
        parser.add_argument('--season', required=True, help="e.g. '2024-25'")
        parser.add_argument('--limit', type=int, default=None, help='Only process this many games (for testing).')

    def handle(self, *args, **options):
        season = options['season']
        limit = options['limit']

        log(f'Listing games for season {season}...')
        games = list_season_games(season)
        log(f'{len(games)} games found.')
        if limit:
            games = games[:limit]

        already_done = set(
            Possession.objects.filter(game__season=season).values_list('game_id', flat=True).distinct()
        )
        log(f'{len(already_done)} games already ingested; resuming the rest.')

        done_count = 0
        error_count = 0
        for i, (game_id, game_date, home_id, away_id) in enumerate(games, start=1):
            if game_id in already_done:
                continue
            try:
                n = ingest_game(game_id, game_date, home_id, away_id, season)
                done_count += 1
                log(f'[{i}/{len(games)}] {game_id} ({game_date}): {n} possessions')
            except Exception as exc:  # keep going; one bad game shouldn't kill an hours-long run
                error_count += 1
                log(f'[{i}/{len(games)}] {game_id} ({game_date}): FAILED - {exc!r}')
            time.sleep(0.5)

        log(f'Done. {done_count} games ingested this run, {error_count} failed, '
            f'{len(already_done) + done_count} total for {season}.')
