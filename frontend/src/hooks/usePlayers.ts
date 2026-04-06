import { useEffect, useState } from 'react';
import { mockPlayers } from '../data/mockPlayers';
import type { Player } from '../types/player';

const MOCK_DELAY_MS = 300;

export interface UsePlayersResult {
  data: Player[] | null;
  loading: boolean;
  error: Error | null;
}

/** Simulates `/players` fetch */
export function usePlayers(): UsePlayersResult {
  const [data, setData] = useState<Player[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const t = window.setTimeout(() => {
      if (!cancelled) {
        setData(mockPlayers);
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
