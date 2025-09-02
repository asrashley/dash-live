import { fireEvent } from "@testing-library/preact";
import { signal } from "@preact/signals";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TextTrackSelection } from "./TextTrackSelection";
import type { MediaTrack } from "../types/MediaTrack";
import { renderWithProviders } from "../../test/renderWithProviders";
import { MediaTrackType } from "../types/MediaTrackType";

describe("TextTrackSelection", () => {
  const tracks = signal<MediaTrack[]>([]);
  const setTrack = vi.fn();
  const videoTrack: MediaTrack = {
    id: "v1",
    trackType: MediaTrackType.VIDEO,
    active: true,
  };
  const audioTrack: MediaTrack = {
    id: "a1",
    language: "eng",
    trackType: MediaTrackType.AUDIO,
    active: true,
  };
  const textTrackOne: MediaTrack = {
    id: "t1",
    language: "eng",
    trackType: MediaTrackType.TEXT,
    active: false,
  };
  const textTrackTwo: MediaTrack = {
    id: "t2",
    language: "cym",
    trackType: MediaTrackType.TEXT,
    active: false,
  };

  beforeEach(() => {
    textTrackOne.active = false;
    textTrackOne.language = "eng";
    textTrackTwo.active = false;
    tracks.value = [videoTrack, audioTrack, textTrackOne, textTrackTwo];
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders with no tracks", () => {
    tracks.value = [];
    const { getByText } = renderWithProviders(
      <TextTrackSelection tracks={tracks} setTrack={setTrack} />
    );
    getByText("- off -");
  });

  it("renders with tracks with no language property", () => {
    textTrackOne.language = undefined;
    const { getByText } = renderWithProviders(
      <TextTrackSelection tracks={tracks} setTrack={setTrack} />
    );
    getByText("- off -");
    getByText("0: track t1");
  });

  it("renders all text tracks and highlights that none have been selected", () => {
    const { getByText, getByTestId } = renderWithProviders(<TextTrackSelection tracks={tracks} setTrack={setTrack} />);
    const offBtn = getByText("- off -") as HTMLButtonElement;
    expect(offBtn).toBeDefined();
    expect((getByText('0: "eng"') as HTMLElement).querySelector('.bool-yes')).toBeNull();
    expect((getByText('1: "cym"') as HTMLElement).querySelector('.bool-yes')).toBeNull();
    expect(offBtn.querySelector('.bool-yes')).not.toBeNull();
    const toggler = getByTestId("track-track-toggle") as HTMLButtonElement;
    expect(toggler.querySelector('.badge-cc')).toBeDefined();
    expect(toggler.querySelector('.badge-cc-fill')).toBeNull();
  });

  it("renders all text tracks and highlights the active one", () => {
    textTrackTwo.active = true;
    const { getByText, getByTestId } = renderWithProviders(<TextTrackSelection tracks={tracks} setTrack={setTrack} />);
    const offBtn = getByText("- off -") as HTMLButtonElement;
    expect(offBtn).toBeDefined();
    expect((getByText('0: "eng"') as HTMLElement).querySelector('.bool-yes')).toBeNull();
    const trackTwoBtn = getByText('1: "cym"') as HTMLButtonElement;
    expect(offBtn.querySelector('.bool-yes')).toBeNull();
    expect(trackTwoBtn.querySelector('.bool-yes')).not.toBeNull();
    const toggler = getByTestId("track-track-toggle") as HTMLButtonElement;
    expect(toggler.querySelector('.badge-cc')).toBeNull();
    expect(toggler.querySelector('.badge-cc-fill')).toBeDefined();
  });

  it("calls setTextTrack(null) when off is clicked", () => {
    const { getByText }  = renderWithProviders(<TextTrackSelection tracks={tracks} setTrack={setTrack} />);
    const offBtn = getByText("- off -") as HTMLButtonElement;
    expect(offBtn).toBeDefined();
    fireEvent.click(offBtn);
    expect(setTrack).toHaveBeenCalledTimes(1);
    expect(setTrack).toHaveBeenCalledWith(null);
  });

  it("calls setTrack with correct track when it is clicked", () => {
    const { getByText } = renderWithProviders(<TextTrackSelection tracks={tracks} setTrack={setTrack} />);
    const trkOne = getByText('0: "eng"') as HTMLButtonElement;
    expect(trkOne).toBeDefined();
    const trkTwo = getByText('1: "cym"') as HTMLButtonElement;
    expect(trkTwo).toBeDefined();
    fireEvent.click(trkOne);
    expect(setTrack).toHaveBeenCalledTimes(1);
    expect(setTrack).toHaveBeenLastCalledWith(textTrackOne);
    fireEvent.click(trkTwo);
    expect(setTrack).toHaveBeenCalledTimes(2);
    expect(setTrack).toHaveBeenLastCalledWith(textTrackTwo);
  });

  it("toggles dropdown on button click", () => {
    const { getByTestId } = renderWithProviders(
      <TextTrackSelection tracks={tracks} setTrack={setTrack} />
    );
    const toggler = getByTestId("track-track-toggle") as HTMLButtonElement;
    expect(toggler.classList.contains("show")).toEqual(false);
    expect(toggler.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(toggler);
    expect(toggler.classList.contains("show")).toEqual(true);
    expect(toggler.getAttribute("aria-expanded")).toBe("true");
  });
});
