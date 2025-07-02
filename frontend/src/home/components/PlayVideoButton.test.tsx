import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from "vitest";
import { fireEvent } from "@testing-library/preact";
import { signal } from "@preact/signals";
import { useLocation } from "wouter-preact";

import { CombinedStream } from "../../hooks/useCombinedStreams";
import { renderWithProviders } from "../../test/renderWithProviders";
import { PlayVideoButton } from "./PlayVideoButton";
import { DashPlayerTypes } from "../../player/types/DashPlayerTypes";
import { AppStateType } from "../../appState";
import { DialogState } from "../../types/DialogState";
import { PlayerLibraryState } from "../../types/PlayerLibraryState";

vi.mock("wouter-preact", async (importOriginal) => {
  return {
    ...(await importOriginal()),
    useLocation: vi.fn(),
  };
});

describe("PlayVideoButton component", () => {
  const useLocationSpy = vi.mocked(useLocation);
  const setLocation = vi.fn();
  const mockNavigate = vi.fn();
  const videoUrl = signal<URL>(new URL("http://example.local"));
  const stream = signal<CombinedStream>({
    title: "Stream Title",
    value: "bbb",
    mps: false,
  });
  const dialog = signal<DialogState | null>(null);
  const cinemaMode = signal<boolean>(false);
  const playerLibrary = signal<PlayerLibraryState | null>(null);
  const mockLocation = {
    ...new URL(document.location.href),
    pathname: "/",
    replace: vi.fn(),
  };

  function setVideoUrl(player: DashPlayerTypes, version: string) {
    const url = `http://example.local?player=${player}&${player}=${version}`;
    videoUrl.value = new URL(url);
  }

  beforeAll(() => {
    vi.stubGlobal("location", mockLocation);
  });

  beforeEach(() => {
    useLocationSpy.mockReturnValue(["/play", setLocation]);
    playerLibrary.value = null;
    dialog.value = null;
    cinemaMode.value = false;
    vi.stubGlobal("navigation", mockNavigate);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test.each<DashPlayerTypes>(["dashjs", "shaka", "native"])(
    "matches snapshot for %s",
    (player: DashPlayerTypes) => {
      setVideoUrl(player, "1.0.0");
      const { asFragment } = renderWithProviders(
        <PlayVideoButton stream={stream} videoUrl={videoUrl} />
      );
      expect(asFragment()).toMatchSnapshot();
    }
  );

  test("navigates to video URL without reload", () => {
    setVideoUrl("native", "");
    const { getByTestId, appState } = renderWithProviders(
      <PlayVideoButton stream={stream} videoUrl={videoUrl} />
    );
    const button = getByTestId("play-video-button") as HTMLAnchorElement;
    fireEvent.click(button);
    expect(setLocation).toHaveBeenCalledWith(videoUrl.value.href);
    expect(mockLocation.replace).not.toHaveBeenCalled();
    expect(appState.playerLibrary.value).toEqual({
      name: "native",
      version: "",
    });
  });

  test("switching to native player does not need a reload", () => {
    playerLibrary.value = {
      name: "dashjs",
      version: "1.0.0",
    };
    setVideoUrl("native", "");
    const { getByTestId, appState } = renderWithProviders(
      <PlayVideoButton stream={stream} videoUrl={videoUrl} />
    );
    const button = getByTestId("play-video-button") as HTMLAnchorElement;
    fireEvent.click(button);
    expect(setLocation).toHaveBeenCalledWith(videoUrl.value.href);
    expect(mockLocation.replace).not.toHaveBeenCalled();
    expect(appState.playerLibrary.value).toEqual({
      name: "native",
      version: "",
    });
  });

  test("reloads when player changes", () => {
    const initialAppState: AppStateType = {
      dialog,
      cinemaMode,
      playerLibrary,
      backdrop: undefined,
      closeDialog: vi.fn,
    };
    playerLibrary.value = {
      name: "dashjs",
      version: "1.0.0",
    };
    setVideoUrl("shaka", "1.2.3");
    const { getByTestId, appState } = renderWithProviders(
      <PlayVideoButton stream={stream} videoUrl={videoUrl} />,
      { appState: initialAppState }
    );
    expect(appState.playerLibrary.value).toEqual(playerLibrary.value);
    const button = getByTestId("play-video-button") as HTMLAnchorElement;
    fireEvent.click(button);
    expect(setLocation).not.toHaveBeenCalled();
    expect(mockLocation.replace).toHaveBeenCalledWith(videoUrl.value.href);
  });
});
