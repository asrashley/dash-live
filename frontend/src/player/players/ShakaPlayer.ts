import type shaka from 'shaka-player';

import { routeMap } from "@dashlive/routemap";
import { AbstractDashPlayer } from "./AbstractDashPlayer";
import { OptionMapWithChildren } from '@dashlive/options';
import { importLibrary } from './importLibrary';
import { MediaTrack } from '../types/MediaTrack';
import { MediaTrackType } from '../types/MediaTrackType';

export interface ShakaConfig {
    drm: {
        servers: {
            [drm: string]: string;
        }
        clearKeys?: {
            [kid: string]: string;
        }
    },
    preferredAudioLanguage?: string;
    preferredTextLanguage?: string;
    textDisplayer?: {
        captionsUpdatePeriod?: number;
        fontScaleFactor?: number;
    }
}

export interface ShakaError extends Error {
    severity: number;
    category: number;
    code: number;
}

function isShakaError(err: unknown): err is ShakaError {
    return typeof err === 'object' && err !== null && 'severity' in err && 'category' in err && 'code' in err;
}

interface DrmSettings {
    licenseUrl: string | null;
}

export interface AllDrmOptions {
    drmSelection: string[];
    clearkey: DrmSettings;
    marlin: DrmSettings;
    playready: DrmSettings;
}

export interface ShakaTrack {
    active: boolean;
    language?: string;
    label: string | null;
}

export interface ShakaTextTrack extends ShakaTrack {
    id: number;
}

export class ShakaPlayer extends AbstractDashPlayer {
    static LOCAL_VERSIONS: Readonly<string[]> = ['4.13.4', '4.11.2', '4.3.8'] as const;
    static CSS_LINK_ID: Readonly<string> = "shaka-controls";

    private player?: shaka.Player;
    private eventManager?: shaka.util.EventManager;

    static cdnTemplate(version: string): string {
        if (ShakaPlayer.LOCAL_VERSIONS.includes(version)) {
            return routeMap.js.url({ filename: `shaka-player.${version}.js` });
        }
        return `https://ajax.googleapis.com/ajax/libs/shaka-player/${version}/shaka-player.compiled.js`
    }

    async initialize(mpd: string, options: OptionMapWithChildren) {
        const { videoElement, textEnabled, version = ShakaPlayer.LOCAL_VERSIONS[0] } = this.props;
        const jsUrl = ShakaPlayer.cdnTemplate(version);
        await importLibrary(jsUrl);

        const { drmSelection = [], clearkey, playready } = options as unknown as AllDrmOptions;
        const shakaConfig: ShakaConfig = {
            drm: {
                servers: {},
            },
        };
        if (textEnabled) {
            shakaConfig.preferredTextLanguage = this.props.textLanguage;
        }
        const { polyfill, log, util, Player } = window['shaka'];
        polyfill.installAll();
        if (log?.setLevel) {
            log.setLevel(log.Level.V1);
        }
        if (drmSelection.includes('playready') && playready.licenseUrl) {
            shakaConfig.drm.servers['com.microsoft.playready'] = playready.licenseUrl;
        }
        if (drmSelection.includes('clearkey') && clearkey.licenseUrl) {
            shakaConfig.drm.servers['org.w3.clearkey'] = clearkey.licenseUrl;
        }
        this.player = new Player();
        this.eventManager = new util.EventManager();
        this.player.attach(videoElement);
        this.player.configure(shakaConfig);
        if (this.subtitlesElement) {
            this.player.setVideoContainer(this.subtitlesElement);
        }
        this.player.addEventListener('error', this.onErrorEvent);
        try {
            await this.player.load(mpd);
        } catch (err) {
            this.props.logEvent('error', `${err}`);
        }
        this.eventManager.listen(this.player, 'loaded', this.onLoadedEvent);
        this.eventManager.listen(this.player, 'trackschanged', this.onTracksChanged);
        videoElement.addEventListener('canplay', this.onCanPlayEvent);
        const styles: HTMLLinkElement = document.createElement('link');
        styles.setAttribute("rel", "stylesheet");
        styles.setAttribute("href", routeMap.css.url({filename: "shaka/controls.css"}));
        styles.setAttribute("id", ShakaPlayer.CSS_LINK_ID);
        document.head.appendChild(styles);
    }

    setSubtitlesElement(subtitlesElement: HTMLDivElement | null) {
        super.setSubtitlesElement(subtitlesElement);
        this.player?.setVideoContainer(subtitlesElement);
    }

    setTextTrack(track: MediaTrack | null) {
        //this.player?.configure('preferredTextLanguage', textLanguage);
        this.player?.setTextTrackVisibility(track !== null);
        if (!track){
            return;
        }
        const textTracks: ShakaTextTrack[] = this.player.getTextTracks() || [];
        const selTrack = textTracks.find((trk: ShakaTextTrack) => track.id === `${trk.id}`);
        if (selTrack) {
            this.player.selectTextTrack(selTrack as unknown as shaka.extern.Track);
        }
    }

    destroy(): void {
        const { videoElement } = this.props;
        videoElement.removeEventListener('canplay', this.onCanPlayEvent);
        this.eventManager?.removeAll();
        this.eventManager = undefined;
        const link = document.head.querySelector(`link[id="${ShakaPlayer.CSS_LINK_ID}"]`);
        link?.remove();
        this.player?.destroy();
        this.player = undefined;
    }

    private onErrorEvent = (ev: CustomEvent) => {
        const err: Error | ShakaError = ev.detail;
        const { logEvent } = this.props;
        if (isShakaError(err)) {
            logEvent('error', `${err.severity} - ${err.category} - ${err.code}`);
        } else {
            logEvent('error', `${err}`);
        }
    };

    private onLoadedEvent = () => {
        this.props.logEvent('loaded', '');
        this.onTracksChanged();
    };

    private onTracksChanged = () => {
        if (!this.player) {
            return;
        }
        const textTracks: ShakaTextTrack[] = this.player.getTextTracks() || [];
        const allTracks: MediaTrack[] = [
            ...textTracks.map((trk) => mediaInfoToMediaTrack(`${trk.id}`, MediaTrackType.TEXT, trk)),
        ];
        this.maybeTracksChanged(allTracks);
    };
}

export function mediaInfoToMediaTrack(id: string, trackType: MediaTrackType, trk: Readonly<ShakaTrack>):  MediaTrack {
    const { language, active } = trk;
    const mt: MediaTrack = {
        id,
        trackType,
        language,
        active,
    }
    return mt;
}