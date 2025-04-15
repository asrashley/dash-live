import {
  afterAll,
  afterEach,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from "vitest";
import { mock } from "vitest-mock-extended";
import fetchMock from "@fetch-mock/vitest";
import { useParams } from "wouter-preact";
import log from "loglevel";

import { useSearchParams } from "../../hooks/useSearchParams";
import { renderWithProviders } from "../../test/renderWithProviders";
import VideoPlayerPage, { manifestUrl } from "./VideoPlayerPage";
import { ApiRequests, EndpointContext } from "../../endpoints";
import dashParameters from "../../test/fixtures/play/vod/bbb/hand_made.json";
import { DashParameters } from "../types/DashParameters";

vi.mock("../../hooks/useSearchParams", () => ({
  useSearchParams: vi.fn(),
}));

vi.mock("wouter-preact", async (importOriginal) => {
  return {
    ...(await importOriginal()),
    useLocation: vi.fn(),
    useParams: vi.fn(),
  };
});

describe("VideoPlayerPage", () => {
  const apiRequests = mock<ApiRequests>();
  const mockUseSearchParams = vi.mocked(useSearchParams);
  const mockUseParams = vi.mocked(useParams);

  afterAll(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    log.setLevel("error");
    apiRequests.getDashParameters.mockImplementation(
      async () => dashParameters as unknown as DashParameters
    );
    mockUseParams.mockReturnValue({
      mode: "dash",
      stream: "bbb",
      manifest: "hand-made",
    });
  });

  afterEach(async () => {
    vi.clearAllMocks();
    fetchMock.mockReset();
  });

  test("matches snapshot", async () => {
    const searchParams = new URLSearchParams({ player: "native" });
    mockUseSearchParams.mockReturnValue({
      searchParams,
    });
    const { asFragment, findBySelector, getByTestId } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <VideoPlayerPage />
      </EndpointContext.Provider>
    );
    getByTestId("video-player-page");
    await findBySelector("#vid-window");
    expect(asFragment()).toMatchSnapshot();
  });

  test("defaults to native player", async () => {
    const searchParams = new URLSearchParams();
    mockUseSearchParams.mockReturnValue({
      searchParams,
    });
    const { findBySelector } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <VideoPlayerPage />
      </EndpointContext.Provider>
    );
    await findBySelector("#vid-window");
  });

  test("shows loading spinner when loading", async () => {
    const searchParams = new URLSearchParams({ player: "native" });
    mockUseSearchParams.mockReturnValue({
      searchParams,
    });
    apiRequests.getDashParameters.mockClear();
    const { promise, resolve } = Promise.withResolvers<void>();
    apiRequests.getDashParameters.mockImplementation(async () => {
      await promise;
      return dashParameters as unknown as DashParameters;
    });
    const { getBySelector, findBySelector } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <VideoPlayerPage />
      </EndpointContext.Provider>
    );
    getBySelector(".lds-ring");
    resolve();
    await findBySelector("#vid-window");
  });

  test.each([
    ["vod", { player: "native" }, "/dash/vod/bbb/hand-made.mpd?player=native"],
    ["vod", { }, "/dash/vod/bbb/hand-made.mpd"],
    ["live", { }, "/dash/live/bbb/hand-made.mpd"],
    ["mps-vod", { player: "native" }, "/mps/vod/bbb/hand-made.mpd?player=native"],
    ["mps-vod", { }, "/mps/vod/bbb/hand-made.mpd"],
    ["mps-live", { }, "/mps/live/bbb/hand-made.mpd"],
  ])(
    "mode %s params %j generates manifest URL %s",
    (mode: string, params: Record<string, string>, expectedUrl: string) => {
      const searchParams = new URLSearchParams(params);
      expect(manifestUrl(mode, "bbb", "hand-made", searchParams)).toEqual(
        expectedUrl
      );
    }
  );
});
