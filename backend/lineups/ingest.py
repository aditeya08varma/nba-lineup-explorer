"""Load one game's teams, players, and reconstructed possessions into the database.
Safe to call more than once for the same game (it clears that game's possessions first).
"""
import time

from django.db import transaction
from nba_api.stats.endpoints import leaguegamefinder

from lineups.models import Game, Player, Possession, Team
from lineups.reconstruct import fetch_game_roster_and_teams, reconstruct_possessions

REQUEST_DELAY_SECONDS = 0.7  # be polite to stats.nba.com between endpoint calls


def list_season_games(season):
    """Returns [(game_id, game_date, home_team_id, away_team_id), ...] for a season,
    one row per game (deduplicated from the two team-perspective rows nba_api gives).

    Home/away is resolved from each row's own TEAM_ABBREVIATION against the matchup
    string ("AWAY @ HOME" or "HOME vs. AWAY"), not from which row happens to contain
    "@": a handful of games (confirmed: 5 of 1230 in the 2024-25 season) have both
    rows carrying an identical matchup string, so that shortcut isn't reliable.
    """
    gf = leaguegamefinder.LeagueGameFinder(
        season_nullable=season, season_type_nullable='Regular Season', league_id_nullable='00',
    )
    df = gf.get_data_frames()[0]
    games = {}
    for row in df.itertuples():
        games.setdefault(row.GAME_ID, {'date': row.GAME_DATE, 'rows': []})
        games[row.GAME_ID]['rows'].append((row.TEAM_ID, row.TEAM_ABBREVIATION, row.MATCHUP))

    out = []
    skipped = []
    for game_id, info in games.items():
        matchup = info['rows'][0][2]
        if '@' in matchup:
            away_abbr, home_abbr = (part.strip() for part in matchup.split('@'))
        else:
            home_abbr, away_abbr = (part.strip() for part in matchup.split('vs.'))

        home_id = next((t for t, abbr, _ in info['rows'] if abbr == home_abbr), None)
        away_id = next((t for t, abbr, _ in info['rows'] if abbr == away_abbr), None)
        if home_id is None or away_id is None:
            skipped.append(game_id)
            continue
        out.append((game_id, info['date'], home_id, away_id))

    if skipped:
        print(f'list_season_games: could not resolve home/away for {len(skipped)} game(s): {skipped}')
    return out


@transaction.atomic
def ingest_game(game_id, game_date, home_team_id, away_team_id, season):
    players, teams, roster_home_id, roster_away_id = fetch_game_roster_and_teams(game_id)
    time.sleep(REQUEST_DELAY_SECONDS)

    for team in teams:
        Team.objects.update_or_create(
            id=team['id'], defaults={'abbreviation': team['abbreviation'], 'name': team['name']},
        )
    for player in players:
        Player.objects.update_or_create(
            id=player['id'], defaults={'first_name': player['first_name'], 'last_name': player['last_name']},
        )

    Game.objects.update_or_create(
        id=game_id,
        defaults={'date': game_date, 'season': season, 'home_team_id': home_team_id, 'away_team_id': away_team_id},
    )

    possessions = reconstruct_possessions(game_id)
    time.sleep(REQUEST_DELAY_SECONDS)

    Possession.objects.filter(game_id=game_id).delete()
    Possession.objects.bulk_create([
        Possession(game_id=game_id, **p) for p in possessions
    ])
    return len(possessions)
