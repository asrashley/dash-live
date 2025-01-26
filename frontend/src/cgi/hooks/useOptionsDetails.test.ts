import { renderHook } from "@testing-library/preact";
import { describe, expect, test } from "vitest";
import { useOptionsDetails } from "./useOptionsDetails";

describe('useOptionsDetails hook', () => {
    test('get all options', () => {
        const { result } = renderHook(() => useOptionsDetails());
        expect(result.current.allOptions.value).toMatchSnapshot();
    });
});