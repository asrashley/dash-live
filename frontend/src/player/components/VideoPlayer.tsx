import { useRef } from "preact/hooks";
import { PlaybackIcon } from "./PlaybackIcon";
import { VideoElement, VideoElementProps } from "./VideoElement";

export type VideoPlayerProps = Omit<VideoElementProps, 'subtitlesElement'>;

export function VideoPlayer(props: VideoPlayerProps) {
  const subtitlesElement = useRef<HTMLDivElement>();

  return (
    <div id="vid-window">
      <PlaybackIcon active={props.activeIcon} />
      <VideoElement {...props}  />
    </div>
  );
}
