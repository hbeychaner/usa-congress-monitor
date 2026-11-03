import { useEffect, useState } from 'react';

export function useRead<T>(request: (() => Promise<T>) | null) {
  const [result, setResult] = useState<{
    request: () => Promise<T>;
    data: T | null;
    error: Error | null;
  } | null>(null);

  useEffect(() => {
    if (!request) return;
    let active = true;
    request().then(
      (data) => { if (active) setResult({ request, data, error: null }); },
      (error: Error) => { if (active) setResult({ request, data: null, error }); },
    );
    return () => { active = false; };
  }, [request]);

  const current = result?.request === request ? result : null;
  return { data: current?.data ?? null, error: current?.error ?? null, loading: request !== null && !current };
}
