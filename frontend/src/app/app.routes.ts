import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () =>
      import('./lineup-explorer/lineup-explorer.component').then((m) => m.LineupExplorerComponent),
  },
];
