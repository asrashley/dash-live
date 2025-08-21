import type { MediaPlayerClass } from "dashjs";
import { AbstractDashPlayer } from "../types/AbstractDashPlayer";

import { routeMap } from "@dashlive/routemap";
import { importLibrary } from "./importLibrary";
export class DashJsPlayer extends AbstractDashPlayer {
    static LOCAL_VERSIONS: Readonly<string[]> = ['5.0.3', '4.7.4', '4.7.1'] as const;

    private player?: MediaPlayerClass;

    static cdnTemplate(version: string): string {
        if (DashJsPlayer.LOCAL_VERSIONS.includes(version)) {
            return routeMap.js.url({ filename: `dashjs-${version}/dash.all.min.js` });
        }
        return `https://cdn.dashjs.org/${version}/dash.all.min.js`;
    }

    async initialize(source: string): Promise<void> {
        const { autoplay = false, version = DashJsPlayer.LOCAL_VERSIONS[0], videoElement } = this.props;
        const jsUrl = DashJsPlayer.cdnTemplate(version);
        await importLibrary(jsUrl);
        const { MediaPlayer } = window["dashjs"];
        this.player = MediaPlayer().create();
        this.player.initialize(videoElement, source, autoplay);
        if (this.subtitlesElement) {
            this.player.attachTTMLRenderingDiv(this.subtitlesElement);
        }
        if (autoplay) {
            videoElement.addEventListener('canplay', this.onCanPlayEvent);
        }
    }

    setSubtitlesElement(elt: HTMLDivElement | null) {
        super.setSubtitlesElement(elt);
        this.player?.attachTTMLRenderingDiv(elt);
    }

    destroy(): void {
        const { videoElement } = this.props;
        videoElement.removeEventListener('canplay', this.onCanPlayEvent);
        this.player?.reset();
        this.player?.destroy();
        this.player = undefined;
    }
}