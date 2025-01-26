import { renderHook } from "@testing-library/preact";
import { describe, expect, test } from "vitest";
import { useOptionsDetails } from "./useOptionsDetails";
import { InputOptionName } from "../types/InputOptionName";

describe('useOptionsDetails hook', () => {
    test('get all options', () => {
        const { result } = renderHook(() => useOptionsDetails());
        expect(result.current.sortField.value).toEqual("fullName");
        expect(result.current.sortOrder.value).toEqual(true);
        expect(result.current.allOptions.value).toMatchSnapshot();
    });

    test('can sort options', () => {
        const { result } = renderHook(() => useOptionsDetails());
        const { setSort } = result.current;
        const origOptions = [...result.current.allOptions.value];
        setSort("fullName", false);
        expect(result.current.allOptions.value).not.toEqual(origOptions);
        setSort("fullName", true);
        expect(result.current.allOptions.value).toEqual(origOptions);
        origOptions.sort((a: InputOptionName, b: InputOptionName) => {
            const left = a.shortName;
            const right = b.shortName;
            if (left === right) {
              return 0;
            }
            if (left < right) {
              return -1;
            }
            return 1;
        });
        expect(result.current.allOptions.value).not.toEqual(origOptions);
        setSort("shortName", true);
        expect(result.current.allOptions.value).toEqual(origOptions);
    });
});