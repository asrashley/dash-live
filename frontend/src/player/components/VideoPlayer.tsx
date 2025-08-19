import { useCallback } from "preact/hooks";
import { useSignal, useSignalEffect } from "@preact/signals";

import { PlaybackIcon } from "./PlaybackIcon";
import { VideoElement, VideoElementProps } from "./VideoElement";

export type VideoPlayerProps = Omit<VideoElementProps, 'subtitlesElement'>;

export function VideoPlayer(props: VideoPlayerProps) {
  const subtitlesElement = useSignal<HTMLDivElement | undefined>();
  const setSubsElt = useCallback((elt: HTMLDivElement) => {
    subtitlesElement.value = elt;
  }, [subtitlesElement]);

  useSignalEffect(() => {
    const controls = props.controls.value;
    const subs = subtitlesElement.value;
    if (controls && subs) {
      controls.setSubtitlesElement(subs);
    }
  });

  return (
    <div id="vid-window">
      <PlaybackIcon active={props.activeIcon} />
      <VideoElement {...props} />
      <div className="subtitles-wrapper">
        <div className="subtitles" ref={setSubsElt} />
      </div>
    </div>
  );
}
