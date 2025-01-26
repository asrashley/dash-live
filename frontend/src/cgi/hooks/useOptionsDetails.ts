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

export interface UseOptionsDetailsHook {
    allOptions: ReadonlySignal<InputOptionName[]>;
}

export function useOptionsDetails(): UseOptionsDetailsHook {
    const allOptions = useSignal<InputOptionName[]>(createOptionNames());
    return { allOptions };
}