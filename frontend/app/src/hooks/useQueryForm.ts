import { useEffect, useMemo, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import type { QueryCodec } from '../shared/queryState';

export function useQueryForm<T>(codec: QueryCodec<T>) {
  const [params, setParams] = useSearchParams();
  const { key: requestKey } = useLocation();
  const { value: applied, error } = useMemo(() => codec.read(params), [codec, params]);
  const [draft, setDraft] = useState(applied);
  useEffect(() => { setDraft(applied); }, [applied]);
  function apply(value: T) {
    const next = codec.write(value);
    setParams(next, { replace: next.toString() === params.toString() });
  }
  return { applied, draft, setDraft, apply, error, requestKey };
}
