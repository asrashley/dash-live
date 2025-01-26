import { batch, useComputed, useSignal, type ReadonlySignal } from "@preact/signals";
import { useCallback } from "preact/hooks";

export interface UseSortAndFilterHook<T> {
    sortField: ReadonlySignal<keyof T>;
    sortedData: ReadonlySignal<T[]>;
    sortOrder: ReadonlySignal<boolean>;
    filters: ReadonlySignal<Record<keyof T, string>>;
    setSort: (field: keyof T, ascending: boolean) => void;
    setFilter: (field: keyof T, value: string) => void;
}

export function useSortAndFilter<T extends Record<string, string | number | boolean>>(
    data: ReadonlySignal<T[]>,
    initialSortField: keyof T
): UseSortAndFilterHook<T> {
    const sortField = useSignal<keyof T>(initialSortField);
    const filters = useSignal<Record<keyof T, string>>({} as Record<keyof T, string>);
    const sortOrder = useSignal<boolean>(true);
    const filteredData = useComputed<T[]>(() => {
        return data.value.filter((item) => {
            return Object.entries(filters.value).every(([key, value]) => {
                return value === "" || `${item[key]}`.toLowerCase().includes(value);
            });
        });
    });
    const sortedData = useComputed<T[]>(() => {
        const sorted = [...filteredData.value];
        sorted.sort((one: T, second: T) => {
            const a = one[sortField.value];
            const b = second[sortField.value];
            if (a === b) {
                return 0;
            }
            if (a < b) {
                return sortOrder.value ? -1 : 1;
            }
            return sortOrder.value ? 1 : -1;
        });
        return sorted;
    });
    const setSort = useCallback((field: keyof T, ascending: boolean) => {
        batch(() => {
            sortField.value = field;
            sortOrder.value = ascending;
        });
    }, [sortField, sortOrder]);
    const setFilter = useCallback((field: keyof T, value: string) => {
        filters.value = { ...filters.value, [field]: value.toLowerCase() };
    }, [filters]);

    return { sortField, sortOrder, sortedData, filters, setSort, setFilter };
}