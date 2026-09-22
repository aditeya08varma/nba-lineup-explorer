from django.urls import path

from lineups import views

urlpatterns = [
    path('lineups', views.LineupSummary.as_view(), name='lineup_summary'),
    path('teams', views.TeamList.as_view(), name='team_list'),
]
