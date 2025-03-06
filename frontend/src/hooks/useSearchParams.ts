import { useMemo } from "preact/hooks";
import { useSearch } from "wouter-preact";

export interface UseSearchParamsHook {
    searchParams: Readonly<URLSearchParams>;
}

export function useSearchParams() : UseSearchParamsHook {
    const search = useSearch();
    const searchParams = useMemo(() => new URLSearchParams(search), [search]);
    return { searchParams };
}