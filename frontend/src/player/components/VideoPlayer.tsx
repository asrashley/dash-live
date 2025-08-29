import { useCallback, useEffect, useRef } from "preact/hooks";
import { useSignal, useSignalEffect } from "@preact/signals";

import { PlaybackIcon } from "./PlaybackIcon";
import { VideoElement, VideoElementProps } from "./VideoElement";
import { PlaybackIconType } from "../types/PlaybackIconType";
import { PlayerControls } from "../types/PlayerControls";

export type VideoPlayerProps = Omit<VideoElementProps, 'subtitlesElement'>;

export function VideoPlayer({setPlayer, ...props}: VideoPlayerProps) {
  const subtitlesElement = useSignal<HTMLDivElement | undefined>();
  const vidControls = useSignal<PlayerControls | null>(null);
  const setSubsElt = useCallback((elt: HTMLDivElement) => {
    subtitlesElement.value = elt;
  }, [subtitlesElement]);
  const activeIcon = useSignal<PlaybackIconType | null>(null);
  const iconTimer = useRef<number | undefined>();

  const setIcon = useCallback((name: PlaybackIconType) => {
    activeIcon.value = name;
    window.clearTimeout(iconTimer.current);
    iconTimer.current = window.setTimeout(() => {
        activeIcon.value = null;
        iconTimer.current = undefined;
    }, 2000);
  }, [activeIcon]);

  const onSetPlayer = useCallback((controls: PlayerControls | null) => {
    vidControls.value = controls;
    if (!controls) {
      setPlayer(null);
      return;
    }
    const wrappedControls: PlayerControls = {
      ...controls,
      pause: () => {
        setIcon('pause');
        return controls.pause();
      },
      play: () => {
        setIcon('play');
        return controls.play();
      },
      skip: (seconds: number) => {
        setIcon(seconds > 0 ? 'forward' : 'backward');
        return controls.skip(seconds);
      },
      stop: () => {
        setIcon('stop');
        return controls.stop();
      }
    };
    setPlayer(wrappedControls);
  }, [setIcon, setPlayer, vidControls]);

  useSignalEffect(() => {
    const subs = subtitlesElement.value;
    const controls = vidControls.value;
    if (controls && subs) {
      controls.setSubtitlesElement(subs);
    }
  });

  useEffect(() => {
    return () => {
      window.clearTimeout(iconTimer.current);
        iconTimer.current = undefined;
    };
  }, [iconTimer]);

  return (
    <div id="vid-window">
      <PlaybackIcon active={activeIcon} />
      <VideoElement {...props} setPlayer={onSetPlayer} />
      <div className="subtitles-wrapper">
        <div className="subtitles" ref={setSubsElt} />
      </div>
    </div>
  );
}
