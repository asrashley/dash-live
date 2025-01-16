import { useCallback } from "preact/hooks";
import { type ReadonlySignal, useSignal } from "@preact/signals";

import { fieldGroups } from "@dashlive/options";

import { InputOptionName } from "../types/InputOptionName";

function createOptionNames(): InputOptionName[] {
    const names: InputOptionName[] = [];
    fieldGroups.forEach(grp => {
        grp.fields.forEach(({ name, fullName, shortName }) => {
            names.push({
                cgiName: name,
                fullName,
                shortName,
            });
        });
    });
    return names;
}

function sortList(options: InputOptionName[], field: string, ascending: boolean): InputOptionName[] {
    const newList = [...options];
    newList.sort((a, b) => {
        const left = a[field];
        const right = b[field];
        if (left === right) {
          return 0;
        }
        if (left < right) {
          return ascending ? -1 : 1;
        }
        return ascending ? 1 : -1;
    });
    return newList;
}

export interface UseOptionsDetailsHook {
    allOptions: ReadonlySignal<InputOptionName[]>;
    sortField: ReadonlySignal<string>;
    sortAscending: ReadonlySignal<boolean>;
    setSortField: (field: string, ascending: boolean) => void;
}
export function useOptionsDetails(): UseOptionsDetailsHook {
    const allOptions = useSignal<InputOptionName[]>(sortList(createOptionNames(), "fullName", true));
    const sortField = useSignal<string>("fullName");
    const sortAscending = useSignal<boolean>(true);
    const setSortField = useCallback((field: string, ascending: boolean) => {
        sortField.value = field;
        sortAscending.value = ascending;
        allOptions.value = sortList(allOptions.value, field, ascending);
    }, [allOptions, sortAscending, sortField]);
    return { allOptions, sortField, sortAscending, setSortField };
}