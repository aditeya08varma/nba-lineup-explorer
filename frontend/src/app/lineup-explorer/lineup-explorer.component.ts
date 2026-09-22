import { DecimalPipe, PercentPipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSortModule, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';

import { Lineup, LineupsService, Team } from '../_services/lineups.service';

interface Tick {
  value: number;
  pos: number;
}

const PLOT = { left: 55, right: 620, top: 20, bottom: 320 };

function niceMax(value: number): number {
  return Math.max(50, Math.ceil(value / 50) * 50);
}

function formatNumber(value: number | null): string {
  return value === null ? '–' : value.toFixed(1);
}

function formatPercent(value: number | null): string {
  return value === null ? '–' : `${Math.round(value * 100)}%`;
}

interface ChartPoint {
  x: number;
  y: number;
  r: number;
  lineup: Lineup;
  label: string;
}

interface DetailRow {
  label: string;
  offense: string;
  defense: string;
}

@Component({
  selector: 'app-lineup-explorer',
  standalone: true,
  imports: [
    DecimalPipe,
    PercentPipe,
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressBarModule,
    MatSelectModule,
    MatSortModule,
    MatTableModule,
  ],
  templateUrl: './lineup-explorer.component.html',
  styleUrl: './lineup-explorer.component.scss',
})
export class LineupExplorerComponent implements OnInit {
  private readonly lineupsService = inject(LineupsService);

  readonly columns = [
    'team', 'players', 'poss', 'off_rating', 'def_rating', 'net_rating', 'point_diff', 'oreb_pct', 'dreb_pct',
  ];
  readonly lineupSizes = [5, 4, 3, 2, 1];
  readonly limits = [0, 25, 50, 100];

  season = '2024-25';
  lineupSize = 5;
  teamId: number | '' = '';
  minPossessions = 30;
  limit = 100;
  sortBy = 'net_rating';
  order: 'asc' | 'desc' = 'desc';

  // State that drives the template is in signals, since this project uses zoneless
  // change detection (no zone.js) — a plain property assigned inside an RxJS
  // subscribe callback would not trigger a re-render, but a signal update does.
  readonly lineups = signal<Lineup[]>([]);
  readonly teams = signal<Team[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly selected = signal<Lineup | undefined>(undefined);
  readonly detailRows = signal<DetailRow[]>([]);
  readonly points = signal<ChartPoint[]>([]);
  readonly xTicks = signal<Tick[]>([]);
  readonly yTicks = signal<Tick[]>([]);

  readonly plot = PLOT;

  ngOnInit(): void {
    this.lineupsService.getTeams().subscribe((teams) => this.teams.set(teams));
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.lineupsService
      .getLineups(this.lineupSize, {
        season: this.season,
        team_id: this.teamId,
        min_possessions: this.minPossessions || 0,
        sort_by: this.sortBy,
        order: this.order,
        limit: this.limit,
      })
      .subscribe({
        next: (rows) => {
          this.lineups.set(rows);
          this.buildChart(rows);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(err.message || 'Request failed');
          this.loading.set(false);
        },
      });
  }

  onSort(sort: Sort): void {
    this.sortBy = sort.active;
    this.order = sort.direction === 'asc' ? 'asc' : 'desc';
    this.load();
  }

  select(row: Lineup): void {
    const next = this.selected() === row ? undefined : row;
    this.selected.set(next);
    this.detailRows.set(next ? this.buildDetailRows(next) : []);
  }

  closeDetail(): void {
    this.selected.set(undefined);
    this.detailRows.set([]);
  }

  private buildDetailRows(row: Lineup): DetailRow[] {
    return [
      { label: 'Possessions', offense: `${row.offensive_possessions}`, defense: `${row.defensive_possessions}` },
      { label: 'Points', offense: `${row.offensive_points} scored`, defense: `${row.defensive_points} allowed` },
      { label: 'Rating per 100', offense: formatNumber(row.off_rating), defense: formatNumber(row.def_rating) },
      { label: 'Field goal %', offense: formatPercent(row.offensive_fg_pct), defense: `${formatPercent(row.defensive_fg_pct)} allowed` },
      { label: '3-point %', offense: formatPercent(row.offensive_fg3_pct), defense: `${formatPercent(row.defensive_fg3_pct)} allowed` },
      { label: 'Turnovers', offense: `${row.offensive_turnovers} lost`, defense: `${row.defensive_turnovers} forced` },
      { label: 'Steals and blocks', offense: `stolen ${row.offensive_steals}, blocked ${row.offensive_blocks}`, defense: `steals ${row.defensive_steals}, blocks ${row.defensive_blocks}` },
      { label: 'Rebounds', offense: `${formatPercent(row.oreb_pct)} of own misses`, defense: `${formatPercent(row.dreb_pct)} of opponent misses` },
    ];
  }

  private buildChart(rows: Lineup[]): void {
    const rated = rows.filter((r) => r.off_rating !== null && r.def_rating !== null);
    const xMax = niceMax(Math.max(0, ...rated.map((r) => r.off_rating as number)));
    const yMax = niceMax(Math.max(0, ...rated.map((r) => r.def_rating as number)));
    const xPos = (v: number) => PLOT.left + (v / xMax) * (PLOT.right - PLOT.left);
    const yPos = (v: number) => PLOT.top + (v / yMax) * (PLOT.bottom - PLOT.top);
    const ticks = (max: number) => Array.from({ length: max / 50 + 1 }, (_, i) => i * 50);

    this.points.set(
      rated.map((row) => ({
        x: xPos(row.off_rating as number),
        y: yPos(row.def_rating as number),
        r: 3 + Math.sqrt(row.total_possessions) * 0.25,
        lineup: row,
        label:
          `${row.team_abbreviation}: ${row.players.map((p) => p.name).join(', ')}\n` +
          `Off ${(row.off_rating as number).toFixed(1)}, Def ${(row.def_rating as number).toFixed(1)}, ${row.total_possessions} poss`,
      })),
    );
    this.xTicks.set(ticks(xMax).map((v) => ({ value: v, pos: xPos(v) })));
    this.yTicks.set(ticks(yMax).map((v) => ({ value: v, pos: yPos(v) })));
  }
}
