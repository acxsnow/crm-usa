import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

export function useTableFilters() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(() => {
    const result: Record<string, string> = {};
    for (const [key, value] of searchParams.entries()) {
      if (key !== "page") result[key] = value;
    }
    return result;
  }, [searchParams]);

  const page = Number(searchParams.get("page") ?? "1") || 1;

  const setFilters = useCallback(
    (next: Record<string, string>) => {
      const params: Record<string, string> = {};
      for (const [key, value] of Object.entries(next)) {
        if (value) params[key] = value;
      }
      setSearchParams(params);
    },
    [setSearchParams]
  );

  const clearFilters = useCallback(() => setSearchParams({}), [setSearchParams]);

  const setPage = useCallback(
    (nextPage: number) => {
      const params: Record<string, string> = {};
      for (const [key, value] of Object.entries(filters)) params[key] = value;
      params.page = String(nextPage);
      setSearchParams(params);
    },
    [filters, setSearchParams]
  );

  return { filters, page, setFilters, clearFilters, setPage, extraParams: filters };
}
