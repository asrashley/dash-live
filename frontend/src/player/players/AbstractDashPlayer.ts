import type { OptionMapWithChildren } from "@dashlive/options";
import { KeyParameters } from "../types/KeyParameters";
import { MediaTrack } from "../types/MediaTrack";
import isEqual from "lodash.isequal";

export interface DashPlayerProps {
    version?: string;
    autoplay?: boolean;
    videoElement: HTMLVideoElement;
    textLanguage: string;
    textEnabled: boolean;
    logEvent(eventName: string, text: string): void;
    tracksChanged(tracks: MediaTrack[]): void;
}

export abstract class AbstractDashPlayer {
    protected subtitlesElement: HTMLDivElement | null = null;
    private currentTracks: Map<string, MediaTrack> = new Map();

    // eslint-disable-next-line no-useless-constructor
    constructor(protected props: DashPlayerProps) {
        /* no op */
    }

    abstract initialize(mpd: string, options: OptionMapWithChildren, keys: Map<string, KeyParameters>): Promise<void>;

    abstract destroy(): void;

    abstract setTextTrack(track: MediaTrack | null) : void;

    setSubtitlesElement(subtitlesElement: HTMLDivElement | null) {
        this.subtitlesElement = subtitlesElement;
    }

    protected onCanPlayEvent = async () => {
        const { videoElement } = this.props;
        try {
            await videoElement.play();
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        } catch(err) {
            videoElement.muted = true;
            videoElement.play();
        }
        videoElement.removeEventListener('canplay', this.onCanPlayEvent);
    };

    protected maybeTracksChanged(tracks: MediaTrack[]) {
        let changed = false;
        const currentIds = new Set<string>(this.currentTracks.keys());
        const newMap: Map<string, MediaTrack> = new Map();
        tracks.forEach((trk) => {
            const key = `${trk.trackType}:${trk.id}`;
            newMap.set(key, trk);
            const current = this.currentTracks.get(key);
            if (current) {
                 changed = changed || !isEqual(trk, current);
                 currentIds.delete(key);
            } else {
                changed = true;
            }
        });
        if (currentIds.size > 0) {
            changed = true;
        }
        if (!changed) {
            return;
        }
        this.currentTracks = newMap;
        this.props.tracksChanged(tracks);
    }
}