import { type ReadonlySignal, useComputed } from "@preact/signals";
import { useCallback, useContext } from "preact/hooks";
import { useLocation } from "wouter-preact";

import { CombinedStream } from "../../hooks/useCombinedStreams";
import { DashPlayerTypes } from "../../player/types/DashPlayerTypes";
import { AppStateContext } from "../../appState";
import { Icon } from "../../components/Icon";

export interface PlayVideoButtonProps {
  videoUrl: ReadonlySignal<URL>;
  stream: ReadonlySignal<CombinedStream>;
}

export function PlayVideoButton({ stream, videoUrl }: PlayVideoButtonProps) {
  const [, setLocation] = useLocation();
  const playerName = useComputed<DashPlayerTypes>(() => {
    return (videoUrl.value.searchParams.get("player") ??
      "native") as DashPlayerTypes;
  });
  const playerVersion = useComputed<string>(
    () => videoUrl.value.searchParams.get(playerName.value) ?? ""
  );
  const { playerLibrary } = useContext(AppStateContext);
  const needsReload = useComputed<boolean>(() => {
    if (playerLibrary.value === null || playerName.value === "native") {
      return false;
    }
    const { name, version } = playerLibrary.value;
    return playerName.value !== name || version !== playerVersion.value;
  });

  const onClick = useCallback(
    (ev: Event) => {
      ev.preventDefault();
      const mustReload = needsReload.value;
      playerLibrary.value = {
        name: playerName.value,
        version: playerVersion.value,
      };
      if (mustReload) {
        window.location.replace(videoUrl.value.href);
      } else {
        setLocation(videoUrl.value.href);
      }
    },
    [
      needsReload,
      playerLibrary,
      playerName,
      playerVersion,
      setLocation,
      videoUrl,
    ]
  );

  return (
    <a
      className="btn btn-lg btn-primary"
      href={videoUrl.value.href}
      data-testid="play-video-button"
      onClick={onClick}>
      <Icon name="play-fill" />
      <span className="title ps-2">Play {stream.value.title}</span>
    </a>
  );
}
