import { AbstractDashPlayer } from "../types/AbstractDashPlayer";

export class NativePlayer extends AbstractDashPlayer {
    async initialize(source: string): Promise<void> {
        const { autoplay = false, videoElement } = this.props;
        videoElement.src = source;
        if (autoplay) {
            videoElement.addEventListener('canplay', this.onCanPlayEvent);
        }
    }

    destroy(): void {
        const { videoElement } = this.props;
        videoElement.removeEventListener('canplay', this.onCanPlayEvent);
    }
}