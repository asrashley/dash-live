import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import fetchMock from "@fetch-mock/vitest";

import { routeMap } from "@dashlive/routemap";

import { renderWithProviders } from "../../test/renderWithProviders";
import { ApiRequests, EndpointContext } from "../../endpoints";
import HomePage from "./HomePage";
import { FakeEndpoint, jsonResponse } from "../../test/FakeEndpoint";
import { mediaUser, MockDashServer } from "../../test/MockServer";
import { LocalStorageKeys } from "../../hooks/useLocalStorage";

describe("HomePage", () => {
  const navigate = vi.fn();
  let apiRequests: ApiRequests;
  let endpoint: FakeEndpoint;

  beforeEach(() => {
    endpoint = new FakeEndpoint(document.location.origin);
    const server = new MockDashServer({
      endpoint,
    });
    const user = server.login(mediaUser.username, mediaUser.password);
    apiRequests = new ApiRequests({
      csrfTokens: {},
      accessToken: user.accessToken,
      refreshToken: user.refreshToken,
      navigate,
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
    await findByText("Stream to play");
    await findByText("Hand-made manifest");
    await findByText("Video Player:");
    await findByText("Play Big Buck Bunny");
    await findByText("/dash/vod/bbb/hand_made.mpd", { exact: false });
    expect(asFragment()).toMatchSnapshot();
  });

  test("can select a multi-period stream", async () => {
    const user = userEvent.setup();
    const { findBySelector, findByText } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <HomePage />
      </EndpointContext.Provider>
    );
    const streamSelect = await findBySelector("#model-stream") as HTMLSelectElement;
    await user.selectOptions(streamSelect, ["first title"]);
    await findByText("Play first title");
    const playBtn = await findBySelector(".play-button > .btn") as HTMLAnchorElement;
    const playUrl = new URL(
      routeMap.videoMps.url({
        mode: "vod",
        mps_name: "demo",
        manifest: "hand_made",
      }),
      document.location.href
    );
    expect(playBtn.getAttribute("href")).toEqual(playUrl.href);
    const anchor = await findBySelector("#dashurl") as HTMLAnchorElement;
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
      LocalStorageKeys.DASH_OPTIONS,
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
    await findByText("Play first title");
    await user.click(getBySelector(".reset-all-button > .btn"));
    expect(localStorage.getItem(LocalStorageKeys.DASH_OPTIONS)).toBeNull();
    await findByText("Play Big Buck Bunny");
  });

  test("shows message if there are no streams", async () => {
    const csrf_tokens = {
      files: "qHAQOfmIb",
      kids: "dNFBz6LI",
      streams: "S_f42Pmob",
      upload: "geVWPK6i",
    };
    endpoint.setResponseModifier('get', routeMap.listStreams.url(), async () => {
      return jsonResponse({
        csrf_tokens,
        keys: [],
        streams: [],
      });
    });
    endpoint.setResponseModifier('get', routeMap.listMps.url(), async () => {
      return jsonResponse([]);
    });
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
    await findByText("Play Big Buck Bunny");
    const btn = (await findByText("View Manifest")) as HTMLButtonElement;
    await user.click(btn);
    await findByText("urn:mpeg:dash:profile:isoff-live:2011", { exact: false });
    expect(asFragment).toMatchSnapshot();
  });
});
