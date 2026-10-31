"use client";
import { useEffect, useState } from "react";

export function useResource<T>(
  load: () => Promise<T>,
  pollWhile?: (data: T) => boolean,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const result = await load();
        if (!active) return;
        setData(result);
        setError(null);
        if (pollWhile?.(result)) timer = setTimeout(refresh, 2000);
      } catch (e) {
        if (active)
          setError(
            e instanceof Error
              ? e
              : new Error("We couldn’t reach the service. Please try again."),
          );
      }
    }
    void refresh();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [load, pollWhile, attempt]);
  return { data, error, retry: () => setAttempt((n) => n + 1) };
}
