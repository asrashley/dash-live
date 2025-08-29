import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../test/renderWithProviders";
import { VideoPlayer } from "./VideoPlayer";
import { DashParameters } from "../types/DashParameters";
import { KeyParameters } from "../types/KeyParameters";
import { PlayerControls } from "../types/PlayerControls";
import { StatusEvent } from "../types/StatusEvent";
import { playerFactory } from "../players/playerFactory";
import { DashPlayerTypes } from "../types/DashPlayerTypes";
import { DashPlayerProps } from "../types/AbstractDashPlayer";
import { FakePlayer } from "../players/__mocks__/FakePlayer";
import { act } from "@testing-library/preact";

vi.mock("../players/playerFactory", () => ({
  playerFactory: vi.fn(),
}));

type PlayerControlsCallCount = {
  caller: (controls: PlayerControls) => void;
  cmd: string;
  pause?: number;
  play?: number;
  skip?: number;
  stop?: number;
};

describe("VideoPlayer component", () => {
  const params: DashParameters = {
    dash: {
      locationURL: "https://unit.test.local/test.mpd",
      mediaDuration: "PT30S",
      minBufferTime: "PT4S",
      mpd_id: "mpd-id",
      now: "2025-04-05T01:02:03Z",
      periods: [],
      profiles: [],
      publishTime: "2025-01-01T00:00:00Z",
      startNumber: 1,
      suggestedPresentationDelay: 0,
      timeSource: null,
      title: "VideoElement test",
    },
    options: {},
    url: "https://unit.test.local/test.mpd",
  };
  const mockedPlayerFactory = vi.mocked(playerFactory);
  const dashParams = signal<DashParameters>(params);
  const keys = signal<Map<string, KeyParameters>>(new Map());
  const currentTime = signal<number>(0);
  const events = signal<StatusEvent[]>([]);
  let player: FakePlayer | undefined;

  beforeEach(() => {
    mockedPlayerFactory.mockImplementation(
      (_playerType: DashPlayerTypes, props: DashPlayerProps) => {
        player = new FakePlayer(props);
        return player;
      }
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
    player = undefined;
  });

  test("matches snapshot", () => {
    const setPlayer = vi.fn();
    const { asFragment, unmount } = renderWithProviders(
      <VideoPlayer
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        events={events}
        setPlayer={setPlayer}
      />
    );
    expect(setPlayer).toHaveBeenCalledTimes(1);
    expect(asFragment()).toMatchSnapshot();
    unmount();
    expect(setPlayer).toHaveBeenCalledTimes(2);
    expect(setPlayer).toHaveBeenLastCalledWith(null);
  });

  test.each<PlayerControlsCallCount>([
    { caller: (c) => c.stop(), stop: 1, cmd: "stop" },
    { caller: (c) => c.play(), play: 1, cmd: "play" },
    { caller: (c) => c.pause(), pause: 1, cmd: "pause" },
    { caller: (c) => c.skip(-5), skip: 1, cmd: "backward" },
    { caller: (c) => c.skip(5), skip: 1, cmd: "forward" },
  ])('wraps calls to $cmd', ({ caller, cmd, ...props }: PlayerControlsCallCount) => {
    const setPlayer = vi.fn();
    const { getBySelector, unmount } = renderWithProviders(
      <VideoPlayer
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        events={events}
        setPlayer={setPlayer}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    Object.defineProperties(videoElement, {
      duration: {
        writable: true,
        value: 30,
      },
      currentTime: {
        writable: true,
        value: 15,
      },
      play: {
        writable: true,
        value: vi.fn(),
      },
    });

    expect(setPlayer).toHaveBeenCalledTimes(1);
    const controls: PlayerControls | null = setPlayer.mock.calls[0][0];
    expect(controls).not.toBeNull();
    expect(player).toBeDefined();
    vi.spyOn(controls, "pause");
    vi.spyOn(controls, "play");
    vi.spyOn(controls, "skip");
    vi.spyOn(controls, "stop");
    vi.spyOn(player, "destroy");
    act(() => {
      caller(controls);
    });
    if (cmd === 'backward') {
      getBySelector('.bi-skip-backward-fill');
    }
    else if (cmd === 'forward') {
      getBySelector('.bi-skip-forward-fill');
    }else {
      getBySelector(`.bi-${cmd}-fill`);
    }
    const expected = {
      setLocation: 0,
      pause: 0,
      play: 0,
      skip: 0,
      stop: 0,
      caller,
      ...props,
    };
    expect(controls.pause).toHaveBeenCalledTimes(expected.pause);
    expect(controls.play).toHaveBeenCalledTimes(expected.play);
    expect(controls.skip).toHaveBeenCalledTimes(expected.skip);
    expect(controls.stop).toHaveBeenCalledTimes(expected.stop);
    expect(player.destroy).toHaveBeenCalledTimes(expected.stop);
    unmount();
    expect(setPlayer).toHaveBeenCalledTimes(2);
    expect(setPlayer).toHaveBeenLastCalledWith(null);
  });
});
