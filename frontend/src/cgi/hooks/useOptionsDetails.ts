import { type ReadonlySignal, useSignal } from "@preact/signals";

import { fieldGroups } from "@dashlive/options";

import { InputOptionName } from "../types/InputOptionName";
import { useSortAndFilter } from "../../hooks/useSortAndFilter";

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

export interface UseOptionsDetailsHook {
    allOptions: ReadonlySignal<InputOptionName[]>;
    sortField: ReadonlySignal<string>;
    sortOrder: ReadonlySignal<boolean>;
    setSort: (field: keyof InputOptionName, ascending: boolean) => void;
    setFilter: (field: keyof InputOptionName, value: string) => void;
}

export function useOptionsDetails(): UseOptionsDetailsHook {
    const { sortedData: allOptions, ...props } = useSortAndFilter<InputOptionName>(useSignal(createOptionNames()), "fullName");
    return { allOptions, ...props };
}