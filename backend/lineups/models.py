from django.contrib.postgres.fields import ArrayField
from django.db import models


class Team(models.Model):
    id = models.IntegerField(primary_key=True)  # NBA's own team id
    abbreviation = models.CharField(max_length=5)
    name = models.TextField()


class Player(models.Model):
    id = models.IntegerField(primary_key=True)  # NBA's own person id
    first_name = models.TextField()
    last_name = models.TextField()


class Game(models.Model):
    id = models.CharField(max_length=20, primary_key=True)  # NBA's own game id, e.g. '0022401196'
    date = models.DateField()
    season = models.CharField(max_length=10)  # e.g. '2024-25'
    home_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name='home_games')
    away_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name='away_games')


class Possession(models.Model):
    id = models.AutoField(primary_key=True)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, db_index=True)
    period = models.SmallIntegerField()
    # Elapsed tenths-of-a-second since game start, on the GameRotation time basis.
    start_time = models.IntegerField()

    offensive_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name='offensive_possessions', db_index=True)
    defensive_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name='defensive_possessions', db_index=True)
    offensive_player_ids = ArrayField(models.IntegerField(), size=5)
    defensive_player_ids = ArrayField(models.IntegerField(), size=5)

    points = models.IntegerField(default=0)
    fg_made = models.IntegerField(default=0)
    fg_attempted = models.IntegerField(default=0)
    fg2_made = models.IntegerField(default=0)
    fg2_attempted = models.IntegerField(default=0)
    fg3_made = models.IntegerField(default=0)
    fg3_attempted = models.IntegerField(default=0)
    ft_made = models.IntegerField(default=0)
    ft_attempted = models.IntegerField(default=0)

    # Rebounds credited to the offense (their own missed shots) and the defense
    # (the other team's missed shots), each on the side that actually grabbed it.
    offensive_rebounds = models.IntegerField(default=0)
    defensive_rebounds = models.IntegerField(default=0)

    assists = models.IntegerField(default=0)  # offense
    turnovers = models.IntegerField(default=0)  # offense
    offensive_fouls = models.IntegerField(default=0)  # offense
    steals = models.IntegerField(default=0)  # defense
    blocks = models.IntegerField(default=0)  # defense
    defensive_fouls = models.IntegerField(default=0)  # defense

    class Meta:
        indexes = [
            models.Index(fields=['game', 'period']),
        ]
