import { AbstractDashPlayer } from "../../types/AbstractDashPlayer";

export class FakePlayer extends AbstractDashPlayer {
  public paused = false;
  public subtitlesElement: HTMLDivElement | null = null;

  async initialize(source: string) {
    const { videoElement } = this.props;
    videoElement.src = source;
    Object.defineProperties(videoElement, {
      pause: {
        value: this.pause,
      },
    });
  }

  destroy() {}

  pause = () => {
    this.paused = true;
  }

  setSubtitlesElement(subtitlesElement: HTMLDivElement | null): void {
    this.subtitlesElement = subtitlesElement;
  }
}