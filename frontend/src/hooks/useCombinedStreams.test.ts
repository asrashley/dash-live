import { beforeEach, expect, describe, vi, afterEach, test } from "vitest";
import { renderHook } from "@testing-library/preact";
import { signal } from "@preact/signals";

import { useAllStreams, type UseAllStreamsHook } from "./useAllStreams";
import { useAllMultiPeriodStreams, type UseAllMultiPeriodStreamsHook } from "./useAllMultiPeriodStreams";
import { DecoratedStream } from "../types/DecoratedStream";
import { useCombinedStreams } from "./useCombinedStreams";

vi.mock("./useAllStreams");
vi.mock("./useAllMultiPeriodStreams");

describe("useCombinedStreams", () => {
    const mockUseAllStreams = vi.mocked(useAllStreams);
    const mockUseAllMultiPeriodStreams = vi.mocked(useAllMultiPeriodStreams);
    const allStreamsError = signal<string | null>(null);
    const allStreamsLoaded = signal<boolean>(false);
    const allStreams = signal([]);
    const streamsMap = signal<Map<string, DecoratedStream>>(new Map());
    const mpsError = signal<string | null>(null);
    const mpsLoaded = signal<boolean>(false);
    const mpsStreams = signal([]);
    const allStreamsHook: UseAllStreamsHook = {
        allStreams,
        streamsMap,
        loaded: allStreamsLoaded,
        error: allStreamsError
    };
    const mpsHook: UseAllMultiPeriodStreamsHook = {
        error: mpsError,
        streams: mpsStreams,
        loaded: mpsLoaded,
        sort: vi.fn(),
        sortField: "",
        sortAscending: true,
    };

    beforeEach(() => {
        mockUseAllStreams.mockReturnValue(allStreamsHook);
        mockUseAllMultiPeriodStreams.mockReturnValue(mpsHook);
        mpsError.value = null;
        allStreamsError.value = null;
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    test("sets error when streams error is set", () => {
        allStreamsError.value = "Streams error";
        const { result } = renderHook(() => useCombinedStreams());
        expect(mockUseAllStreams).toHaveBeenCalled();
        expect(mockUseAllMultiPeriodStreams).toHaveBeenCalled();
        expect(result.current.error.value).to.equal("Streams error");
    });

    test("sets error when MPS error is set", () => {
        mpsError.value = "MPS error";
        const { result } = renderHook(() => useCombinedStreams());
        expect(mockUseAllStreams).toHaveBeenCalled();
        expect(mockUseAllMultiPeriodStreams).toHaveBeenCalled();
        expect(result.current.error.value).to.equal("MPS error");
    });

    test("shows all errors", () => {
        allStreamsError.value = "Streams error";
        mpsError.value = "MPS error";
        const { result } = renderHook(() => useCombinedStreams());
        expect(mockUseAllStreams).toHaveBeenCalled();
        expect(mockUseAllMultiPeriodStreams).toHaveBeenCalled();
        expect(result.current.error.value).to.equal("Streams error, MPS error");
    });

    test("error is null when there are no errors", () => {
        const { result } = renderHook(() => useCombinedStreams());
        expect(mockUseAllStreams).toHaveBeenCalled();
        expect(mockUseAllMultiPeriodStreams).toHaveBeenCalled();
        expect(result.current.error.value).to.equal(null);
    });

    test("sorts stream names by title", () => {
        allStreams.value = [
            { directory: "dir1", title: "Bravo" },
            { directory: "dir2", title: "Alpha" },
        ];
        mpsStreams.value = [
            { name: "mps1", title: "Delta" },
            { name: "mps2", title: "Charlie" },
        ];
        const { result } = renderHook(() => useCombinedStreams());
        expect(mockUseAllStreams).toHaveBeenCalled();
        expect(mockUseAllMultiPeriodStreams).toHaveBeenCalled();
        expect(result.current.streamNames.value).toEqual([
            "std.dir2", // Alpha
            "std.dir1", // Bravo
            "mps.mps2", // Charlie
            "mps.mps1", // Delta
        ]);
    });
});