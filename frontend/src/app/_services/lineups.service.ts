import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

export interface LineupPlayer {
  player_id: number;
  name: string;
}

export interface Lineup {
  team_id: number;
  team_name: string;
  team_abbreviation: string;
  player_ids: number[];
  players: LineupPlayer[];
  total_possessions: number;
  offensive_possessions: number;
  defensive_possessions: number;
  offensive_points: number;
  defensive_points: number;
  offensive_fg_pct: number;
  defensive_fg_pct: number;
  offensive_fg3_pct: number;
  defensive_fg3_pct: number;
  offensive_steals: number;
  defensive_steals: number;
  offensive_blocks: number;
  defensive_blocks: number;
  offensive_turnovers: number;
  defensive_turnovers: number;
  off_rating: number | null;
  def_rating: number | null;
  net_rating: number | null;
  point_diff: number;
  oreb_pct: number | null;
  dreb_pct: number | null;
}

export interface Team {
  id: number;
  abbreviation: string;
  name: string;
}

export interface LineupFilters {
  season?: string;
  team_id?: number;
  player_id?: number;
  min_possessions?: number;
  sort_by?: string;
  order?: string;
  limit?: number;
}

@Injectable({ providedIn: 'root' })
export class LineupsService {
  private readonly baseUrl = environment.API_BASE_URL;

  constructor(private http: HttpClient) {}

  getLineups(lineupSize: number, filters: LineupFilters = {}): Observable<Lineup[]> {
    let params = new HttpParams().set('lineup_size', lineupSize);
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== '') {
        params = params.set(key, value);
      }
    }
    return this.http.get<Lineup[]>(`${this.baseUrl}/lineups`, { params });
  }

  getTeams(): Observable<Team[]> {
    return this.http.get<Team[]>(`${this.baseUrl}/teams`);
  }
}
