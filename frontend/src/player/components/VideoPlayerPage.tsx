import { useCallback, useContext, useEffect, useMemo, useRef } from "preact/hooks";
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
import { PlaybackIconType } from "../types/PlaybackIconType";

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
  setIcon: (name: string) => void;
}

export function keyHandler(
  { controls, setIcon, setLocation }: KeyHandlerProps,
  ev: KeyboardEvent
) {
  switch (ev.key) {
    case " ":
    case "MediaPlayPause":
      if (controls.isPaused()) {
        setIcon("play");
        controls.play();
      } else {
        setIcon("pause");
        controls.pause();
      }
      break;
    case "Escape":
    case "MediaStop":
      setIcon("stop");
      controls.stop();
      break;
    case "MediaPlay":
      setIcon("play");
      controls.play();
      break;
    case "MediaPause":
      setIcon("pause");
      controls.pause();
      break;
    case "ArrowLeft":
    case "MediaTrackPrevious":
      setIcon("backward");
      controls.skip(-30);
      break;
    case "ArrowRight":
    case "MediaTrackNext":
      setIcon("forward");
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
  const controls = useSignal<PlayerControls | undefined>();
  const events = useSignal<StatusEvent[]>([]);
  const activeIcon = useSignal<PlaybackIconType | null>(null);
  const { dashParams, keys, loaded } = useDashParameters(
    mode,
    stream,
    manifest,
    searchParams
  );
  const iconTimer = useRef<number | undefined>();
  const mpd = useMemo<string>(
    () => manifestUrl(mode, stream, manifest, searchParams),
    [mode, stream, manifest, searchParams]
  );
  const playerName = useMemo<DashPlayerTypes>(() => {
    return (searchParams.get("player") ?? "native") as DashPlayerTypes;
  }, [searchParams]);
  const setIcon = useCallback((name: PlaybackIconType) => {
    activeIcon.value = name;
    window.clearTimeout(iconTimer.current);
    iconTimer.current = window.setTimeout(() => {
      activeIcon.value = null;
      iconTimer.current = undefined;
    }, 2000);
  }, [activeIcon]);
  const onKeyDown = useCallback((ev: KeyboardEvent) => {
    if (!controls.value) {
      return;
    }
    keyHandler({  controls: controls.value, setIcon, setLocation }, ev);
  }, [controls, setIcon, setLocation]);

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
      window.clearTimeout(iconTimer.current);
      iconTimer.current = undefined;
    };
  }, [onKeyDown, iconTimer]);

  return (
    <div data-testid="video-player-page">
      {loaded.value ? (
        <VideoPlayer
          mpd={mpd}
          playerName={playerName}
          dashParams={dashParams}
          keys={keys}
          currentTime={currentTime}
          controls={controls}
          events={events}
          activeIcon={activeIcon}
        />
      ) : (
        <LoadingSpinner />
      )}
      <StatusPanel events={events} currentTime={currentTime} />
    </div>
  );
}
