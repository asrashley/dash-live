import { fireEvent, act } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { signal } from "@preact/signals";
import { PlaybackControls } from "./PlaybackControls";
import type { PlayerControls } from "../types/PlayerControls";
import { renderWithProviders } from "../../test/renderWithProviders";

describe("PlaybackControls", () => {
  const hasPlayer = signal<boolean>(true);
  const isPaused = signal<boolean>(false);
  const currentTime = signal<number>(0);
  const play = vi.fn();
  const pause = vi.fn();
  const stop = vi.fn();
  const skip = vi.fn();
  const setSubtitlesElement = vi.fn();

  const controls = signal<PlayerControls>();

  beforeEach(() => {
    isPaused.value = true;
    currentTime.value = 0;
    hasPlayer.value = true;
    controls.value = {
      hasPlayer,
      isPaused,
      play,
      pause,
      stop,
      skip,
      setSubtitlesElement,
    };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders play and pause icons based on isPaused", async () => {
    isPaused.value = true;
    const { getByTestId } = renderWithProviders(
      <PlaybackControls currentTime={currentTime} controls={controls} />
    );
    const btn = getByTestId("play-pause-btn") as HTMLButtonElement;
    expect(btn.getAttribute("disabled")).toBeNull();
    expect(btn.querySelector(".pause-fill")).toBeNull();
    expect(btn.querySelector(".play-fill")).toBeDefined();
    await act(async () => {
      isPaused.value = false;
    });
    expect(btn.querySelector(".pause-fill")).toBeDefined();
    expect(btn.querySelector(".play-fill")).toBeNull();
  });

  it("calls play and pause on playPause button click", () => {
    const { getByTestId } = renderWithProviders(
      <PlaybackControls currentTime={currentTime} controls={controls} />
    );
    const playPauseBtn = getByTestId("play-pause-btn") as HTMLButtonElement;
    expect(playPauseBtn.getAttribute("disabled")).toBeNull();
    fireEvent.click(playPauseBtn);
    expect(play).toHaveBeenCalled();
    act(() => {
      isPaused.value = false;
    });
    fireEvent.click(playPauseBtn);
    expect(pause).toHaveBeenCalled();
    expect(skip).not.toHaveBeenCalled();
  });

  it("calls skip(-15) when skip backward is clicked", () => {
    const { getByTestId } = renderWithProviders(
      <PlaybackControls currentTime={currentTime} controls={controls} />
    );
    const skipBackBtn = getByTestId("skip-back-btn") as HTMLButtonElement;
    fireEvent.click(skipBackBtn);
    expect(skip).toHaveBeenCalledTimes(1);
    expect(skip).toHaveBeenCalledWith(-15);
  });

  it("calls skip(15) when skip forward is clicked", () => {
    const { getByTestId } = renderWithProviders(
      <PlaybackControls currentTime={currentTime} controls={controls} />
    );
    const skipFwdBtn = getByTestId("skip-fwd-btn") as HTMLButtonElement;
    fireEvent.click(skipFwdBtn);
    expect(skip).toHaveBeenCalledTimes(1);
    expect(skip).toHaveBeenCalledWith(15);
    expect(pause).not.toHaveBeenCalled();
  });

  it("calls stop on stop button", () => {
    const { getByTestId } = renderWithProviders(
      <PlaybackControls currentTime={currentTime} controls={controls} />
    );
    const stopBtn = getByTestId("stop-btn") as HTMLButtonElement;
    fireEvent.click(stopBtn);
    expect(pause).not.toHaveBeenCalled();
    expect(skip).not.toHaveBeenCalled();
    expect(stop).toHaveBeenCalled();
  });

  it("disables buttons if hasPlayer is false", async () => {
    hasPlayer.value = false;
    const { getAllByRole, findByText } =
      renderWithProviders(
        <PlaybackControls currentTime={currentTime} controls={controls} />
      );
    await findByText("--:--:--");
    let buttons: HTMLButtonElement[] = getAllByRole(
      "button"
    ) as HTMLButtonElement[];
    // playPause is always enabled, others are disabled
    expect(buttons[0].getAttribute("disabled")).toBeNull();
    expect(buttons[1].getAttribute("disabled")).not.toBeNull();
    expect(buttons[2].getAttribute("disabled")).not.toBeNull();
    expect(buttons[3].getAttribute("disabled")).not.toBeNull();
    await act(async () => {
      hasPlayer.value = true;
    });
    await findByText("00:00:00");
    buttons = getAllByRole("button") as HTMLButtonElement[];
    buttons.forEach((btn) => expect(btn.getAttribute("disabled")).toBeNull());
  });

  it("shows --:--:-- if no player", () => {
    hasPlayer.value = false;
    const { getByText } = renderWithProviders(
      <PlaybackControls currentTime={currentTime} controls={controls} />
    );
    expect(getByText("--:--:--")).toBeTruthy();
  });

  it("shows --:--:-- if no controls", () => {
    controls.value = null;
    const { getByText, getByTestId } = renderWithProviders(
      <PlaybackControls currentTime={currentTime} controls={controls} />
    );
    expect(getByText("--:--:--")).toBeTruthy();
    const playPauseBtn = getByTestId("play-pause-btn") as HTMLButtonElement;
    expect(playPauseBtn.getAttribute("disabled")).not.toBeNull();
  });
});
