import { beforeEach, describe, expect, test, vi } from "vitest";
import { html } from "htm/preact";

import { renderWithProviders } from "../../../test/renderWithProviders.js";
import HomePage from "./HomePage.js";
import { EndpointContext } from "../../endpoints.js";

describe("HomePage", () => {
  const apiRequests = {
    getAllManifests: vi.fn(),
    getAllMultiPeriodStreams: vi.fn(),
    getAllStreams: vi.fn(),
  };
  let getManifests;
  let getStdStreams;
  let getMpsStreams;

  beforeEach(() => {
    getManifests = new Promise((resolve) => {
      apiRequests.getAllManifests.mockImplementation(async () => {
        const manifests = await import("../../../mocks/manifests.json");
        resolve();
        return manifests;
      });
    });
    getStdStreams = new Promise((resolve) => {
      apiRequests.getAllStreams.mockImplementation(async () => {
        const streams = await import("../../../mocks/streams.json");
        resolve();
        return streams;
      });
    });
    getMpsStreams = new Promise((resolve) => {
      apiRequests.getAllMultiPeriodStreams.mockImplementation(async () => {
        const streams = await import(
          "../../../mocks/multi-period-streams.json"
        );
        resolve();
        return streams;
      });
    });
  });

  test("matches snapshot", async () => {
    const { asFragment, findByText } = renderWithProviders(
      html`<${EndpointContext.Provider} value=${apiRequests}><${HomePage} /></${EndpointContext.Provider}>`
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
        csrf_tokens,
        streams: [],
      };
    });
    const { findByText } = renderWithProviders(
      html`<${EndpointContext.Provider} value=${apiRequests}><${HomePage} /></${EndpointContext.Provider}>`
    );
    await findByText("no streams in the database", { exact: false });
  });
});
