"""Aggregate possessions into lineup-level stats.

Same shape of approach as the OKC Thunder assessment: group possessions by the
set of players on court, sum both sides, derive rate stats. Rewritten fresh
against this project's own schema. A full season is roughly 270,000
possessions rather than ~1,300, so this streams them from the database with
.iterator() instead of loading them all into memory at once, but still builds
the lineup groupings in Python. If this ever gets too slow for smaller lineup
sizes (more sub-lineup combinations per possession), the next step would be
pushing the grouping into SQL — not needed yet at this scale.
"""
from collections import defaultdict
from itertools import combinations

from lineups.models import Player, Possession, Team

STAT_FIELDS = [
    'points', 'fg_made', 'fg_attempted', 'fg2_made', 'fg2_attempted',
    'fg3_made', 'fg3_attempted', 'ft_made', 'ft_attempted',
    'offensive_rebounds', 'defensive_rebounds', 'assists', 'turnovers',
    'offensive_fouls', 'steals', 'blocks', 'defensive_fouls',
]


def _empty_totals():
    totals = {'offensive_possessions': 0, 'defensive_possessions': 0}
    for field in STAT_FIELDS:
        totals['offensive_' + field] = 0
        totals['defensive_' + field] = 0
    return totals


def _pct(made, attempted):
    return made / attempted if attempted else 0


def _per_100(points, possessions):
    return points / possessions * 100 if possessions else None


def _share(part, whole):
    return part / whole if whole else None


def get_lineup_summary(
    season, lineup_size=5, team_id=None, player_id=None, min_possessions=0,
    sort_by='net_rating', order='desc', limit=0,
):
    query = Possession.objects.filter(game__season=season)
    if team_id:
        query = query.filter(offensive_team_id=team_id) | query.filter(defensive_team_id=team_id)

    lineups = defaultdict(_empty_totals)
    for possession in query.only(
        'offensive_team_id', 'defensive_team_id', 'offensive_player_ids', 'defensive_player_ids',
        *STAT_FIELDS,
    ).iterator(chunk_size=2000):
        for lineup in combinations(possession.offensive_player_ids, lineup_size):
            totals = lineups[(possession.offensive_team_id, lineup)]
            totals['offensive_possessions'] += 1
            for field in STAT_FIELDS:
                totals['offensive_' + field] += getattr(possession, field)
        for lineup in combinations(possession.defensive_player_ids, lineup_size):
            totals = lineups[(possession.defensive_team_id, lineup)]
            totals['defensive_possessions'] += 1
            for field in STAT_FIELDS:
                totals['defensive_' + field] += getattr(possession, field)

    players = {p.id: p for p in Player.objects.all()}
    teams = {t.id: t for t in Team.objects.all()}

    rows = []
    for (row_team_id, lineup), totals in lineups.items():
        row = dict(totals)
        row['total_possessions'] = row['offensive_possessions'] + row['defensive_possessions']
        for side in ('offensive', 'defensive'):
            row[side + '_fg_pct'] = _pct(row[side + '_fg_made'], row[side + '_fg_attempted'])
            row[side + '_fg3_pct'] = _pct(row[side + '_fg3_made'], row[side + '_fg3_attempted'])
        row['off_rating'] = _per_100(row['offensive_points'], row['offensive_possessions'])
        row['def_rating'] = _per_100(row['defensive_points'], row['defensive_possessions'])
        row['net_rating'] = (
            row['off_rating'] - row['def_rating'] if row['off_rating'] is not None and row['def_rating'] is not None
            else None
        )
        row['point_diff'] = row['offensive_points'] - row['defensive_points']
        row['oreb_pct'] = _share(row['offensive_offensive_rebounds'], row['offensive_offensive_rebounds'] + row['defensive_defensive_rebounds']) if (row['offensive_offensive_rebounds'] + row['defensive_defensive_rebounds']) else None
        row['dreb_pct'] = _share(row['defensive_defensive_rebounds'], row['defensive_defensive_rebounds'] + row['offensive_offensive_rebounds']) if (row['defensive_defensive_rebounds'] + row['offensive_offensive_rebounds']) else None
        row['team_id'] = row_team_id
        row['team_name'] = teams[row_team_id].name if row_team_id in teams else ''
        row['team_abbreviation'] = teams[row_team_id].abbreviation if row_team_id in teams else ''
        row['player_ids'] = list(lineup)
        row['players'] = [
            {'player_id': pid, 'name': f'{players[pid].first_name} {players[pid].last_name}'}
            for pid in lineup if pid in players
        ]
        rows.append(row)

    if player_id:
        rows = [r for r in rows if player_id in r['player_ids']]
    rows = [r for r in rows if r['total_possessions'] >= min_possessions]

    if rows and sort_by not in rows[0]:
        sort_by = 'net_rating'
    has_value = [r for r in rows if r[sort_by] is not None]
    no_value = [r for r in rows if r[sort_by] is None]
    has_value.sort(key=lambda r: r[sort_by], reverse=(order == 'desc'))
    rows = has_value + no_value
    if limit:
        rows = rows[:limit]
    return rows
