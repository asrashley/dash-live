import { DrmContextMap } from "./DrmContextMap";
import { KeyParameters } from "./KeyParameters";

export type AdaptationSetJson = {
    content_type: string;
    default_kid: string | null;
    drm?: DrmContextMap;
    fileSuffix: string;
    id: number;
    initURL: string;
    keys?: { [kid: string]: KeyParameters };
    lang: null | string;
    mediaURL: string;
    mimeType: string;
    mode: string;
    par: string;
    segmentAlignment: boolean;
    startWithSAP: number;
    timescale: number;
};
