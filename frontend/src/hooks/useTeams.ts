/**
 * `useTeams` — async-shaped hook for the teams list.
 *
 * Today: resolves to `mockTeams` after a short delay so the UI can show loading states.
 * Later: replace the effect body with `fetch('/api/teams')` (or React Query) and map JSON to `Team[]`.
 */
import { useEffect, useState } from 'react';
import { mockTeams } from '../data/mockTeams';
import type { Team } from '../types/team';

/** Artificial latency (ms) so spinners and skeletons can be tested against real network timing. */
const MOCK_DELAY_MS = 300;

export interface UseTeamsResult {
  /** Resolved team rows, or `null` until the first load completes */
  data: Team[] | null;
  /** True from mount until data is set (or permanently if you add error handling that never sets data) */
  loading: boolean;
  /** Reserved for real requests; mock path keeps this `null` on success */
  error: Error | null;
}

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
    // Abort if the component unmounts before the timeout fires (avoids setState on unmounted tree)
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, []);

  return { data, loading, error };
}
