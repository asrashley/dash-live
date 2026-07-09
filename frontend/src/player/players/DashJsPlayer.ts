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
        const player = MediaPlayer().create();
        this.player = player;
        player.updateSettings(settings);
        player.initialize(videoElement, source, autoplay);
        const subtitlesElement = this.subtitlesElement;
        if (subtitlesElement) {
            player.attachTTMLRenderingDiv(subtitlesElement);
        }
        const { signal } = this.disposeController;
        if (autoplay) {
            videoElement.addEventListener('canplay', this.onCanPlayEvent, { signal });
        }
        player.on(MediaPlayer.events.PERIOD_SWITCH_COMPLETED, this.sendTrackList);
    }

    setSubtitlesElement(elt: HTMLDivElement | null) {
        super.setSubtitlesElement(elt);
        if (elt) {
            this.player?.attachTTMLRenderingDiv(elt);
        }
    }

    setTextTrack(track: MediaTrack | null) {
        const player = this.player;
        if (!player) {
            return;
        }
        let idx: number = -1;
        if (track) {
            const tracks = player.getTracksFor('text');
            idx = tracks.findIndex(trk => trk.id === track.id);
        }
        player.setTextTrack(idx);
        this.sendTrackList();
    }

    destroy(): void {
        this.disposeController.abort('destroy player');
        this.player?.reset();
        this.player?.destroy();
        this.player = undefined;
    }

    private sendTrackList = () => {
        const player = this.player;
        if (!player) {
            return;
        }
        const allTracks: MediaTrack[] = [];
        const mediaTypes = ['video', 'audio', 'text'] as const;
        mediaTypes.forEach((mediaType) => {
            let current: MediaInfo | null = player.getCurrentTrackFor(mediaType);
            // getCurrentTrackFor always returns a track, even if none is selected
            if (mediaType === 'text' && player.getCurrentTextTrackIndex() <  0) {
                current = null;
            }
            const tracks: MediaTrack[] = player.getTracksFor(mediaType).map(
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
        id: String(id),
        trackType: mediaTrackType(mi.type),
        active: current?.id === id,
        ...(language == null ? {} : { language }),
    };
    return mt;
}