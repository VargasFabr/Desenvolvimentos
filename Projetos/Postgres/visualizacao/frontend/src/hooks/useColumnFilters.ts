import { useEffect, useMemo, useState } from "react";
import { emptyFilters, paramsFromFilters } from "../utils/filters";

export function useColumnFilters(
  opcoes: Record<string, string[]> | undefined,
  initial: Record<string, string> = {},
  limit = 500
) {
  const keys = useMemo(() => Object.keys(opcoes ?? {}), [opcoes]);
  const [filters, setFilters] = useState<Record<string, string>>(initial);

  useEffect(() => {
    if (!keys.length) return;
    setFilters((prev) => {
      const next = emptyFilters(keys);
      for (const k of keys) {
        const v = prev[k] ?? initial[k];
        if (v) next[k] = v;
      }
      return next;
    });
    // só re-sincroniza quando as colunas de filtro mudam
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keys.join(",")]);

  const params = useMemo(() => paramsFromFilters(filters, limit), [filters, limit]);
  const clear = () => setFilters(emptyFilters(keys));

  return { filters, setFilters, params, clear };
}
