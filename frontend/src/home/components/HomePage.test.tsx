import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { mock } from "vitest-mock-extended";
import userEvent from "@testing-library/user-event";
import fetchMock from "@fetch-mock/vitest";

import { renderWithProviders } from "../../test/renderWithProviders";
import { ApiRequests, EndpointContext } from "../../endpoints";
import { AllManifests } from "../../types/AllManifests";
import { AllStreamsJson } from "../../types/AllStreams";
import HomePage from "./HomePage";
import { FakeEndpoint } from "../../test/FakeEndpoint";
import { MockDashServer } from "../../test/MockServer";
import { routeMap } from "@dashlive/routemap";
import { previousOptionsKeyName } from "../hooks/useStreamOptions";

describe("HomePage", () => {
  const apiRequests = mock<ApiRequests>();
  let getManifests: Promise<void>;
  let getStdStreams: Promise<void>;
  let getMpsStreams: Promise<void>;
  let endpoint: FakeEndpoint;

  beforeEach(() => {
    endpoint = new FakeEndpoint(document.location.origin);
    new MockDashServer({
      endpoint,
    });
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
        const { streams } = await import(
          "../../test/fixtures/multi-period-streams/index.json"
        );
        resolve();
        return streams;
      });
    });
  });

  afterEach(() => {
    endpoint.shutdown();
    fetchMock.mockReset();
    vi.clearAllMocks();
    localStorage.clear();
  });

  test("matches snapshot", async () => {
    const { asFragment, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <HomePage />
      </EndpointContext.Provider>
    );
    await Promise.all([getManifests, getStdStreams, getMpsStreams]);
    await findByText("Stream to play");
    await findByText("Video Player:");
    await findByText("Play Big Buck Bunny");
    await findByText("/dash/vod/bbb/hand_made.mpd", { exact: false });
    expect(asFragment()).toMatchSnapshot();
  });

  test("can select a multi-period stream", async () => {
    const user = userEvent.setup();
    const { getBySelector, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <HomePage />
      </EndpointContext.Provider>
    );
    await Promise.all([getManifests, getStdStreams, getMpsStreams]);
    const streamSelect = getBySelector("#model-stream") as HTMLSelectElement;
    await user.selectOptions(streamSelect, ["first title"]);
    await findByText("Play first title");
    const playBtn = getBySelector(".play-button > .btn") as HTMLAnchorElement;
    const playUrl = new URL(
      routeMap.videoMps.url({
        mode: "vod",
        mps_name: "demo",
        manifest: "hand_made",
      }),
      document.location.href
    );
    expect(playBtn.getAttribute("href")).toEqual(playUrl.href);
    const anchor = getBySelector("#dashurl") as HTMLAnchorElement;
    const mpdUrl = new URL(
      routeMap.mpsManifest.url({
        mode: "vod",
        mps_name: "demo",
        manifest: "hand_made.mpd",
      }),
      document.location.href
    );
    expect(anchor.getAttribute("href")).toEqual(mpdUrl.href);
  });

  test("can reset previous options", async () => {
    const user = userEvent.setup();
    localStorage.setItem(
      previousOptionsKeyName,
      JSON.stringify({
        manifest: "hand_made.mpd",
        mode: "vod",
        stream: "mps.demo",
      })
    );
    const { getBySelector, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <HomePage />
      </EndpointContext.Provider>
    );
    await Promise.all([getManifests, getStdStreams, getMpsStreams]);
    await findByText("Play first title");
    await user.click(getBySelector(".reset-all-button > .btn"));
    expect(localStorage.getItem(previousOptionsKeyName)).toBeNull();
    await findByText("Play Big Buck Bunny");
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
    apiRequests.getAllMultiPeriodStreams.mockResolvedValue([]);
    const { findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <HomePage />
      </EndpointContext.Provider>
    );
    await findByText("no streams in the database", { exact: false });
  });

  test("shows manifest contents", async () => {
    const user = userEvent.setup();

    const { asFragment, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <HomePage />
      </EndpointContext.Provider>
    );
    await Promise.all([getManifests, getStdStreams, getMpsStreams]);
    await findByText("Play Big Buck Bunny");
    const btn = (await findByText("View Manifest")) as HTMLButtonElement;
    await user.click(btn);
    await findByText("urn:mpeg:dash:profile:isoff-live:2011", { exact: false });
    expect(asFragment).toMatchSnapshot();
  });
});
