import type { Standing } from '../types/standing';
import { mockTeams } from './mockTeams';

/** Table rows sorted like the real league (points, then goal difference) */
function buildStandings(): Standing[] {
  const sorted = [...mockTeams].sort((a, b) => {
    const pts = b.stats.points - a.stats.points;
    if (pts !== 0) return pts;
    const gdA = a.stats.goalsFor - a.stats.goalsAgainst;
    const gdB = b.stats.goalsFor - b.stats.goalsAgainst;
    return gdB - gdA;
  });
  return sorted.map((t, i) => ({
    position: i + 1,
    teamId: t.id,
    played: t.stats.played,
    wins: t.stats.wins,
    draws: t.stats.draws,
    losses: t.stats.losses,
    goalsFor: t.stats.goalsFor,
    goalsAgainst: t.stats.goalsAgainst,
    goalDifference: t.stats.goalsFor - t.stats.goalsAgainst,
    points: t.stats.points,
    form: t.form.slice(-5),
  }));
}

export const mockStandings: Standing[] = buildStandings();
