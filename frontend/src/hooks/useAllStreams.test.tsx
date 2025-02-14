import { describe, expect, test } from "vitest";
import { mock } from "vitest-mock-extended";
import { act, renderHook } from "@testing-library/preact";
import { type ComponentChildren } from "preact";

import {
  decorateAllStreams,
  useAllStreams,
  UseAllStreamsHook,
} from "./useAllStreams";
import { ApiRequests, EndpointContext } from "../endpoints";
import streamsJson from "../test/fixtures/streams.json";
import { AllStreamsJson } from "../types/AllStreams";

const decoratedTracks = [
  {
    tracks: [
      {
        clearBitrates: 7,
        encryptedBitrates: 7,
        track_id: 1,
        content_type: "video",
        codec_fourcc: "avc3",
      },
      {
        clearBitrates: 1,
        encryptedBitrates: 1,
        track_id: 2,
        content_type: "audio",
        codec_fourcc: "mp4a",
      },
      {
        clearBitrates: 1,
        encryptedBitrates: 1,
        track_id: 3,
        content_type: "audio",
        codec_fourcc: "ec-3",
      },
    ],
    directory: "bbb",
    pk: 1,
  },
  {
    tracks: [
      {
        clearBitrates: 7,
        encryptedBitrates: 7,
        track_id: 1,
        content_type: "video",
        codec_fourcc: "avc1",
      },
      {
        clearBitrates: 1,
        encryptedBitrates: 1,
        track_id: 2,
        content_type: "audio",
        codec_fourcc: "mp4a",
      },
      {
        clearBitrates: 1,
        encryptedBitrates: 1,
        track_id: 3,
        content_type: "audio",
        codec_fourcc: "ec-3",
      },
    ],
    directory: "tears",
    pk: 2,
  },
];

describe("useAllStreams hook", () => {
  const apiRequests = mock<ApiRequests>();

  const wrapper = ({ children }: { children: ComponentChildren }) => {
    return (
      <EndpointContext.Provider value={apiRequests}>
        {children}
      </EndpointContext.Provider>
    );
  };

  test("decorating streams", () => {
    const decorated = decorateAllStreams(streamsJson.streams);
    const justTracks = decorated.map(({ pk, directory, tracks }) => ({
      pk,
      tracks,
      directory,
    }));
    expect(justTracks).toEqual(decoratedTracks);
  });

  test("fetches streams", async () => {
    const prom = new Promise<void>((resolve) => {
      apiRequests.getAllStreams.mockImplementation(async () => {
        resolve();
        return streamsJson as AllStreamsJson;
      });
    });
    const { result } = renderHook<UseAllStreamsHook, void>(useAllStreams, {
      wrapper,
    });
    await act(async () => {
      await prom;
    });
    const { error, allStreams, streamsMap } = result.current;
    expect(error.value).toBeNull();
    expect(allStreams.value).toEqual(
      decorateAllStreams(streamsJson.streams)
    );
    for (const stream of streamsJson.streams) {
      const val = streamsMap.value.get(`${stream.pk}`);
      expect(val).toBeDefined();
      expect(val).toEqual(decorateAllStreams([stream])[0]);
    }
  });

  test("fails to fetch streams list", async () => {
    const prom = new Promise<void>((resolve) => {
      apiRequests.getAllStreams.mockImplementation(async () => {
        resolve();
        throw new Error("connection failed");
      });
    });
    const { result } = renderHook<UseAllStreamsHook, void>(useAllStreams, {
      wrapper,
    });
    await act(async () => {
      await prom;
    });
    expect(result.current.error.value).toEqual(
      expect.stringContaining("Failed to fetch streams")
    );
    expect(result.current.allStreams.value).toEqual([]);
    expect(result.current.streamsMap.value.size).toEqual(0);
  });
});
