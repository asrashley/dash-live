import { describe, expect, test } from "vitest";
import { renderHook, act } from "@testing-library/preact";
import { signal } from "@preact/signals";
import { useSortAndFilter } from "./useSortAndFilter";

type TestItem = {
    id: number;
    name: string;
    age: number;
};

describe("useSortAndFilter hook", () => {
    const mockData = signal<TestItem[]>([
        { id: 3, name: "Charlie", age: 35 },
        { id: 1, name: "Alice", age: 30 },
        { id: 2, name: "Bob", age: 25 },
        { id: 4, name: "Eve", age: 25 },
    ]);

    test("sorts data by initial sort field in ascending order", () => {
        const { result } = renderHook(() => useSortAndFilter<TestItem>(mockData, "name"));

        expect(result.current.sortedData.value).toEqual([
            { id: 1, name: "Alice", age: 30 },
            { id: 2, name: "Bob", age: 25 },
            { id: 3, name: "Charlie", age: 35 },
            { id: 4, name: "Eve", age: 25 },
        ]);
        expect(result.current.sortField.value).toEqual("name");
        expect(result.current.sortOrder.value).toEqual(true);
    });

    test("sorts data by initial sort field in descending order", () => {
        const { result } = renderHook(() => useSortAndFilter<TestItem>(mockData, "name"));

        act(() => {
            result.current.setSort("name", false);
        });

        expect(result.current.sortedData.value).toEqual([
            { id: 4, name: "Eve", age: 25 },
            { id: 3, name: "Charlie", age: 35 },
            { id: 2, name: "Bob", age: 25 },
            { id: 1, name: "Alice", age: 30 },
        ]);
        expect(result.current.sortField.value).toEqual("name");
        expect(result.current.sortOrder.value).toEqual(false);
    });

    test("sorts data by age in ascending order", () => {
        const { result } = renderHook(() => useSortAndFilter<TestItem>(mockData, "name"));

        act(() => {
            result.current.setSort("age", true);
        });

        expect(result.current.sortedData.value).toEqual([
            { id: 2, name: "Bob", age: 25 },
            { id: 4, name: "Eve", age: 25 },
            { id: 1, name: "Alice", age: 30 },
            { id: 3, name: "Charlie", age: 35 },
        ]);
    });

    test("sorts data by age in descending order", () => {
        const { result } = renderHook(() => useSortAndFilter<TestItem>(mockData, "name"));

        act(() => {
            result.current.setSort("age", false);
        });

        expect(result.current.sortedData.value).toEqual([
            { id: 3, name: "Charlie", age: 35 },
            { id: 1, name: "Alice", age: 30 },
            { id: 2, name: "Bob", age: 25 },
            { id: 4, name: "Eve", age: 25 },
        ]);
    });

    test("filters data by name", () => {
        const { result } = renderHook(() => useSortAndFilter<TestItem>(mockData, "name"));

        act(() => {
            result.current.setFilter("name", "Bob");
        });

        expect(result.current.sortedData.value).toEqual([
            { id: 2, name: "Bob", age: 25 },
        ]);
    });

    test("filters data by substring", () => {
        const { result } = renderHook(() => useSortAndFilter<TestItem>(mockData, "name"));

        act(() => {
            result.current.setFilter("name", "HAR");
        });

        expect(result.current.sortedData.value).toEqual([
            { id: 3, name: "Charlie", age: 35 },
        ]);
    });

    test("filters data by age", () => {
        const { result } = renderHook(() => useSortAndFilter<TestItem>(mockData, "name"));

        act(() => {
            result.current.setFilter("age", "25");
        });

        expect(result.current.sortedData.value).toEqual([
            { id: 2, name: "Bob", age: 25 },
            { id: 4, name: "Eve", age: 25 },
        ]);
    });

    test("filters data by multiple fields", () => {
        const { result } = renderHook(() => useSortAndFilter<TestItem>(mockData, "name"));

        act(() => {
            result.current.setFilter("name", "e");
            result.current.setFilter("age", "25");
        });

        expect(result.current.sortedData.value).toEqual([
            { id: 4, name: "Eve", age: 25 },
        ]);
    });

    test("clears filter", () => {
        const { result } = renderHook(() => useSortAndFilter<TestItem>(mockData, "name"));

        act(() => {
            result.current.setFilter("name", "Bob");
        });

        expect(result.current.sortedData.value).toEqual([
            { id: 2, name: "Bob", age: 25 },
        ]);

        act(() => {
            result.current.setFilter("name", "");
        });

        expect(result.current.sortedData.value).toEqual([
            { id: 1, name: "Alice", age: 30 },
            { id: 2, name: "Bob", age: 25 },
            { id: 3, name: "Charlie", age: 35 },
            { id: 4, name: "Eve", age: 25 },
        ]);
    });
});
