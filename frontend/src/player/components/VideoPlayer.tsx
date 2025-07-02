import { Icon } from "../../components/Icon";
import { VideoElement, VideoElementProps } from "./VideoElement";

export type VideoPlayerProps = VideoElementProps;
export function VideoPlayer(props: VideoPlayerProps) {
  return (
    <div id="vid-window">
      <Icon name="pause" className="fs-2" />
      <Icon name="step-forward" className="fs-2" />
      <Icon name="step-backward" className="fs-2" />
      <Icon name="stop" className="fs-2" />
      <VideoElement {...props} />
    </div>
  );
}
