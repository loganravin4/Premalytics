import { useEffect, useState } from 'react';
import { mockTeams } from '../data/mockTeams';
import type { Team } from '../types/team';

const MOCK_DELAY_MS = 300;

export interface UseTeamsResult {
  data: Team[] | null;
  loading: boolean;
  error: Error | null;
}

/** Simulates `/teams` fetch; swap `mockTeams` for `fetch` later */
export function useTeams(): UseTeamsResult {
  const [data, setData] = useState<Team[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const t = window.setTimeout(() => {
      if (!cancelled) {
        setData(mockTeams);
        setError(null);
        setLoading(false);
      }
    }, MOCK_DELAY_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, []);

  return { data, loading, error };
}
