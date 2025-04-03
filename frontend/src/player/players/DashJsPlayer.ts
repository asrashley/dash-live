import type dashjs from "dashjs";
import { AbstractDashPlayer } from "../types/AbstractDashPlayer";

import { routeMap } from "@dashlive/routemap";
import { importLibrary } from "./importLibrary";
export class DashJsPlayer extends AbstractDashPlayer {
    static LOCAL_VERSIONS: Readonly<string[]> = ['4.7.4', '4.7.1'] as const;

    private player?: dashjs.MediaPlayerClass;

    static cdnTemplate(version: string): string {
        if (DashJsPlayer.LOCAL_VERSIONS.includes(version)) {
            return routeMap.js.url({ filename: `dashjs-${version}.js` });
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
        if (autoplay) {
            videoElement.addEventListener('canplay', this.onCanPlayEvent);
        }
    }

    destroy(): void {
        const { videoElement } = this.props;
        videoElement.removeEventListener('canplay', this.onCanPlayEvent);
        this.player?.destroy();
        this.player = undefined;
    }
}