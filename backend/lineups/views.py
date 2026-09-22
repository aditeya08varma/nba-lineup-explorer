from rest_framework.response import Response
from rest_framework.views import APIView

from lineups.aggregate import get_lineup_summary
from lineups.models import Team

SORT_FIELDS = ['net_rating', 'point_diff', 'off_rating', 'def_rating', 'oreb_pct', 'dreb_pct', 'total_possessions']


def _parse_int(request, key, default, minimum=None, maximum=None):
    try:
        value = int(request.query_params.get(key, default))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _parse_choice(request, key, default, choices):
    value = request.query_params.get(key, default)
    return value if value in choices else default


class LineupSummary(APIView):
    def get(self, request):
        season = request.query_params.get('season', '2024-25')
        team_id = _parse_int(request, 'team_id', None) if request.query_params.get('team_id') else None
        player_id = _parse_int(request, 'player_id', None) if request.query_params.get('player_id') else None
        rows = get_lineup_summary(
            season=season,
            lineup_size=_parse_int(request, 'lineup_size', 5, minimum=1, maximum=5),
            team_id=team_id,
            player_id=player_id,
            min_possessions=_parse_int(request, 'min_possessions', 0, minimum=0),
            sort_by=_parse_choice(request, 'sort_by', 'net_rating', SORT_FIELDS),
            order=_parse_choice(request, 'order', 'desc', ['asc', 'desc']),
            limit=_parse_int(request, 'limit', 0, minimum=0),
        )
        return Response(rows)


class TeamList(APIView):
    def get(self, request):
        return Response(list(Team.objects.values('id', 'abbreviation', 'name').order_by('name')))
