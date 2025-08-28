import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { act } from "@testing-library/preact";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../test/renderWithProviders";
import { StatusEvent } from "../types/StatusEvent";
import { PlayerControls } from "../types/PlayerControls";
import { STATUS_EVENTS, VideoElement } from "./VideoElement";
import { DashParameters } from "../types/DashParameters";
import { KeyParameters } from "../types/KeyParameters";
import { playerFactory } from "../players/playerFactory";
import { PlaybackIconType } from "../types/PlaybackIconType";
import { DashPlayerTypes } from "../types/DashPlayerTypes";
import { DashPlayerProps } from "../types/AbstractDashPlayer";
import { FakePlayer } from "../players/__mocks__/FakePlayer";

vi.mock("../players/playerFactory", () => ({
  playerFactory: vi.fn(),
}));

describe("VideoElement component", () => {
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
  const dashParams = signal<DashParameters>(params);
  const keys = signal<Map<string, KeyParameters>>(new Map());
  const currentTime = signal<number>(0);
  const controls = signal<PlayerControls | undefined>();
  const activeIcon = signal<PlaybackIconType | null>(null);
  const events = signal<StatusEvent[]>([]);
  const mockedPlayerFactory = vi.mocked(playerFactory);
  const play = vi.fn();
  let player: FakePlayer | undefined;

  beforeEach(() => {
    dashParams.value = structuredClone(params);
    events.value = [];
    currentTime.value = 0;
    keys.value = new Map();
    mockedPlayerFactory.mockImplementation(
      (_playerType: DashPlayerTypes, props: DashPlayerProps) => {
        player = new FakePlayer(props);
        vi.spyOn(player, 'pause');
        vi.spyOn(player, 'setSubtitlesElement');
        return player;
      }
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
    player = undefined;
  });

  test("should initialize player on mount", () => {
    const { getBySelector } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        activeIcon={activeIcon}
        events={events}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    expect(videoElement.src).toEqual(params.url);
    expect(mockedPlayerFactory).toHaveBeenCalledTimes(1);
    expect(mockedPlayerFactory).toHaveBeenCalledWith("native", {
      videoElement,
      autoplay: true,
      version: undefined,
      logEvent: expect.any(Function),
    });
  });

  test("should destroy player on unmount", () => {
    const { unmount } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        activeIcon={activeIcon}
        events={events}
      />
    );
    expect(mockedPlayerFactory).toHaveBeenCalledTimes(1);
    const playerInstance = mockedPlayerFactory.mock.results[0].value;
    const destroySpy = vi.spyOn(playerInstance, "destroy");
    unmount();
    expect(destroySpy).toHaveBeenCalledTimes(1);
  });

  test("does not re-render", () => {
    const { getBySelector, rerender } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        activeIcon={activeIcon}
        events={events}
      />
    );
    expect(mockedPlayerFactory).toHaveBeenCalledTimes(1);
    const vid = getBySelector("video") as HTMLVideoElement;
    rerender(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        activeIcon={activeIcon}
        events={events}
      />
    );
    expect(mockedPlayerFactory).toHaveBeenCalledTimes(1);
    expect(vid).toStrictEqual(getBySelector("video"));
  });

  test("can play()", () => {
    const { getBySelector } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        activeIcon={activeIcon}
        events={events}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    const playSpy = vi.spyOn(videoElement, "play");
    playSpy.mockImplementation(play);
    expect(controls.value).toBeDefined();
    controls.value.play();
    expect(playSpy).toHaveBeenCalledTimes(1);
  });

  test("can pause()", () => {
    const { getBySelector } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        activeIcon={activeIcon}
        events={events}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    const pauseSpy = vi.spyOn(videoElement, "pause");
    const isPausedSpy = vi.spyOn(videoElement, "paused", "get");
    isPausedSpy.mockReturnValue(false);
    pauseSpy.mockImplementation(() => {});
    expect(controls.value).toBeDefined();
    expect(controls.value.isPaused()).toEqual(false);
    controls.value.pause();
    expect(pauseSpy).toHaveBeenCalledTimes(1);
    isPausedSpy.mockReturnValue(true);
    expect(controls.value.isPaused()).toEqual(true);
  });

  test("can skip()", () => {
    const { getBySelector } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        activeIcon={activeIcon}
        events={events}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    Object.defineProperty(videoElement, "duration", {
      writable: true,
      value: 30,
    });
    videoElement.currentTime = 0;
    expect(controls.value).toBeDefined();
    controls.value.skip(12);
    expect(videoElement.currentTime).toEqual(12);
    controls.value.skip(10);
    expect(videoElement.currentTime).toEqual(22);
  });

  test("can stop()", () => {
    const { getBySelector } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        activeIcon={activeIcon}
        events={events}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    const pauseSpy = vi.spyOn(videoElement, "pause");
    pauseSpy.mockImplementation(() => {});
    expect(controls.value).toBeDefined();
    controls.value.stop();
    expect(pauseSpy).toHaveBeenCalledTimes(1);
  });

  test("can add items to event log", () => {
    renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        activeIcon={activeIcon}
        events={events}
      />
    );
    expect(mockedPlayerFactory).toHaveBeenCalledTimes(1);
    mockedPlayerFactory.mock.calls[0][1].logEvent("test", "test event");
    expect(events.value.length).toEqual(1);
    expect(events.value[0].event).toEqual("test");
    for (let i = 0; i < 20; i++) {
      mockedPlayerFactory.mock.calls[0][1].logEvent("test", `test event ${i}`);
      expect(events.value.length).toBeLessThanOrEqual(
        VideoElement.DEFAULT_MAX_EVENTS
      );
    }
  });

  test("updates currentTime on timeupdate", () => {
    const { getBySelector } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        activeIcon={activeIcon}
        events={events}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    videoElement.currentTime = 10;
    const ev = new Event("timeupdate");
    Object.defineProperty(ev, "target", {
      writable: false,
      value: videoElement,
    });
    expect(currentTime.value).toEqual(0);
    videoElement.dispatchEvent(ev);
    expect(currentTime.value).toEqual(10);
  });

  test.each(STATUS_EVENTS)("should handle %s event", (eventName: string) => {
    const { getBySelector } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        controls={controls}
        activeIcon={activeIcon}
        events={events}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    Object.defineProperty(videoElement, "play", {
      writable: true,
      value: play,
    });
    if (eventName === "error") {
      Object.defineProperty(videoElement, "error", {
        writable: true,
        value: {
          code: 1,
          message: "Test error",
        },
      });
    }

    const ev = new Event(eventName);
    Object.defineProperty(ev, "target", {
      writable: false,
      value: videoElement,
    });
    videoElement.dispatchEvent(ev);
    expect(events.value.length).toEqual(1);
    expect(events.value[0].event).toEqual(eventName);
  });

  test("set subtitle element after component has mounted", () => {
    const { getByTestId } = renderWithProviders(
      <div>
        <VideoElement
          mpd={params.url}
          playerName="native"
          dashParams={dashParams}
          keys={keys}
          currentTime={currentTime}
          controls={controls}
          activeIcon={activeIcon}
          events={events}
        />
        <div data-testid="subtitles" />
      </div>
    );
    const playerControls = controls.value;
    const subsElt = getByTestId("subtitles") as HTMLDivElement;
    expect(playerControls).toBeDefined();
    expect(player).toBeDefined();
    expect(player.setSubtitlesElement).not.toHaveBeenCalled();
    playerControls.setSubtitlesElement(subsElt);
    expect(player.setSubtitlesElement).toHaveBeenCalledTimes(1);
    expect(player.setSubtitlesElement).toHaveBeenCalledWith(subsElt);
  });

  test("set subtitle element before component has mounted", () => {
    let videoRef: VideoElement | undefined;
    const setVideoRef = (elt: VideoElement) => {
      videoRef = elt;
    };
    dashParams.value = undefined;
    const { getByTestId } = renderWithProviders(
      <div>
        <VideoElement
          mpd={params.url}
          playerName="native"
          dashParams={dashParams}
          keys={keys}
          currentTime={currentTime}
          controls={controls}
          activeIcon={activeIcon}
          events={events}
          ref={setVideoRef}
        />
        <div data-testid="subtitles" />
      </div>
    );
    const subsElt = getByTestId("subtitles") as HTMLDivElement;
    expect(controls.value).not.toBeDefined();
    expect(videoRef).toBeDefined();
    videoRef.setSubtitlesElement(subsElt);
    act(() => {
      dashParams.value = structuredClone(params);
    });
    expect(controls.value).toBeDefined();
    expect(player).toBeDefined();
    expect(player.setSubtitlesElement).toHaveBeenCalledTimes(1);
    expect(player.setSubtitlesElement).toHaveBeenCalledWith(subsElt);
  });
});
