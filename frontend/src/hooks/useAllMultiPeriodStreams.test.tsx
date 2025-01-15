import { type ComponentChildren } from "preact";
import { afterEach, describe, expect, test, vi } from "vitest";
import { act, renderHook } from "@testing-library/preact";
import { mock } from "vitest-mock-extended";

import { ApiRequests, EndpointContext } from "../endpoints";
import { useAllMultiPeriodStreams, UseAllMultiPeriodStreamsHook } from "./useAllMultiPeriodStreams";
import { AllMultiPeriodStreamsJson } from "../types/AllMultiPeriodStreams";

import allMpsJson from "../test/fixtures/multi-period-streams/index.json";

describe("useAllMultiPeriodStreams hook", () => {
  const apiRequests = mock<ApiRequests>();

  const wrapper = ({ children }: { children: ComponentChildren }) => {
    return (
      <EndpointContext.Provider value={apiRequests}>
        {children}
      </EndpointContext.Provider>
    );
  };

  function happyPathSetup(): Promise<void> {
    return new Promise<void>((resolve) => {
      apiRequests.getAllMultiPeriodStreams.mockImplementation(async () => {
        resolve();
        return allMpsJson as AllMultiPeriodStreamsJson;
      });
    });
  }

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("fetches streams list from server", async () => {
    const getAllMultiPeriodStreamsPromise = happyPathSetup();
    const { result } = renderHook<UseAllMultiPeriodStreamsHook, void>(
      useAllMultiPeriodStreams,
      { wrapper }
    );
    await act(async () => {
      await getAllMultiPeriodStreamsPromise;
    });
    const { error, loaded, streams } = result.current;
    expect(loaded.value).toEqual(true);
    expect(error.value).toBeNull();
    expect(streams.value).toEqual(allMpsJson.streams);
  });

  test("can sort streams", async () => {
    const getAllMultiPeriodStreamsPromise = happyPathSetup();
    const { result } = renderHook<UseAllMultiPeriodStreamsHook, void>(
      () => useAllMultiPeriodStreams(),
      { wrapper }
    );
    await act(async () => {
      await getAllMultiPeriodStreamsPromise;
    });
    const { loaded, sort } = result.current;
    const streams = structuredClone(result.current.streams.value);
    expect(loaded.value).toEqual(true);
    expect(streams).toEqual(allMpsJson.streams);
    expect(result.current.sortField).toEqual("name");
    await act(async () => {
        sort('title', true);
    });
    expect(result.current.sortField).toEqual("title");
    expect(streams).toEqual(allMpsJson.streams);
    expect(result.current.streams.value).not.toEqual(streams);
    expect(result.current.streams.value).toEqual([
        streams[1],
        streams[0],
    ]);
    await act(async () => {
        sort('title', false);
    });
    expect(result.current.streams.value).toEqual(streams);
  });

  test("can sort streams with duplicate titles", async () => {
    const { csrfTokens, streams } = allMpsJson;
    const duplicatedTitle: AllMultiPeriodStreamsJson = {
        csrfTokens,
        streams: [
            streams[0],
            {
                ...streams[1],
                title: streams[0].title,
            }
        ]
    };
    const getAllMultiPeriodStreamsPromise = new Promise<void>((resolve) => {
        apiRequests.getAllMultiPeriodStreams.mockImplementation(async () => {
          resolve();
          return duplicatedTitle;
        });
      });

    const { result } = renderHook<UseAllMultiPeriodStreamsHook, void>(
      () => useAllMultiPeriodStreams(),
      { wrapper }
    );
    await act(async () => {
      await getAllMultiPeriodStreamsPromise;
    });
    const { loaded, sort } = result.current;
    const streamsValue = structuredClone(result.current.streams.value);
    expect(loaded.value).toEqual(true);
    expect(streamsValue).not.toEqual(allMpsJson.streams);
    expect(result.current.sortField).toEqual("name");
    await act(async () => {
        sort('title', true);
    });
    expect(result.current.streams.value).toEqual(duplicatedTitle.streams);
  });

  test("fails to fetch list from server", async () => {
    const getAllMultiPeriodStreamsPromise = new Promise<void>((resolve) => {
        apiRequests.getAllMultiPeriodStreams.mockImplementation(async () => {
          resolve();
          throw new Error('Connection failed');
        });
      });
      const { result } = renderHook<UseAllMultiPeriodStreamsHook, void>(
      () => useAllMultiPeriodStreams(),
      { wrapper }
    );
    await act(async () => {
      await getAllMultiPeriodStreamsPromise;
    });
    const { error, loaded, streams } = result.current;
    expect(loaded.value).toEqual(false);
    expect(error.value).toEqual(expect.stringContaining("Fetching multi-period streams list failed"));
    expect(streams.value).toEqual([]);
  });
});
