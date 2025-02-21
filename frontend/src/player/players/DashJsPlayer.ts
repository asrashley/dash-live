import type { MediaPlayer } from "dashjs";
import { DashPlayer } from "../types/DashPlayer";

export class DashJsPlayer extends DashPlayer {
    private player?: MediaPlayer;
    private videoElement?: HTMLVideoElement;

    async initialize(videoElement: HTMLVideoElement, source: string): Promise<boolean> {
        this.player = dashjs.MediaPlayer().create();
        player.initialize(videoElement, source, true);
        videoElement.addEventListener('canplay', this.canPlay);
        return true;
    }

    private canPlay = () => {
        if (!this.videoElement) {
            return;
        }
        console.log('start playback');
        this.videoElement.play();
    };
}