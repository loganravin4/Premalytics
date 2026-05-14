/**
 * `useMatches` — fixtures for dashboards, recent results, and date-sorted views.
 */
import { useEffect, useState } from 'react';
import { mockMatches } from '../data/mockMatches';
import type { Match } from '../types/match';

const MOCK_DELAY_MS = 300;

export interface UseMatchesResult {
  data: Match[] | null;
  loading: boolean;
  error: Error | null;
}

export function useMatches(): UseMatchesResult {
  const [data, setData] = useState<Match[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const t = window.setTimeout(() => {
      if (!cancelled) {
        setData(mockMatches);
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
