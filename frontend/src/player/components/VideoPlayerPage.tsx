import { useEffect, useMemo } from "preact/hooks";
import { useSignal } from "@preact/signals";
import { useParams } from "wouter-preact";

import { routeMap } from "@dashlive/routemap";

import { PlayerControls } from "../types/PlayerControls";
import { VideoPlayer } from "./VideoPlayer";
import { StatusEvent } from "../types/StatusEvent";
import { StatusPanel } from "./StatusPanel";
import { RouteParamsType } from "../../types/RouteParamsType";

import { DashPlayerTypes } from "../types/DashPlayerTypes";
import { useDashParameters } from "../hooks/useDashParameters";
import { LoadingSpinner } from "../../components/LoadingSpinner";

import { useSearchParams } from "../../hooks/useSearchParams";

import "../styles/video.less";

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

export default function VideoPlayerPage() {
  const { mode, stream, manifest } = useParams<RouteParamsType>();
  const { searchParams } = useSearchParams();
  const currentTime = useSignal<number>(0);
  const controls = useSignal<PlayerControls | undefined>();
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

  useEffect(() => {
    document.body.classList.add("video-player");
    return () => {
      document.body.classList.remove("video-player");
    };
  }, [cinemaMode]);

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
        />
      ) : (
        <LoadingSpinner />
      )}
      <StatusPanel events={events} currentTime={currentTime} />
    </div>
  );
}
