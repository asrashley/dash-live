import { MediaTrack } from "../../types/MediaTrack";
import { AbstractDashPlayer } from "../AbstractDashPlayer";

export class FakePlayer extends AbstractDashPlayer {
  public paused = false;
  public subtitlesElement: HTMLDivElement | null = null;
  public textTrack: MediaTrack | null = null;

  async initialize(source: string) {
    const { videoElement } = this.props;
    videoElement.src = source;
    Object.defineProperties(videoElement, {
      pause: {
        value: this.pause,
        writable: true,
      },
    });
  }

  destroy() {}

  pause = () => {
    this.paused = true;
  }

  setSubtitlesElement(subtitlesElement: HTMLDivElement | null) {
    this.subtitlesElement = subtitlesElement;
  }

  setTextTrack(track: MediaTrack | null) {
    this.textTrack = track;
  }

  callMaybeTracksChanged(tracks: MediaTrack[]) {
    this.maybeTracksChanged(tracks);
  }
}