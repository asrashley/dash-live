import type { MediaPlayerClass, MediaPlayerSettingClass, MediaInfo } from "dashjs";
import { AbstractDashPlayer } from "./AbstractDashPlayer";

import { routeMap } from "@dashlive/routemap";
import { importLibrary } from "./importLibrary";
import { MediaTrack } from "../types/MediaTrack";
import { MediaTrackType } from "../types/MediaTrackType";
export class DashJsPlayer extends AbstractDashPlayer {
    static LOCAL_VERSIONS: Readonly<string[]> = ['5.0.3', '4.7.4', '4.7.1'] as const;

    private player?: MediaPlayerClass;
    private disposeController = new AbortController();

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
        const settings: MediaPlayerSettingClass = {
            streaming: {
                text: {
                    defaultEnabled: true,
                },
            },
        };
        this.player = MediaPlayer().create();
        this.player.updateSettings(settings);
        this.player.initialize(videoElement, source, autoplay);
        if (this.subtitlesElement) {
            this.player.attachTTMLRenderingDiv(this.subtitlesElement);
        }
        const { signal } = this.disposeController;
        if (autoplay) {
            videoElement.addEventListener('canplay', this.onCanPlayEvent, { signal });
        }
        this.player.on(MediaPlayer.events.PERIOD_SWITCH_COMPLETED, this.sendTrackList);
    }

    setSubtitlesElement(elt: HTMLDivElement | null) {
        super.setSubtitlesElement(elt);
        this.player?.attachTTMLRenderingDiv(elt);
    }

    setTextTrack(track: MediaTrack | null) {
        if (!this.player) {
            return;
        }
        let idx: number = -1;
        if (track) {
            const tracks = this.player.getTracksFor('text');
            idx = tracks.findIndex(trk => trk.id === track.id);
        }
        this.player.setTextTrack(idx);
        this.sendTrackList();
    }

    destroy(): void {
        this.disposeController.abort('destroy player');
        this.player?.reset();
        this.player?.destroy();
        this.player = undefined;
    }

    private sendTrackList = () => {
        if (!this.player) {
            return;
        }
        const allTracks: MediaTrack[] = [];
        ['video', 'audio', 'text'].forEach((mediaType: MediaInfo["type"])  => {
            let current: MediaInfo | null = this.player.getCurrentTrackFor(mediaType);
            // getCurrentTrackFor always returns a track, even if none is selected
            if (mediaType === 'text' && this.player.getCurrentTextTrackIndex() <  0) {
                current = null;
            }
            const tracks: MediaTrack[] = this.player.getTracksFor(mediaType).map(
                mi => mediaInfoToMediaTrack(mi, current));
            tracks.forEach(trk => allTracks.push(trk));
        });
        this.maybeTracksChanged(allTracks);
    };
}

export function mediaTrackType(tt: MediaInfo["type"]): MediaTrackType {
    switch (tt) {
        case 'video':
            return MediaTrackType.VIDEO;
        case 'audio':
            return MediaTrackType.AUDIO;
        case 'text':
            return MediaTrackType.TEXT;
        case 'image':
            return MediaTrackType.IMAGE;
    }
    return MediaTrackType.UNKNOWN;
}

export function mediaInfoToMediaTrack(mi: Readonly<MediaInfo>, current: MediaInfo | null):  MediaTrack {
    const { id, lang: language } = mi;
    const mt: MediaTrack = {
        id,
        trackType: mediaTrackType(mi.type),
        language,
        active: current?.id === id,
    }
    return mt;
}