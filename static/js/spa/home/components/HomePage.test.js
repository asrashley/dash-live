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
  let requestsPromise;

  beforeEach(() => {
    const getManifests = new Promise((resolve) => {
      apiRequests.getAllManifests.mockImplementation(async () => {
        const manifests = await import("../../../mocks/manifests.json");
        resolve();
        return manifests;
      });
    });
    const getStdStreams = new Promise((resolve) => {
      apiRequests.getAllStreams.mockImplementation(async () => {
        const streams = await import("../../../mocks/streams.json");
        resolve();
        return streams;
      });
    });
    const getMpsStreams = new Promise((resolve) => {
      apiRequests.getAllMultiPeriodStreams.mockImplementation(async () => {
        const streams = await import(
          "../../../mocks/multi-period-streams.json"
        );
        resolve();
        return streams;
      });
    });
    requestsPromise = Promise.all([getManifests, getStdStreams, getMpsStreams]);
  });

  test("matches snapshot", async () => {
    const { asFragment, findByText } = renderWithProviders(
      html`<${EndpointContext.Provider} value=${apiRequests}><${HomePage} /></${EndpointContext.Provider}>`
    );
    await requestsPromise;
    await findByText("Stream to play");
    await findByText("Video Player:");
    await findByText("Play Big Buck Bunny");
    await findByText("/dash/vod/bbb/hand_made.mpd", { exact: false });
    expect(asFragment()).toMatchSnapshot();
  });
});
