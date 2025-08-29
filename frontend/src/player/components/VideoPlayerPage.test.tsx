import {
  afterAll,
  afterEach,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from "vitest";
import { act } from "@testing-library/preact";
import { signal } from "@preact/signals";
import { mock, mockReset } from "vitest-mock-extended";
import fetchMock from "@fetch-mock/vitest";
import { useLocation, useParams } from "wouter-preact";
import log from "loglevel";

import { useSearchParams } from "../../hooks/useSearchParams";
import { renderWithProviders } from "../../test/renderWithProviders";
import VideoPlayerPage, {
  keyHandler,
  KeyHandlerProps,
  manifestUrl,
} from "./VideoPlayerPage";
import { ApiRequests, EndpointContext } from "../../endpoints";
import dashParameters from "../../test/fixtures/play/vod/bbb/hand_made.json";
import { DashParameters } from "../types/DashParameters";
import { PlayerControls } from "../types/PlayerControls";
import { playerFactory } from "../players/playerFactory";
import {
  DashPlayerProps,
} from "../types/AbstractDashPlayer";
import { DashPlayerTypes } from "../types/DashPlayerTypes";
import { FakePlayer } from "../players/__mocks__/FakePlayer";

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

vi.mock("../players/playerFactory", () => ({
  playerFactory: vi.fn(),
}));

describe("VideoPlayerPage", () => {
  const apiRequests = mock<ApiRequests>();
  const mockedPlayerFactory = vi.mocked(playerFactory);
  const mockUseSearchParams = vi.mocked(useSearchParams);
  const mockUseLocation = vi.mocked(useLocation);
  const mockUseParams = vi.mocked(useParams);
  const setLocation = vi.fn();
  let player: FakePlayer | undefined;

  afterAll(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    player = undefined;
    vi.useFakeTimers();
    log.setLevel("error");
    mockUseLocation.mockReturnValue(["/play", setLocation]);
    apiRequests.getDashParameters.mockImplementation(
      async () => dashParameters as unknown as DashParameters
    );
    mockUseParams.mockReturnValue({
      mode: "dash",
      stream: "bbb",
      manifest: "hand-made",
    });
    mockedPlayerFactory.mockImplementation(
      (_playerType: DashPlayerTypes, props: DashPlayerProps) => {
        player = new FakePlayer(props);
        vi.spyOn(player, 'pause');
        return player;
      }
    );
  });

  afterEach(async () => {
    player = undefined;
    vi.clearAllMocks();
    fetchMock.mockReset();
    vi.useRealTimers();
  });

  test("matches snapshot", async () => {
    const searchParams = new URLSearchParams({ player: "native" });
    mockUseSearchParams.mockReturnValue({
      searchParams,
    });
    const { asFragment, findBySelector, findByText, getByTestId } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <VideoPlayerPage />
      </EndpointContext.Provider>
    );
    getByTestId("video-player-page");
    await findBySelector("#vid-window");
    await findByText("00:00:00");
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
    ["vod", {}, "/dash/vod/bbb/hand-made.mpd"],
    ["live", {}, "/dash/live/bbb/hand-made.mpd"],
    [
      "mps-vod",
      { player: "native" },
      "/mps/vod/bbb/hand-made.mpd?player=native",
    ],
    ["mps-vod", {}, "/mps/vod/bbb/hand-made.mpd"],
    ["mps-live", {}, "/mps/live/bbb/hand-made.mpd"],
  ])(
    "mode %s params %j generates manifest URL %s",
    (mode: string, params: Record<string, string>, expectedUrl: string) => {
      const searchParams = new URLSearchParams(params);
      expect(manifestUrl(mode, "bbb", "hand-made", searchParams)).toEqual(
        expectedUrl
      );
    }
  );

  test("listens to key down events", async () => {
    const searchParams = new URLSearchParams();
    mockUseSearchParams.mockReturnValue({
      searchParams,
    });
    const { findBySelector, queryBySelector } = renderWithProviders(
      <EndpointContext.Provider value={apiRequests}>
        <VideoPlayerPage />
      </EndpointContext.Provider>
    );
    await findBySelector("#vid-window");
    expect(player).toBeDefined();
    const ev: KeyboardEvent = new KeyboardEvent("keydown", {
      key: "MediaPause",
    });
    act(() => {
      document.body.dispatchEvent(ev);
    });
    await findBySelector("#vid-window .bi-pause-fill");
    expect(player.pause).toHaveBeenCalledTimes(1);
    // check that icon is cleared after 2 seconds
    act(() => {
      vi.advanceTimersByTime(2001);
    });
    expect(queryBySelector(".bi-pause-fill")).toBeNull();
  });
});

