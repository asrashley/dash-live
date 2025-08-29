import { useCallback, useContext, useEffect, useMemo } from "preact/hooks";
import { useSignal } from "@preact/signals";
import { useLocation, useParams } from "wouter-preact";

import { routeMap, uiRouteMap } from "@dashlive/routemap";

import { PlayerControls } from "../types/PlayerControls";
import { VideoPlayer } from "./VideoPlayer";
import { StatusEvent } from "../types/StatusEvent";
import { StatusPanel } from "./StatusPanel";
import { RouteParamsType } from "../../types/RouteParamsType";

import { DashPlayerTypes } from "../types/DashPlayerTypes";
import { useDashParameters } from "../hooks/useDashParameters";
import { LoadingSpinner } from "../../components/LoadingSpinner";

import { useSearchParams } from "../../hooks/useSearchParams";
import { AppStateContext } from "../../appState";

import "../styles/video.less";
import { PlaybackControls } from "./PlaybackControls";

export function manifestUrl(
  mode: string,
  stream: string,
  manifest: string,
  params: Readonly<URLSearchParams>
): string {
  const query = params.size ? `?${params.toString()}` : "";
  if (mode.startsWith("mps-")) {
    return `${routeMap.mpsManifest.url({
      mode: mode.slice(4),
      mps_name: stream,
      manifest,
    })}.mpd${query}`;
  }
  return `${routeMap.dashMpdV3.url({ mode, stream, manifest })}.mpd${query}`;
}

export interface KeyHandlerProps {
  controls: PlayerControls;
  setLocation: (url: string) => void;
}

export function keyHandler(
  { controls, setLocation }: KeyHandlerProps,
  ev: KeyboardEvent
) {
  switch (ev.key) {
    case " ":
    case "MediaPlayPause":
      if (controls.isPaused.value) {
        controls.play();
      } else {
        controls.pause();
      }
      break;
    case "Escape":
    case "MediaStop":
      controls.stop();
      break;
    case "MediaPlay":
      controls.play();
      break;
    case "MediaPause":
      controls.pause();
      break;
    case "ArrowLeft":
    case "MediaTrackPrevious":
      controls.skip(-30);
      break;
    case "ArrowRight":
    case "MediaTrackNext":
      controls.skip(30);
      break;
    case "Home":
    case "Finish":
      setLocation(uiRouteMap.home.url());
      break;
  }
}

export default function VideoPlayerPage() {
  const [, setLocation] = useLocation();
  const { mode, stream, manifest } = useParams<RouteParamsType>();
  const { searchParams } = useSearchParams();
  const { cinemaMode } = useContext(AppStateContext);
  const currentTime = useSignal<number>(0);
  const controls = useSignal<PlayerControls | null>(null);
  const events = useSignal<StatusEvent[]>([]);
  const { dashParams, keys, loaded } = useDashParameters(
    mode,
    stream,
    manifest,
    searchParams
  );
  const mpd = useMemo<string>(
    () => manifestUrl(mode, stream, manifest, searchParams),
    [mode, stream, manifest, searchParams]
  );
  const playerName = useMemo<DashPlayerTypes>(() => {
    return (searchParams.get("player") ?? "native") as DashPlayerTypes;
  }, [searchParams]);

  const onKeyDown = useCallback((ev: KeyboardEvent) => {
    if (!controls.value) {
      return;
    }
    keyHandler({  controls: controls.value, setLocation }, ev);
  }, [controls, setLocation]);

  const setPlayer = useCallback((player: PlayerControls | null) => {
    controls.value = player;
  }, [controls]);

  useEffect(() => {
    cinemaMode.value = true;
    return () => {
      cinemaMode.value = false;
    };
  }, [cinemaMode]);

  useEffect(() => {
    document.body.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.removeEventListener("keydown", onKeyDown);
    };
  }, [onKeyDown]);

  return (
    <div data-testid="video-player-page">
      {loaded.value ? (
        <VideoPlayer
          mpd={mpd}
          playerName={playerName}
          dashParams={dashParams}
          keys={keys}
          currentTime={currentTime}
          events={events}
          setPlayer={setPlayer}
        />
      ) : (
        <LoadingSpinner />
      )}
      <StatusPanel events={events} />
      <PlaybackControls currentTime={currentTime} controls={controls} />
    </div>
  );
}
