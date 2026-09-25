"""Turn one game's play-by-play into Possession rows with correct 5-man
lineups on both sides.

On-court lineups come from the GameRotation endpoint (NBA's own authoritative
player stint data: in/out times in tenths of a second of elapsed game time),
not from parsing "SUB: X FOR Y" text in the play-by-play feed. That text log
is known to sometimes drop substitution events; GameRotation doesn't have
that problem.
"""
import time

import pandas as pd
from nba_api.stats.endpoints import boxscoretraditionalv3, gamerotation, playbyplayv3

PERIOD_LENGTH_REGULATION = 7200  # 12 minutes, in tenths of a second
PERIOD_LENGTH_OT = 3000  # 5 minutes, in tenths of a second

POSSESSION_STAT_FIELDS = [
    'points', 'fg_made', 'fg_attempted', 'fg2_made', 'fg2_attempted',
    'fg3_made', 'fg3_attempted', 'ft_made', 'ft_attempted',
    'offensive_rebounds', 'defensive_rebounds', 'assists', 'turnovers',
    'offensive_fouls', 'steals', 'blocks', 'defensive_fouls',
]


def elapsed_time(period, clock_str):
    """Convert (period, 'PT11M24.00S') into elapsed tenths-of-a-second since
    game start, on the same time basis GameRotation uses."""
    period = int(period)
    minutes = int(clock_str[2:clock_str.index('M')])
    seconds = float(clock_str[clock_str.index('M') + 1:-1])
    remaining = (minutes * 60 + seconds) * 10

    if period <= 4:
        period_start = (period - 1) * PERIOD_LENGTH_REGULATION
        period_length = PERIOD_LENGTH_REGULATION
    else:
        period_start = 4 * PERIOD_LENGTH_REGULATION + (period - 5) * PERIOD_LENGTH_OT
        period_length = PERIOD_LENGTH_OT

    return period_start + (period_length - remaining)


def _load_rotation(game_id):
    rot = gamerotation.GameRotation(game_id=game_id)
    all_stints = pd.concat(rot.get_data_frames(), ignore_index=True)
    stints = {}
    for team_id, g in all_stints.groupby('TEAM_ID'):
        stints[int(team_id)] = list(zip(g['PERSON_ID'].astype(int), g['IN_TIME_REAL'], g['OUT_TIME_REAL']))
    return stints


def _lineup_at(stints, team_id, t):
    return {pid for pid, in_t, out_t in stints[team_id] if in_t <= t < out_t}


def _empty_stats():
    return {key: 0 for key in POSSESSION_STAT_FIELDS}


def fetch_game_roster_and_teams(game_id):
    """Returns (players: list of dicts, teams: list of dicts, home_team_id, away_team_id)."""
    box = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
    player_df, home_team_df, away_team_df = box.get_data_frames()
    players = [
        {'id': int(r.personId), 'first_name': r.firstName, 'last_name': r.familyName, 'team_id': int(r.teamId)}
        for r in player_df.itertuples()
    ]
    teams = [
        {'id': int(r.teamId), 'abbreviation': r.teamTricode, 'name': f'{r.teamCity} {r.teamName}'}
        for r in pd.concat([home_team_df, away_team_df]).itertuples()
    ]
    return players, teams, int(home_team_df.iloc[0]['teamId']), int(away_team_df.iloc[0]['teamId'])


def reconstruct_possessions(game_id):
    """Returns a list of possession dicts, ready to become Possession rows.
    Makes two nba_api calls (rotation, play-by-play); the caller is responsible
    for rate-limiting between games.
    """
    stints = _load_rotation(game_id)
    time.sleep(0.6)
    pbp = playbyplayv3.PlayByPlayV3(game_id=game_id).get_data_frames()[0]
    pbp = pbp.sort_values(['period', 'actionNumber']).reset_index(drop=True)

    team_ids = list(stints.keys())
    possessions = []
    current = None

    def start_possession(offense_team, t, period):
        nonlocal current
        other = [tm for tm in team_ids if tm != offense_team][0]
        current = {
            'period': period,
            'start_time': t,
            'offensive_team_id': offense_team,
            'defensive_team_id': other,
            'offensive_player_ids': sorted(_lineup_at(stints, offense_team, t)),
            'defensive_player_ids': sorted(_lineup_at(stints, other, t)),
            **_empty_stats(),
        }

    def close_possession():
        nonlocal current
        if current is not None and len(current['offensive_player_ids']) == 5 and len(current['defensive_player_ids']) == 5:
            possessions.append(current)
        current = None

    last_period = None
    for row in pbp.itertuples():
        action_type = row.actionType
        desc = str(row.description)

        if row.period != last_period:
            close_possession()
            last_period = row.period

        # Steals and blocks appear as their own row with a blank actionType, right
        # after the turnover/missed shot they relate to. They annotate a possession
        # rather than starting a new one, so handle them before anything else.
        if not action_type or pd.isna(action_type):
            if 'STEAL' in desc and possessions:
                possessions[-1]['steals'] += 1
            elif 'BLOCK' in desc and current is not None:
                current['blocks'] += 1
            continue

        if action_type in ('Substitution', 'period', 'Timeout', 'Instant Replay', 'Jump Ball', 'Violation'):
            continue

        team_id = row.teamId
        if pd.isna(team_id) or team_id == 0:
            continue
        team_id = int(team_id)
        t = elapsed_time(row.period, row.clock)

        if current is None:
            start_possession(team_id, t, row.period)
        elif team_id != current['offensive_team_id'] and action_type in ('Made Shot', 'Missed Shot', 'Turnover', 'Free Throw'):
            close_possession()
            start_possession(team_id, t, row.period)

        on_offense = team_id == current['offensive_team_id']

        if action_type == 'Made Shot':
            value = int(row.shotValue) if not pd.isna(row.shotValue) else 2
            current['points'] += value
            current['fg_made'] += 1
            current['fg_attempted'] += 1
            if value == 3:
                current['fg3_made'] += 1
                current['fg3_attempted'] += 1
            else:
                current['fg2_made'] += 1
                current['fg2_attempted'] += 1
            if 'AST' in desc:
                current['assists'] += 1
            close_possession()
        elif action_type == 'Missed Shot':
            current['fg_attempted'] += 1
            if row.shotValue == 3:
                current['fg3_attempted'] += 1
            else:
                current['fg2_attempted'] += 1
        elif action_type == 'Free Throw':
            current['ft_attempted'] += 1
            if 'MISS' not in desc:
                current['ft_made'] += 1
                current['points'] += 1
        elif action_type == 'Turnover':
            current['turnovers'] += 1
            close_possession()
        elif action_type == 'Foul':
            if on_offense:
                current['offensive_fouls'] += 1
            else:
                current['defensive_fouls'] += 1
        elif action_type == 'Rebound':
            if on_offense:
                current['offensive_rebounds'] += 1
                continue  # offensive rebound: possession continues
            current['defensive_rebounds'] += 1
            close_possession()
            start_possession(team_id, t, row.period)

    close_possession()
    return possessions