type PlayerControlsCallCount = {
  setLocation: number;
  pause: number;
  play: number;
  skip: number;
  stop: number;
};

describe("Key handling", () => {
  const notCalled: PlayerControlsCallCount = {
    setLocation: 0,
    pause: 0,
    play: 0,
    skip: 0,
    stop: 0,
  };
  const isPaused = signal<boolean>(false);
  const mockControls = mock<PlayerControls>({ isPaused });
  const setLocation = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
    mockReset(mockControls);
  });

  test("ignores key not used by player", () => {
    const props: KeyHandlerProps = {
      controls: mockControls,
      setLocation,
    };
    const ev: KeyboardEvent = new KeyboardEvent("keydown", {
      key: "q",
    });
    keyHandler(props, ev);
    expect(setLocation).not.toHaveBeenCalled();
    expect(mockControls.pause).not.toHaveBeenCalled();
    expect(mockControls.play).not.toHaveBeenCalled();
    expect(mockControls.skip).not.toHaveBeenCalled();
    expect(mockControls.stop).not.toHaveBeenCalled();
  });

  test.each([" ", "MediaPlayPause"])(
    'toggles play pause when "%s" pressed',
    (key: string) => {
      isPaused.value = false;
      const props: KeyHandlerProps = {
        controls: mockControls,
        setLocation,
      };
      const ev: KeyboardEvent = new KeyboardEvent("keydown", {
        key,
      });
      keyHandler(props, ev);
      expect(setLocation).not.toHaveBeenCalled();
      expect(mockControls.pause).toHaveBeenCalledTimes(1);
      expect(mockControls.play).not.toHaveBeenCalled();
      expect(mockControls.skip).not.toHaveBeenCalled();
      expect(mockControls.stop).not.toHaveBeenCalled();

      isPaused.value = true;
      keyHandler(props, ev);
      expect(mockControls.pause).toHaveBeenCalledTimes(1);
      expect(mockControls.play).toHaveBeenCalledTimes(1);
    }
  );

  test.each<[string, Partial<PlayerControlsCallCount>]>([
    ["Escape", { stop: 1 }],
    ["MediaStop", { stop: 1 }],
    ["MediaPlay", { play: 1 }],
    ["MediaPause", { pause: 1 }],
    ["ArrowLeft", { skip: 1 }],
    ["MediaTrackPrevious", { skip: 1 }],
    ["ArrowRight", { skip: 1 }],
    ["MediaTrackNext", { skip: 1 }],
    ["Home", { setLocation: 1 }],
    ["Finish", { setLocation: 1 }],
  ])(
    '"%s" pressed',
    (key: string, counts: Partial<PlayerControlsCallCount>) => {
      isPaused.value = false;
      const props: KeyHandlerProps = {
        controls: mockControls,
        setLocation,
      };
      const ev: KeyboardEvent = new KeyboardEvent("keydown", {
        key,
      });
      keyHandler(props, ev);
      const expected: PlayerControlsCallCount = {
        ...notCalled,
        ...counts,
      };
      expect(setLocation).toHaveBeenCalledTimes(expected.setLocation);
      expect(mockControls.pause).toHaveBeenCalledTimes(expected.pause);
      expect(mockControls.play).toHaveBeenCalledTimes(expected.play);
      expect(mockControls.skip).toHaveBeenCalledTimes(expected.skip);
      expect(mockControls.stop).toHaveBeenCalledTimes(expected.stop);
    }
  );
});
