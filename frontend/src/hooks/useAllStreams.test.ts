import { describe, expect, test } from "vitest";

import { streams } from "../test/fixtures/streams.json";
import { decorateAllStreams } from "./useAllStreams";

describe("useAllStreams hook", () => {
  test("decorating streams", () => {
    const decorated = decorateAllStreams(streams);
    const justTracks = decorated.map(({ pk, directory, tracks }) => ({
      pk,
      tracks,
      directory,
    }));
    const expectedTracks = [
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
    expect(justTracks).toEqual(expectedTracks);
  });
});
