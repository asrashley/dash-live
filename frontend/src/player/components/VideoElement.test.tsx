import { afterEach, beforeEach, describe, expect, Mock, test, vi } from "vitest";
import { act } from "@testing-library/preact";
import { signal } from "@preact/signals";

import { renderWithProviders } from "../../test/renderWithProviders";
import { StatusEvent } from "../types/StatusEvent";
import { PlayerControls } from "../types/PlayerControls";
import { STATUS_EVENTS, VideoElement, VideoElementProps } from "./VideoElement";
import { DashParameters } from "../types/DashParameters";
import { KeyParameters } from "../types/KeyParameters";
import { playerFactory } from "../players/playerFactory";
import { DashPlayerTypes } from "../types/DashPlayerTypes";
import { DashPlayerProps } from "../players/AbstractDashPlayer";
import { FakePlayer } from "../players/__mocks__/FakePlayer";

vi.mock("../players/playerFactory", () => ({
  playerFactory: vi.fn(),
}));

function spyOnVideo(video: HTMLVideoElement) {
  let paused: boolean = true;

  Object.defineProperties(video, {
      play: {
        writable: true,
        value: vi.fn(() => {
          paused = false;
        }),
      },
      paused: {
        get: vi.fn(() => paused),
      },
      duration: {
        writable: true,
        value: 30,
      },
  });
}

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
  const textEnabled = signal<boolean>(true);
  const textLanguage = signal<string>("");
  const events = signal<StatusEvent[]>([]);
  const mockedPlayerFactory = vi.mocked(playerFactory);
  const tracksChanged = vi.fn();
  let setPlayer: Mock<VideoElementProps["setPlayer"]>;
  let player: FakePlayer | undefined;

  beforeEach(() => {
    setPlayer = vi.fn();
    dashParams.value = structuredClone(params);
    events.value = [];
    currentTime.value = 0;
    textEnabled.value = true;
    textLanguage.value = "eng";
    keys.value = new Map();
    mockedPlayerFactory.mockImplementation(
      (_playerType: DashPlayerTypes, props: DashPlayerProps) => {
        player = new FakePlayer(props);
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
    const { getBySelector, unmount } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        events={events}
        textEnabled={textEnabled}
        textLanguage={textLanguage}
        setPlayer={setPlayer}
        tracksChanged={tracksChanged}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    expect(videoElement.src).toEqual(params.url);
    expect(mockedPlayerFactory).toHaveBeenCalledTimes(1);
    expect(mockedPlayerFactory).toHaveBeenCalledWith("native", {
      videoElement,
      autoplay: true,
      version: undefined,
      textEnabled: textEnabled.value,
      textLanguage: textLanguage.value,
      logEvent: expect.any(Function),
      tracksChanged: expect.any(Function),
    });
    unmount();
    expect(setPlayer).toHaveBeenCalledTimes(2);
    expect(setPlayer).toHaveBeenLastCalledWith(null);
  });

  test("should destroy player on unmount", () => {
    expect(setPlayer).not.toHaveBeenCalled();
    const { unmount } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        events={events}
        textEnabled={textEnabled}
        textLanguage={textLanguage}
        setPlayer={setPlayer}
        tracksChanged={tracksChanged}
      />
    );
    expect(mockedPlayerFactory).toHaveBeenCalledTimes(1);
    const playerInstance = mockedPlayerFactory.mock.results[0].value;
    const destroySpy = vi.spyOn(playerInstance, "destroy");
    unmount();
    expect(destroySpy).toHaveBeenCalledTimes(1);
    expect(setPlayer).toHaveBeenCalledTimes(2);
    expect(setPlayer).toHaveBeenLastCalledWith(null);
  });

  test("does not re-render", () => {
    expect(setPlayer).not.toHaveBeenCalled();
    const { getBySelector, rerender, unmount } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        events={events}
        textEnabled={textEnabled}
        textLanguage={textLanguage}
        setPlayer={setPlayer}
        tracksChanged={tracksChanged}
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
        events={events}
        textEnabled={textEnabled}
        textLanguage={textLanguage}
        setPlayer={setPlayer}
        tracksChanged={tracksChanged}
      />
    );
    expect(mockedPlayerFactory).toHaveBeenCalledTimes(1);
    expect(vid).toStrictEqual(getBySelector("video"));
    unmount();
  });

  test("can play()", () => {
    const { getBySelector, unmount } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        events={events}
        textEnabled={textEnabled}
        textLanguage={textLanguage}
        setPlayer={setPlayer}
        tracksChanged={tracksChanged}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    spyOnVideo(videoElement);
    expect(setPlayer).toHaveBeenCalledTimes(1);
    const controls: PlayerControls | null = setPlayer.mock.calls[0][0];
    expect(controls).not.toBeNull();
    controls.play();
    expect(videoElement.play).toHaveBeenCalledTimes(1);
    unmount();
    expect(setPlayer).toHaveBeenCalledTimes(2);
    expect(setPlayer).toHaveBeenLastCalledWith(null);
  });

  test("can pause()", () => {
    const { getBySelector, unmount } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        events={events}
        textEnabled={textEnabled}
        textLanguage={textLanguage}
        setPlayer={setPlayer}
        tracksChanged={tracksChanged}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    spyOnVideo(videoElement);
    expect(videoElement.paused).toEqual(true);
    expect(setPlayer).toHaveBeenCalledTimes(1);
    const controls: PlayerControls | null = setPlayer.mock.calls[0][0];
    expect(controls).not.toBeNull();
    expect(controls.hasPlayer.value).toEqual(true);
    expect(controls.isPaused.value).toEqual(true);
    const playEv = new Event('play');
    act(() => {
      videoElement.dispatchEvent(playEv);
    });
    expect(controls.isPaused.value).toEqual(false);
    controls.pause();
    //expect(videoElement.pause).toHaveBeenCalledTimes(1);
    const pauseEv = new Event('pause');
    act(() => {
      videoElement.dispatchEvent(pauseEv);
    });
    expect(controls.isPaused.value).toEqual(true);
    unmount();
    expect(setPlayer).toHaveBeenCalledTimes(2);
    expect(setPlayer).toHaveBeenLastCalledWith(null);
  });

  test("can skip()", () => {
    const { getBySelector } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        events={events}
        textEnabled={textEnabled}
        textLanguage={textLanguage}
        setPlayer={setPlayer}
        tracksChanged={tracksChanged}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    spyOnVideo(videoElement);
    videoElement.currentTime = 0;
    expect(setPlayer).toHaveBeenCalledTimes(1);
    const controls: PlayerControls | null = setPlayer.mock.calls[0][0];
    expect(controls).not.toBeNull();
    controls.skip(12);
    expect(videoElement.currentTime).toEqual(12);
    controls.skip(10);
    expect(videoElement.currentTime).toEqual(22);
  });

  test("can stop()", () => {
    const { unmount } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        events={events}
        textEnabled={textEnabled}
        textLanguage={textLanguage}
        setPlayer={setPlayer}
        tracksChanged={tracksChanged}
      />
    );
    expect(setPlayer).toHaveBeenCalledTimes(1);
    const controls: PlayerControls | null = setPlayer.mock.calls[0][0];
    expect(controls).not.toBeNull();
    expect(player).toBeDefined();
    vi.spyOn(player, 'destroy');
    controls.stop();
    expect(player.destroy).toHaveBeenCalledTimes(1);
    unmount();
    expect(setPlayer).toHaveBeenCalledTimes(2);
    expect(setPlayer).toHaveBeenLastCalledWith(null);
  });

  test("can add items to event log", () => {
    renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        events={events}
        textEnabled={textEnabled}
        textLanguage={textLanguage}
        setPlayer={setPlayer}
        tracksChanged={tracksChanged}
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
        events={events}
        textEnabled={textEnabled}
        textLanguage={textLanguage}
        setPlayer={setPlayer}
        tracksChanged={tracksChanged}
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
    const { getBySelector, unmount } = renderWithProviders(
      <VideoElement
        mpd={params.url}
        playerName="native"
        dashParams={dashParams}
        keys={keys}
        currentTime={currentTime}
        events={events}
        textEnabled={textEnabled}
        textLanguage={textLanguage}
        setPlayer={setPlayer}
        tracksChanged={tracksChanged}
      />
    );
    const videoElement = getBySelector("video") as HTMLVideoElement;
    spyOnVideo(videoElement);
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
    unmount();
    expect(setPlayer).toHaveBeenCalledTimes(2);
    expect(setPlayer).toHaveBeenLastCalledWith(null);
  });

  test("set subtitle element after component has mounted", () => {
    const { getByTestId, unmount } = renderWithProviders(
      <div>
        <VideoElement
          mpd={params.url}
          playerName="native"
          dashParams={dashParams}
          keys={keys}
          currentTime={currentTime}
          events={events}
          textEnabled={textEnabled}
          textLanguage={textLanguage}
          setPlayer={setPlayer}
          tracksChanged={tracksChanged}
        />
        <div data-testid="subtitles" />
      </div>
    );
    const subsElt = getByTestId("subtitles") as HTMLDivElement;
    expect(setPlayer).toHaveBeenCalledTimes(1);
    const controls: PlayerControls | null = setPlayer.mock.calls[0][0];
    expect(controls).not.toBeNull();
    expect(player).toBeDefined();
    expect(player.setSubtitlesElement).not.toHaveBeenCalled();
    controls.setSubtitlesElement(subsElt);
    expect(player.setSubtitlesElement).toHaveBeenCalledTimes(1);
    expect(player.setSubtitlesElement).toHaveBeenCalledWith(subsElt);
    unmount();
    expect(setPlayer).toHaveBeenCalledTimes(2);
    expect(setPlayer).toHaveBeenLastCalledWith(null);
  });

  test("set subtitle element before component has mounted", () => {
    let videoRef: VideoElement | undefined;
    const setVideoRef = (elt: VideoElement) => {
      videoRef = elt;
    };
    dashParams.value = undefined;
    const { getByTestId, unmount } = renderWithProviders(
      <div>
        <VideoElement
          mpd={params.url}
          playerName="native"
          dashParams={dashParams}
          keys={keys}
          currentTime={currentTime}
          events={events}
          textEnabled={textEnabled}
          textLanguage={textLanguage}
          ref={setVideoRef}
          setPlayer={setPlayer}
          tracksChanged={tracksChanged}
        />
        <div data-testid="subtitles" />
      </div>
    );
    const subsElt = getByTestId("subtitles") as HTMLDivElement;
    expect(videoRef).toBeDefined();
    expect(setPlayer).not.toHaveBeenCalled();
    videoRef.setSubtitlesElement(subsElt);
    expect(setPlayer).not.toHaveBeenCalled();
    act(() => {
      dashParams.value = structuredClone(params);
    });
    expect(setPlayer).toHaveBeenCalledTimes(1);
    const controls: PlayerControls | null = setPlayer.mock.calls[0][0];
    expect(controls).not.toBeNull();
    expect(player).toBeDefined();
    expect(player.setSubtitlesElement).toHaveBeenCalledTimes(1);
    expect(player.setSubtitlesElement).toHaveBeenCalledWith(subsElt);
    unmount();
    expect(setPlayer).toHaveBeenCalledTimes(2);
    expect(setPlayer).toHaveBeenLastCalledWith(null);
  });
});
