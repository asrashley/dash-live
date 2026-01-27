import { signal } from "@preact/signals";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { CombinedStream } from "../../hooks/useCombinedStreams";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import { JWToken } from "../../user/types/JWToken";
import { renderHook } from "@testing-library/preact";
import { useStreamOptions } from "./useStreamOptions";

vi.mock("../../hooks/useLocalStorage");

describe("useStreamOptions hook", () => {
    const streamNames = signal<string[]>([]);
    const streamsMap = signal<Map<string, CombinedStream>>(new Map());
    const useLocalStorageMock = vi.mocked(useLocalStorage);
    const dashOptions = signal<{ [key: string]: string | number | boolean }>({});
    const setDashOption = vi.fn();
    const resetDashOptions = vi.fn();
    const refreshToken = signal<JWToken | null>(null);
    const streams: CombinedStream[] = [
        { title: "DASH Stream 1", value: "stream1", mps: false },
        { title: "MPS Stream 2", value: "stream2", mps: true }
    ];


    beforeEach(() => {
        useLocalStorageMock.mockReturnValue({
            dashOptions,
            setDashOption,
            resetDashOptions,
            refreshToken,
            setRefreshToken: vi.fn(),
        });
        dashOptions.value = {
            mode: "vod",
            manifest: "hand_made.mpd",
            stream: undefined,
        };
        streamsMap.value = new Map<string, CombinedStream>(streams.map(s => [s.value, s]));
        streamNames.value = [...streamsMap.value.keys()];
        streamNames.value.sort();
    });

    afterEach(() => {
        vi.resetAllMocks();
    });

    test('current stream is empty when no stream selected and no streams available', () => {
        streamsMap.value = new Map();
        streamNames.value = [];
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        expect(result.current.stream.value).toEqual({
            title: "",
            value: "",
            mps: false
        });
    });

    test('uses first available stream when local storage is empty', () => {
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        expect(result.current.stream.value).toEqual(streams[0]);
    });

    test.each(["vod", "live"])('mode is set to "%s" from local storage', (mode) => {
        dashOptions.value.mode = mode;
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        expect(result.current.mode.value).toBe(mode);
    });
    test('manifest is set from local storage', () => {
        dashOptions.value.manifest = "custom_manifest.mpd";
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        expect(result.current.manifest.value).toBe("custom_manifest.mpd");
    });

    test('setting stream to MPS stream while in odvod mode switches mode to vod', () => {
        dashOptions.value.mode = "odvod";
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        result.current.setValue("stream", "stream2");
        expect(setDashOption).toHaveBeenCalledWith("stream", "stream2");
        expect(setDashOption).toHaveBeenCalledWith("mode", "vod");
    });

    test('setting stream to non-MPS stream while in odvod mode does not switch mode', () => {
        dashOptions.value.mode = "odvod";
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        result.current.setValue("stream", "stream1");
        expect(setDashOption).toHaveBeenCalledWith("stream", "stream1");
        expect(setDashOption).not.toHaveBeenCalledWith("mode", "vod");
    });

    test("drms reflects enabled DRM systems from local storage", () => {
        dashOptions.value = {
            ...dashOptions.value,
            clearkey: "1",
            playready: "0",
            marlin: "1",
        };
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        expect(result.current.drms.value).toEqual({
            clearkey: true,
            playready: false,
            marlin: true,
        });
    });

    test("nonDefaultOptions includes only non-default options", () => {
        dashOptions.value = {
            ...dashOptions.value,
            manifest: "custom.mpd",
            clearkey: "1",
            playready: "1",
            playready__drmloc: "moov",
            marlin__drmloc: "pssh",
            someOtherOption: "customValue",
        };
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        expect(result.current.nonDefaultOptions.value).toEqual({
            someOtherOption: "customValue",
            drm: "clearkey,playready-moov"
        });
    });

    test("manifestOptions excludes manifest-irrelevant options", () => {
        dashOptions.value = {
            ...dashOptions.value,
            manifest: "custom.mpd",
            clearkey: "1",
            playready: "1",
            playready__drmloc: "moov",
            marlin__drmloc: "pssh",
            someOtherOption: "customValue",
            mode: "live",
            player: "dashjs",
            dashjs: "4.7.4",
            shaka: "4.3.5",
        };
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        expect(result.current.manifestOptions.value).toEqual({
            someOtherOption: "customValue",
            drm: "clearkey,playready-moov"
        });
    });

    test("resetAllValues calls resetDashOptions from local storage", () => {
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        result.current.resetAllValues();
        expect(resetDashOptions).toHaveBeenCalled();
    });

    test("setValue calls setDashOption from local storage", () => {
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        result.current.setValue("someOption", "someValue");
        expect(setDashOption).toHaveBeenCalledWith("someOption", "someValue");
    });

    test.each([true, false])("disabledFields matches MPS stream value %s", (mps: boolean) => {
        dashOptions.value.stream = mps ? "stream2" : "stream1";
        const { result } = renderHook((() => useStreamOptions({ streamNames, streamsMap })));
        expect(result.current.disabledFields.value).toEqual({
            mode__odvod: mps,
        });
    });
});