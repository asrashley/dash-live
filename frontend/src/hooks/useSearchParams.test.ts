import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "@testing-library/preact";
import { useSearch } from "wouter-preact";

import { useSearchParams } from "./useSearchParams";

vi.mock("wouter-preact", async (importOriginal) => {
    return {
        ...(await importOriginal()),
        useSearch: vi.fn(),
    };
});

describe('useSearchParams hook', () => {
    const mockUseSearch = vi.mocked(useSearch);

    afterEach(() => {
        vi.clearAllMocks();
    });

    test('empty search string', () => {
        mockUseSearch.mockReturnValue('');
        const { result } = renderHook(() => useSearchParams());
        expect(result.current.searchParams.toString()).toEqual('');
        expect(result.current.searchParams.size).toEqual(0);
    });

    test('parses search string', () => {
        mockUseSearch.mockReturnValue('player=dashjs&timeline=1&drm=clearkey');
        const { result } = renderHook(() => useSearchParams())
        expect(result.current.searchParams.size).toEqual(3);
        expect(result.current.searchParams.get('player')).toEqual('dashjs');
        expect(result.current.searchParams.get('timeline')).toEqual('1');
        expect(result.current.searchParams.get('drm')).toEqual('clearkey');
    });
});