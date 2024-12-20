import { CsrfTokenCollection } from "./CsrfTokenCollection";
import { KeyMaterial } from "./KeyMaterial";
import { Stream } from "./Stream";

export interface AllStreamsJson {
    csrf_tokens: CsrfTokenCollection;
    keys: KeyMaterial[];
    streams: Stream[];
}