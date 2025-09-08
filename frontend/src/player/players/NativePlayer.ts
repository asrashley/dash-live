import { MediaTrack } from "../types/MediaTrack";
import { AbstractDashPlayer } from "./AbstractDashPlayer";

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

    override setSubtitlesElement(_subtitlesElement: HTMLDivElement | null) {
        // no op
    }

    override setTextTrack(track: MediaTrack | null) {
        const { videoElement } = this.props;
        for(let i=0; i < videoElement.textTracks.length; ++i) {
            const tt = videoElement.textTracks[i];
            if(track?.id === tt.id) {
                tt.mode = 'showing';
            } else {
                tt.mode = 'disabled';
            }
        }
    }

}