import { signal, type Signal } from "@preact/signals";
import { beforeEach, describe, expect, test } from "vitest";
import { renderWithProviders } from "../../test/renderWithProviders";
import { PlaybackIconType } from "../types/PlaybackIconType";
import { PlaybackIcon } from "./PlaybackIcon";

describe("PlaybackIcon", () => {
  const active: Signal<PlaybackIconType | null> = signal(null);

  beforeEach(() => {
    active.value = null;
  });

  test("no active icon", () => {
    const { container } = renderWithProviders(
      <PlaybackIcon active={active} />
    );
    expect(container.innerHTML).toEqual("");
  });

  test("matches snapshot", () => {
    active.value = "pause";
    const { asFragment, getBySelector } = renderWithProviders(
      <PlaybackIcon active={active} />
    );
    const tcElt = getBySelector(".icon") as HTMLElement;
    expect(tcElt.className.trim()).toEqual("bi icon bi-pause-fill");
    expect(asFragment()).toMatchSnapshot();
  });

  test.each<[PlaybackIconType, string]>([
    ['pause', 'bi-pause-fill'],
    [ 'play' , 'bi-play-fill'],
    [ 'stop', 'bi-stop-fill'],
    [ 'backward', 'bi-skip-backward-fill'],
    [ 'forward', 'bi-skip-forward-fill'],
  ])('icon %s', (name: PlaybackIconType, className: string) => {
    active.value = name;
    const { getBySelector } = renderWithProviders(
      <PlaybackIcon active={active} />
    );
    const tcElt = getBySelector(".icon") as HTMLElement;
    expect(tcElt.classList.contains(className)).toEqual(true);
  });
});
