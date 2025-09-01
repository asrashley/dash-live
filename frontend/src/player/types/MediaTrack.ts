import { MediaTrackType } from "./MediaTrackType";

export type MediaTrack = {
    id: string;
    trackType: MediaTrackType;
    language?: string;
    active: boolean;
}