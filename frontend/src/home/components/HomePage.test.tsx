import { beforeEach, describe, expect, test } from "vitest";

import { renderWithProviders } from "../../test/renderWithProviders";
import HomePage from './HomePage';
import { ApiRequests, EndpointContext } from "../../endpoints";
import { mock } from "vitest-mock-extended";
import { AllManifests } from "../../types/AllManifests";
import { AllStreamsJson } from "../../types/AllStreams";

describe("HomePage", () => {
  const apiRequests = mock<ApiRequests>();
  let getManifests: Promise<void>;
  let getStdStreams: Promise<void>;
  let getMpsStreams: Promise<void>;

  beforeEach(() => {
    getManifests = new Promise<void>((resolve) => {
      apiRequests.getAllManifests.mockImplementation(async () => {
        const manifests = await import("../../test/fixtures/manifests.json");
        resolve();
        return manifests.default as AllManifests;
      });
    });
    getStdStreams = new Promise<void>((resolve) => {
      apiRequests.getAllStreams.mockImplementation(async () => {
        const streams = await import("../../test/fixtures/streams.json");
        resolve();
        return streams.default as AllStreamsJson;
      });
    });
    getMpsStreams = new Promise<void>((resolve) => {
      apiRequests.getAllMultiPeriodStreams.mockImplementation(async () => {
        const streams = await import(
          "../../test/fixtures/multi-period-streams/index.json"
        );
        resolve();
        return streams.default;
      });
    });
  });

  test("matches snapshot", async () => {
    const { asFragment, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}><HomePage /></EndpointContext.Provider>
    );
    await Promise.all([getManifests, getStdStreams, getMpsStreams]);
    await findByText("Stream to play");
    await findByText("Video Player:");
    await findByText("Play Big Buck Bunny");
    await findByText("/dash/vod/bbb/hand_made.mpd", { exact: false });
    expect(asFragment()).toMatchSnapshot();
  });

  test("shows message if there are no streams", async () => {
    const csrf_tokens = {
      files: "qHAQOfmIb",
      kids: "dNFBz6LI",
      streams: "S_f42Pmob",
      upload: "geVWPK6i",
    };
    apiRequests.getAllStreams.mockImplementation(async () => {
      return {
        csrf_tokens,
        keys: [],
        streams: [],
      };
    });
    apiRequests.getAllMultiPeriodStreams.mockImplementation(async () => {
      return {
        csrfTokens: csrf_tokens,
        streams: [],
      };
    });
    const { findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}><HomePage /></EndpointContext.Provider>
    );
    await findByText("no streams in the database", { exact: false });
  });
});
