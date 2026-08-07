import { useEffect, useState } from "react";
import { getJson } from "../api/client";

interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/**
 * Fetches `path` (with optional query `params`) whenever the JSON-stringified
 * dependency key changes. Deliberately simple (no cache/retry library) --
 * the API surface here is small and every response is cheap to refetch.
 */
export function useFetch<T>(path: string | null, params?: Record<string, string | undefined>): FetchState<T> {
  const [state, setState] = useState<FetchState<T>>({ data: null, loading: true, error: null });
  const depKey = JSON.stringify({ path, params });

  useEffect(() => {
    if (!path) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    getJson<T>(path, params)
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (!cancelled) setState({ data: null, loading: false, error: err instanceof Error ? err.message : String(err) });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [depKey]);

  return state;
}
