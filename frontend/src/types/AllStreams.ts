import { CsrfTokenCollection } from "./CsrfTokenCollection";
import { KeyMaterial } from "./KeyMaterial";
import { Stream } from "./Stream";

export interface AllStreamsResponse {
    keys: KeyMaterial[];
    streams: Stream[];
}

export interface AllStreamsJson extends AllStreamsResponse {
    csrf_tokens: CsrfTokenCollection;
}