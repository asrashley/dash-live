import type shaka from 'shaka-player';

import { routeMap } from "@dashlive/routemap";
import { AbstractDashPlayer } from "../types/AbstractDashPlayer";
import { OptionMapWithChildren } from '@dashlive/options';
import { importLibrary } from './importLibrary';

export interface ShakaConfig {
    drm: {
        servers: {
            [drm: string]: string;
        }
        clearKeys?: {
            [kid: string]: string;
        }
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

export class ShakaPlayer extends AbstractDashPlayer {
    static LOCAL_VERSIONS: Readonly<string[]> = ['4.13.4', '4.11.2', '4.3.8'] as const;
    private player?: shaka.Player;

    static cdnTemplate(version: string): string {
        if (ShakaPlayer.LOCAL_VERSIONS.includes(version)) {
            return routeMap.js.url({ filename: `shaka-player.${version}.js` });
        }
        return `https://ajax.googleapis.com/ajax/libs/shaka-player/${version}/shaka-player.compiled.js`
    }

    async initialize(mpd: string, options: OptionMapWithChildren) {
        const { videoElement, version = ShakaPlayer.LOCAL_VERSIONS[0] } = this.props;
        const jsUrl = ShakaPlayer.cdnTemplate(version);
        await importLibrary(jsUrl);

        const { drmSelection = [], clearkey, playready } = options as unknown as AllDrmOptions;
        const shakaConfig: ShakaConfig = {
            drm: {
                servers: {},
            },
        };
        const { polyfill, log, Player } = window['shaka'];
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
        this.player.attach(videoElement);
        this.player.configure(shakaConfig);
        this.player.addEventListener('error', this.onErrorEvent);
        try {
            await this.player.load(mpd);
            this.player.addEventListener('loaded', this.onLoadedEvent);
        } catch (err) {
            this.props.logEvent('error', `${err}`);
        }
        videoElement.addEventListener('canplay', this.onCanPlayEvent);
    }

    setSubtitlesElement(subtitlesElement: HTMLDivElement | null) {
        this.player?.setVideoContainer(subtitlesElement);
    }

    destroy(): void {
        const { videoElement } = this.props;
        videoElement.removeEventListener('canplay', this.onCanPlayEvent);
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
    };
}